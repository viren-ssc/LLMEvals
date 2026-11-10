"""Bridge incoming HPC exports to existing fixed-rubric evaluator and checkpoint engine."""

import argparse
import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from .calibration.evaluate import read_results
from .calibration.schema import CalibrationCase, EvidenceReview
from .evaluation_runner import evaluate_hpc_pilot
from .final_metrics import FINAL_JSON, SOURCE_JSON, file_hash, load_final
from .hpc_ingestion import Generation, join_generations, load_benchmark, read_records, workload
from .settings import ROOT, Settings
from .storage import now, versions, write_json

INCOMING = ROOT / "data/incoming"
WORKBOOK = INCOMING / "Canadian-ness_Llama_756_Ready_for_DeepEval.xlsx"
GENERATIONS = INCOMING / "Canadian-ness_Llama_756_Generations.jsonl"
PREPARED = ROOT / "data/processed/llama_756_v1"
RUN = ROOT / "outputs/evaluations/llama_pilot_20261106_v1"
EXPECTED_RUBRIC_HASH = "bb9889807b7babc8feed6a97ddd0c12c0fa334627e5d295017167fbd0a767cb2"
EVIDENCE_ATTESTATION = (
    "User-supplied project task states benchmark reference answers are verified and context "
    "is evidence-based supporting text. This imports that user attestation for provisional "
    "judging only; no new independent source verification or verbatim-quotation claim."
)


def save_jsonl(path, rows):
    text = "".join(json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n" for r in rows)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") != text:
        raise ValueError(f"Prepared artifact differs: {path}; choose a new version")
    if not path.exists():
        path.write_text(text, encoding="utf-8")


def validate(workbook=WORKBOOK, generations=GENERATIONS):
    rows = load_benchmark(workbook, 756)
    generated = [Generation.model_validate(r) for r in read_records(generations)]
    joined = join_generations(rows, generated, models=("llama",))
    checks = {
        "756_generation_records": len(generated) == 756,
        "exact_id_match": {r.question_id for r in rows} == {g.question_id for g in generated},
        "756_nonempty_answers": all(ready for *_, ready in joined),
        "excel_jsonl_answers_identical": all(
            r.model_extra.get("llama_answer") == g.answer for r, _, g, _ in joined
        ),
        "language_distribution": Counter(r.language for r in rows) == {"en": 404, "fr": 352},
        "1814_metric_evaluations": workload(joined)["metric_evaluations"] == 1814,
    }
    if not all(checks.values()):
        raise ValueError(
            "HPC validation failed: " + ", ".join(k for k, v in checks.items() if not v)
        )
    manifest = dict(
        status="VALID",
        timestamp=now(),
        checks=checks,
        files={
            str(p.relative_to(ROOT)): {"sha256": file_hash(p)}
            for p in (Path(workbook), Path(generations))
        },
        questions=len(rows),
        unique_question_ids=len({r.question_id for r in rows}),
        nonempty_llama_answers=len(generated),
        languages=dict(Counter(r.language for r in rows)),
        primary_assignments=len(rows),
        secondary_assignments=sum(len(r.applicable_metrics) - 1 for r in rows),
        metric_evaluations=workload(joined)["metric_evaluations"],
        per_metric=dict(sorted(Counter(m for r in rows for m in r.applicable_metrics).items())),
        per_primary_metric=dict(sorted(Counter(r.primary_metric for r in rows).items())),
        generation_metadata_fields=sorted(set().union(*(g.model_extra.keys() for g in generated))),
        generation_metadata_note="No model checkpoint revision, inference settings, prompt template or token counts supplied. Not invented.",
        comparison_scope="Excel/JSONL comparison; no separate final benchmark artifact supplied for independent text comparison.",
    )
    write_json(INCOMING / "Canadian-ness_Llama_Validation_Manifest.json", manifest)
    return rows, joined, manifest


def select_pilot(rows):
    chosen = []
    for mid in (f"M{i}" for i in range(1, 8)):
        for language in ("en", "fr"):
            candidates = [r for r in rows if r.primary_metric == mid and r.language == language]
            if mid == "M6":
                target = "CA-EXP-037" if language == "en" else "CA-EXP2-059"
                row = next(r for r in candidates if r.question_id == target)
            else:
                row = min(
                    candidates,
                    key=lambda r: (len(r.applicable_metrics), len(r.model_extra["llama_answer"])),
                )
            chosen.append(row)
    return chosen


def prepare():
    rows, joined, validation = validate()
    config = load_final()
    if (
        file_hash(FINAL_JSON) != EXPECTED_RUBRIC_HASH
        or file_hash(SOURCE_JSON) != EXPECTED_RUBRIC_HASH
    ):
        raise ValueError("Selected rubric checksum changed; review artifact before judging")
    cases = []
    for row, model, generation, ready in joined:
        if not ready:
            raise ValueError("Cannot prepare missing answer")
        secondary = [m for m in row.applicable_metrics if m != row.primary_metric]
        # Import the explicit user-supplied verified-benchmark attestation. Do not invent
        # a source URL or pretend this is newly verified against external sources.
        case = CalibrationCase(
            question_id=row.question_id,
            question=row.question,
            model_answer=generation.answer,
            reference_answer=row.reference_answer,
            reference_context=[row.context_text],
            applicable_metrics=[row.primary_metric, *secondary],
            primary_metric=row.primary_metric,
            secondary_metrics=secondary,
            model_variant=model,
            language=row.language,
            provenance="HPC export; text/answer preserved; benchmark evidence user-attested",
            illustrative=False,
            dataset_version="llama-core-756-" + file_hash(WORKBOOK)[:12],
            case_family="CORE",
            synthetic=False,
            development_example=False,
            expected_behavior="No synthetic target score; apply only the supplied fixed metric.",
            evidence_review=EvidenceReview(
                status="verified",
                reference_answer_verified=True,
                sufficient_for_metrics=row.applicable_metrics,
                verified_by="User-supplied benchmark attestation (not local independent verification)",
                verification_date="2026-11-06 (attestation imported; original verification date unspecified)",
                source_ids=[f"benchmark-sha256:{file_hash(WORKBOOK)}:question:{row.question_id}"],
                note=EVIDENCE_ATTESTATION,
            ),
        )
        cases.append(case)
    pilot_ids = {r.question_id for r in select_pilot(rows)}
    pilot = [c for c in cases if c.question_id in pilot_ids]
    PREPARED.mkdir(parents=True, exist_ok=True)
    save_jsonl(PREPARED / "all_cases.jsonl", [c.model_dump() for c in cases])
    save_jsonl(PREPARED / "pilot_cases.jsonl", [c.model_dump() for c in pilot])
    tasks = [
        dict(
            question_id=c.question_id,
            evaluated_model=c.model_variant,
            language=c.language,
            evaluation_metric=mid,
            primary_metric=c.primary_metric,
            metric_role="primary" if mid == c.primary_metric else "secondary",
            rubric_version=config.version,
            rubric_sha256=EXPECTED_RUBRIC_HASH,
            provisional=True,
            status="PLANNED_NOT_EXECUTED",
        )
        for c in cases
        for mid in c.applicable_metrics
    ]
    save_jsonl(PREPARED / "full_run_plan.jsonl", tasks)
    metadata = dict(
        phase="PILOT_PROVISIONAL",
        rubric_artifact=str(FINAL_JSON.relative_to(ROOT)),
        rubric_sha256=EXPECTED_RUBRIC_HASH,
        rubric_status=config.status,
        source_files=validation["files"],
        evidence_attestation=EVIDENCE_ATTESTATION,
        selection_policy="One primary assignment per metric/language; least metric count then shortest answer, except M6 explicit EN canal/FR booster-seat uncertainty cases. All applicable labels retained.",
        full_run_execution_enabled=False,
        approval_gates=[
            "Review real pilot results with user",
            "Existing frozen production rubric approval gate remains unchanged",
        ],
        packages=versions(),
    )
    write_json(
        PREPARED / "preparation.json",
        dict(
            **metadata,
            question_count=len(cases),
            metric_evaluations=len(tasks),
            pilot_question_ids=[c.question_id for c in pilot],
            pilot_evaluations=sum(len(c.applicable_metrics) for c in pilot),
        ),
    )
    return pilot, metadata


def audit_requests(directory, cases, config):
    """Check saved real payloads against exact inputs, fixed steps/bands and expected schemas."""
    case_index = {c.question_id: c for c in cases}
    definitions = {m.metric_id: m for m in config.metrics}
    checks = []
    for row in read_results(directory):
        if not row["applicable"]:
            continue
        case, definition = case_index[row["question_id"]], definitions[row["metric_id"]]
        item = dict(question_id=case.question_id, evaluation_metric=definition.metric_id, checks={})
        raw_path = row.get("raw_output_file")
        responses = (
            json.loads((Path(directory) / raw_path).read_text(encoding="utf-8"))["responses"]
            if raw_path
            else []
        )
        bodies = [r["request_body"] for r in responses if "request_body" in r]
        item["request_count"] = len(responses)
        item["checks"]["has_request"] = bool(bodies)
        for body in bodies:
            prompt = body["messages"][0]["content"]
            flags = {
                "question_preserved": case.question in prompt,
                "answer_preserved": case.model_answer in prompt,
                "fixed_steps": all(step in prompt for step in definition.evaluation_steps),
                "fixed_rubric": all(
                    b.expected_outcome in prompt for b in definition.rubric_0_to_10
                ),
                "scope": definition.criteria in prompt and definition.scope_exclusions in prompt,
                "scoring_not_step_generation": set(
                    body.get("response_format", {})
                    .get("json_schema", {})
                    .get("schema", {})
                    .get("properties", {})
                )
                == {"score", "reason"},
                "correct_model": body["model"] == row["judge_model"],
                "summary_not_verbatim": "not necessarily a verbatim quotation" in prompt,
            }
            if "CONTEXT" in definition.required_evaluation_params:
                flags["reference_included"] = case.reference_answer in prompt
                # DeepEval renders list-valued context with Python string escaping.
                flags["context_included"] = (
                    case.reference_context[0] in prompt
                    or repr(case.reference_context)[1:-1] in prompt
                )
            else:
                flags["evidence_excluded"] = all(
                    text in case.question or text in case.model_answer or text not in prompt
                    for text in [case.reference_answer, case.reference_context[0]]
                )
            for key, value in flags.items():
                item["checks"][key] = item["checks"].get(key, True) and value
        item["passed"] = all(item["checks"].values())
        checks.append(item)
    report = dict(
        passed=bool(checks) and all(c["passed"] for c in checks),
        checks=checks,
        method="Exact strings/escaped context checked in checkpointed HTTP request bodies; response schemas must be score/reason, never steps.",
    )
    write_json(Path(directory) / "request_audit.json", report)
    return report


def export_reports(directory, statistics_filename="pilot_statistics.json"):
    directory = Path(directory)
    rows = [r for r in read_results(directory) if r["applicable"]]
    records = [
        dict(
            question_id=r["question_id"],
            evaluated_model=r["evaluated_model"],
            language=r["language"],
            primary_metric=r["primary_metric"],
            evaluation_metric=r["metric_id"],
            metric_role=r["metric_role"],
            score=r["score"],
            judge_reason=r["reason"],
            judge_model=r["judge_model"],
            rubric_version=r["rubric_version"],
            rubric_sha256=r["metric_json_sha256"],
            evaluation_steps_version=r["evaluation_steps_version"],
            judge_configuration=r["judge_configuration"],
            evaluation_run_id=r["evaluation_run_id"],
            evaluation_timestamp=r["timestamp"],
            status=r["status"],
            provisional=True,
            attempt=r["attempt"],
            error_message=r["error"],
            raw_output_file=r["raw_output_file"],
            request_attempts=r["request_attempts"],
            latency_seconds=r["latency_seconds"],
        )
        for r in rows
    ]
    # Derived exports may be rebuilt from immutable individual checkpoints.
    (directory / "question_scores.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8"
    )
    with (directory / "question_scores.csv").open("w", encoding="utf-8-sig", newline="") as f:
        if records:
            writer = csv.DictWriter(f, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    summaries = []
    for dims in [
        ("evaluated_model", "evaluation_metric"),
        ("evaluated_model", "evaluation_metric", "language"),
        ("evaluated_model", "evaluation_metric", "metric_role"),
        ("evaluated_model", "evaluation_metric", "language", "metric_role"),
    ]:
        groups = defaultdict(list)
        for row in records:
            groups[tuple(row[k] for k in dims)].append(row)
        for key, group in sorted(groups.items()):
            scores = [r["score"] for r in group if r["status"] == "SUCCESS"]
            summaries.append(
                dict(
                    grouping="/".join(dims),
                    **dict(zip(dims, key)),
                    count=len(group),
                    scored=len(scores),
                    failed=sum(r["status"] == "FAILED" for r in group),
                    mean=statistics.mean(scores) if scores else None,
                    median=statistics.median(scores) if scores else None,
                    provisional=True,
                )
            )
    write_json(directory / "metric_summaries.json", summaries)
    fields = [
        "grouping",
        "evaluated_model",
        "evaluation_metric",
        "language",
        "metric_role",
        "count",
        "scored",
        "failed",
        "mean",
        "median",
        "provisional",
    ]
    with (directory / "metric_summaries.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summaries)
    success = [r for r in records if r["status"] == "SUCCESS"]
    all_attempts = [
        json.loads(p.read_text(encoding="utf-8")) for p in (directory / "records").glob("*.json")
    ]
    all_attempts = [r for r in all_attempts if r["applicable"]]
    latencies = [r["latency_seconds"] for r in all_attempts if r["request_attempts"]]
    mean_latency = statistics.mean(latencies) if latencies else None
    stats = dict(
        evaluations=len(records),
        successes=len(success),
        errors=sum(r["status"] == "FAILED" for r in records),
        error_rate=sum(r["status"] == "FAILED" for r in records) / len(records)
        if records
        else None,
        scoring_http_attempts=sum(r["request_attempts"] for r in all_attempts),
        saved_evaluation_attempts=len(all_attempts),
        failed_evaluation_attempts=sum(r["status"] == "FAILED" for r in all_attempts),
        mean_evaluation_latency_seconds=mean_latency,
        median_evaluation_latency_seconds=statistics.median(latencies) if latencies else None,
        min_evaluation_latency_seconds=min(latencies) if latencies else None,
        max_evaluation_latency_seconds=max(latencies) if latencies else None,
        projected_sequential_seconds_1814=1814 * mean_latency if mean_latency else None,
        projection_note="Pilot sample conditional on current gateway load and short selected answers; not measured full-run throughput. No arbitrary overall score.",
        provisional=True,
    )
    write_json(directory / statistics_filename, stats)
    return stats


def write_review_workbook(directory, case_path=PREPARED / "pilot_cases.jsonl"):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font

    from .calibration.schema import load_cases

    directory = Path(directory)
    cases = {c.question_id: c for c in load_cases(case_path)}
    records = read_records(directory / "question_scores.jsonl")
    book = Workbook()
    sheet = book.active
    sheet.title = "Individual scores"
    extra = [
        "question",
        "llama_answer",
        "reference_answer",
        "context_supporting_summary",
        "human_review_notes",
        "human_score",
    ]
    columns = list(records[0]) + extra
    sheet.append(columns)
    for row in records:
        case = cases[row["question_id"]]
        values = dict(
            row,
            question=case.question,
            llama_answer=case.model_answer,
            reference_answer=case.reference_answer,
            context_supporting_summary=case.reference_context[0],
            human_review_notes=None,
            human_score=None,
        )
        sheet.append(
            [
                json.dumps(values[k], ensure_ascii=False)
                if isinstance(values[k], dict)
                else values[k]
                for k in columns
            ]
        )
    summaries = json.loads((directory / "metric_summaries.json").read_text(encoding="utf-8"))
    summary_sheet = book.create_sheet("Metric language role summaries")
    summary_columns = list(dict.fromkeys(k for row in summaries for k in row))
    summary_sheet.append(summary_columns)
    for row in summaries:
        summary_sheet.append([row.get(k) for k in summary_columns])
    rubrics = book.create_sheet("Fixed steps and rubrics")
    rubrics.append(["metric_id", "kind", "step_or_band", "verbatim_definition"])
    for metric in load_final().metrics:
        for i, step in enumerate(metric.evaluation_steps, 1):
            rubrics.append([metric.metric_id, "fixed_step", i, step])
        for band in metric.rubric_0_to_10:
            rubrics.append(
                [
                    metric.metric_id,
                    "rubric_0_to_10",
                    f"{band.min}-{band.max}",
                    band.expected_outcome,
                ]
            )
    for tab in book:
        tab.freeze_panes = "A2"
        tab.auto_filter.ref = tab.dimensions
        for cell in tab[1]:
            cell.font = Font(bold=True)
        for row in tab:
            for cell in row:
                if isinstance(cell.value, str):
                    cell.data_type = (
                        "s"  # Preserve answer text literally, including formula prefixes.
                    )
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        for column in tab.columns:
            tab.column_dimensions[column[0].column_letter].width = 25
    book.save(directory / "pilot_review.xlsx")


def pilot(*, resume=False, retry_failures=False, directory=RUN):
    from .api_client import Gateway
    from .judge_adapter import RemoteJudge

    cases, metadata = prepare()
    gateway = Gateway(Settings.load())
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    try:
        gateway.discover()
        start_attempts = gateway.attempts
        evaluate_hpc_pilot(
            PREPARED / "pilot_cases.jsonl",
            RemoteJudge(gateway),
            directory,
            config_path=FINAL_JSON,
            run_metadata=metadata,
            resume=resume,
            retry_failures=retry_failures,
        )
        scored_after = gateway.attempts - start_attempts
        before = {p.name: file_hash(p) for p in (directory / "records").glob("*.json")}
        # Real no-op resume verifies the same engine does not issue duplicate judge calls.
        evaluate_hpc_pilot(
            PREPARED / "pilot_cases.jsonl",
            RemoteJudge(gateway),
            directory,
            config_path=FINAL_JSON,
            run_metadata=metadata,
            resume=True,
        )
        after = {p.name: file_hash(p) for p in (directory / "records").glob("*.json")}
        write_json(
            directory / "resume_check.json",
            dict(
                passed=before == after and gateway.attempts - start_attempts == scored_after,
                checkpoint_files_unchanged=before == after,
                extra_http_attempts=gateway.attempts - start_attempts - scored_after,
            ),
        )
        audit = audit_requests(directory, cases, load_final())
        stats = export_reports(directory)
        write_review_workbook(directory)
        passed = (
            audit["passed"]
            and before == after
            and stats["successes"] == 22
            and stats["errors"] == 0
            and gateway.attempts - start_attempts == scored_after
        )
        write_json(
            directory / "pilot_acceptance.json",
            dict(
                passed=passed,
                provisional=True,
                full_run_started=False,
                full_run_requires_user_review=True,
                approval_gate_unchanged=True,
                session_http_attempts=gateway.attempts,
                session_scoring_http_attempts=scored_after,
                discovery_http_attempts=start_attempts,
            ),
        )
        print(json.dumps(dict(passed=passed, **stats), indent=2))
        return 0 if passed else 1
    finally:
        gateway.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "pilot", "report"])
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--retry-failures", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        cases, _ = prepare()
        print(f"Prepared {len(cases)} pilot questions; full run planned only.")
        return 0
    if args.command == "report":
        print(json.dumps(export_reports(RUN), indent=2))
        write_review_workbook(RUN)
        return 0
    return pilot(resume=args.resume, retry_failures=args.retry_failures)


if __name__ == "__main__":
    raise SystemExit(main())
