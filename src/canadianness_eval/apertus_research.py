"""Immutable as-generated Apertus intake and full-run comparison exports."""

import argparse
import json
import statistics
from collections import Counter, defaultdict

from openpyxl import load_workbook

from .calibration.schema import CalibrationCase, load_cases
from .final_metrics import file_hash
from .gc_as_generated import repetition_indicator, unique_index
from .hpc_ingestion import load_benchmark, read_records
from .hpc_workflow import save_jsonl
from .research_exports import add_sheet, table
from .research_run import LABEL, confirmation, exclusive, verify_plan
from .research_run import prepare as prepare_research
from .settings import ROOT
from .storage import write_json

RUN_ID = "apertus_full_as_generated_c4_20261107_v2"
PLAN = ROOT / "config/research" / RUN_ID / "experiment.json"
APPROVAL = PLAN.parent / "execution_approval.json"
PROCESSED = ROOT / "data/processed/apertus_as_generated_v2"
INCOMING = ROOT / "data/incoming/apertus_as_generated"


def prepare():
    INCOMING.mkdir(parents=True, exist_ok=True)
    for suffix in ["jsonl", "xlsx"]:
        name = f"apertus_756_evaluation_1024_tokens.{suffix}"
        source, dest = ROOT / name, INCOMING / name
        if dest.exists() and file_hash(dest) != file_hash(source):
            raise ValueError("Apertus source copy changed")
        if not dest.exists():
            dest.write_bytes(source.read_bytes())
    original_path = INCOMING / "apertus_756_evaluation_1024_tokens.jsonl"
    workbook = INCOMING / "apertus_756_evaluation_1024_tokens.xlsx"
    original_hash = file_hash(original_path)
    raw = unique_index(read_records(original_path), "Apertus original JSONL")
    excel = {r.question_id: r for r in load_benchmark(workbook, 756)}
    base = {
        c.question_id: c for c in load_cases(ROOT / "data/processed/llama_756_v1/all_cases.jsonl")
    }
    if not set(raw) == set(excel) == set(base):
        raise ValueError("Apertus IDs differ from benchmark")
    cases, generated, metadata = [], [], []
    for qid, r in raw.items():
        answer = r["apertus_answer"]
        if (
            not isinstance(answer, str)
            or not answer.strip()
            or excel[qid].model_extra["apertus_answer"] != answer
        ):
            raise ValueError("Invalid or mismatched Apertus response: " + qid)
        for k in ["question", "reference_answer", "language", "primary_metric"]:
            if r[k] != getattr(base[qid], k) or r[k] != getattr(excel[qid], k):
                raise ValueError("Benchmark mismatch: " + qid + "/" + k)
        if (
            base[qid].reference_context != [r["context_text"]]
            or excel[qid].context_text != r["context_text"]
        ):
            raise ValueError("Context mismatch: " + qid)
        labels = {m.strip() for m in r["applicable_metrics"].replace(";", ",").split(",")}
        if labels != set(base[qid].applicable_metrics) or labels != set(
            excel[qid].applicable_metrics
        ):
            raise ValueError("Metric applicability mismatch: " + qid)
        meta = {"question_id": qid}
        for k in [
            "truncated",
            "response_complete",
            "output_tokens",
            "finish_reason",
            "max_new_tokens",
            "model_id",
            "model_revision",
            "run_id",
        ]:
            if r[k] != excel[qid].model_extra[k]:
                raise ValueError("Generation metadata mismatch: " + qid + "/" + k)
            meta[k] = r[k]
        if (
            r["finish_reason"] not in ["length", "stop"]
            or r["truncated"] != (r["finish_reason"] == "length")
            or r["response_complete"] != (not r["truncated"])
        ):
            raise ValueError("Conflicting generation termination flags")
        meta.update(repetition_indicator(answer))
        values = base[qid].model_dump()
        values.update(
            model_variant="apertus",
            model_answer=answer,
            dataset_version="apertus-as-generated-" + original_hash[:12],
            provenance="Original Apertus JSONL/XLSX; full response unchanged; generation metadata in frozen sidecar",
        )
        cases.append(CalibrationCase.model_validate(values))
        generated.append(
            dict(question_id=qid, evaluated_model="apertus", answer=answer, status="success")
        )
        metadata.append(meta)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    cases_path = PROCESSED / "all_cases.jsonl"
    generations = PROCESSED / "generations.jsonl"
    sidecar = PROCESSED / "generation_metadata.jsonl"
    save_jsonl(cases_path, [c.model_dump() for c in cases])
    save_jsonl(generations, generated)
    save_jsonl(sidecar, metadata)
    if PLAN.exists():
        return verify_plan(PLAN)
    draft = prepare_research(
        PROCESSED / "preparation_draft/experiment.json",
        run_id=RUN_ID,
        model="apertus",
        cases_path=cases_path,
        generations_path=generations,
        workbook_path=workbook,
    )
    defaults_path = ROOT / "config/evaluator/execution_defaults.json"
    defaults = json.loads(defaults_path.read_text(encoding="utf8"))
    if defaults["default_concurrency"] != 4:
        raise ValueError("User-selected default concurrency changed")
    draft["judge"]["concurrency"] = 4
    draft["execution_engine"] = "concurrent-research-v1"
    draft["execution_profile"] = dict(
        workers=4,
        scheduling_unit="question",
        checkpoint_unit="individual metric",
        scorer="unchanged evaluate_calibration in isolated durable question shards",
        shared_retry_cooldown=True,
        coordinator_serialized_publication=True,
    )
    draft["policy_basis"] = (
        "Explicit user instruction: I have added the apertus evalaution dataset, run it for me with the new concurrency settings. Execution only; no scientific/team approval."
    )
    for path in [original_path, sidecar, defaults_path]:
        draft["input_sha256"][path.relative_to(ROOT).as_posix()] = file_hash(path)
    for name in ["concurrent_research.py", "apertus_research.py", "gc_as_generated.py"]:
        path = ROOT / "src/canadianness_eval" / name
        draft["software_sha256"][path.relative_to(ROOT).as_posix()] = file_hash(path)
    for run in ["llama_full_20261106_v2", "gc_llm_full_as_generated_20261106_v2"]:
        for path in (ROOT / "outputs/evaluations" / run).rglob("*"):
            if path.is_file() and path.suffix != ".tmp" and not path.name.startswith("~$"):
                draft["protected_pilot_sha256"][path.relative_to(ROOT).as_posix()] = file_hash(path)
    draft["as_generated_contract"] = dict(
        all_responses_retained=True,
        source_jsonl_sha256=original_hash,
        source_metadata_sidecar=sidecar.relative_to(ROOT).as_posix(),
        responses_regenerated=False,
        responses_cleaned=False,
        special_scoring_instructions=False,
        termination_questions=dict(Counter(r["finish_reason"] for r in metadata)),
        generation_run_ids=sorted({r["run_id"] for r in metadata}),
        model_revisions=sorted({r["model_revision"] for r in metadata}),
        max_new_tokens=sorted({r["max_new_tokens"] for r in metadata}),
        repetition_flags="Derived exploratory 4-gram heuristic; analysis only",
    )
    draft["missing_generation_metadata"] = (
        "Temperature, sampling controls, seed and prompt template not supplied. Llama revision/inference settings unavailable. Apertus uses four workers versus previous sequential runs; request scoring protocol unchanged, but timing/load/cache conditions differ."
    )
    exclusive(PLAN, draft)
    exclusive(
        PLAN.parent / "approval_request.json",
        dict(
            status="PENDING_EXECUTION_AUTHORIZATION",
            run_id=RUN_ID,
            experiment_sha256=file_hash(PLAN),
            required_confirmation=confirmation(draft),
            execution_authorized=False,
            scientific_validity_approved=False,
            team_approval=False,
            rubric_empirically_calibrated=False,
        ),
    )
    write_json(
        PROCESSED / "validation_manifest.json",
        dict(
            status="VALID",
            questions=756,
            unique_questions=756,
            nonempty_unchanged_answers=756,
            excel_jsonl_answers_identical=True,
            metric_tasks=1814,
            primary=756,
            secondary=1058,
            language_questions=dict(Counter(c.language for c in cases)),
            termination_questions=dict(Counter(r["finish_reason"] for r in metadata)),
            source_jsonl_sha256=original_hash,
            experiment_sha256=file_hash(PLAN),
        ),
    )
    return verify_plan(PLAN)


def analyse():
    plan = verify_plan(PLAN)
    directory = ROOT / plan["run_directory"]
    rows = read_records(directory / "all_results.jsonl")
    if len(rows) != 1814 or any(r["status"] != "SUCCESS" for r in rows):
        raise ValueError("Complete results required for final analysis")
    meta = {r["question_id"]: r for r in read_records(PROCESSED / "generation_metadata.jsonl")}
    raw = {
        r["question_id"]: r
        for r in read_records(INCOMING / "apertus_756_evaluation_1024_tokens.jsonl")
    }
    enriched = []
    for r in rows:
        assert r["model_answer"] == raw[r["question_id"]]["apertus_answer"]
        enriched.append(
            dict(
                r,
                generation_metadata=meta[r["question_id"]],
                truncated=meta[r["question_id"]]["truncated"],
                response_complete=meta[r["question_id"]]["response_complete"],
                finish_reason=meta[r["question_id"]]["finish_reason"],
                generation_run_id=meta[r["question_id"]]["run_id"],
                model_revision=meta[r["question_id"]]["model_revision"],
                analysis_repetition_flag=meta[r["question_id"]]["analysis_repetition_flag"],
            )
        )
    table(directory / "as_generated_results", enriched)
    subgroups = []
    for axis in ["truncated", "response_complete", "analysis_repetition_flag"]:
        grouped = defaultdict(list)
        for r in enriched:
            grouped[(r["evaluation_metric"], r[axis])].append(r)
        for (metric, value), group in sorted(grouped.items()):
            subgroups.append(
                dict(
                    evaluation_metric=metric,
                    grouping=axis,
                    group_value=value,
                    tasks=len(group),
                    mean=statistics.mean(r["score"] for r in group),
                    result_label=LABEL,
                )
            )
    table(directory / "completion_repetition_subgroups", subgroups)
    pairs = []
    for model, run in [
        ("llama", "llama_full_20261106_v2"),
        ("gc_llm", "gc_llm_full_as_generated_20261106_v2"),
    ]:
        prior = {
            (r["question_id"], r["evaluation_metric"]): r
            for r in read_records(ROOT / "outputs/evaluations" / run / "all_results.jsonl")
        }
        for r in enriched:
            old = prior[r["question_id"], r["evaluation_metric"]]
            for k in [
                "question",
                "reference_answer",
                "context_supporting_summary",
                "metric_role",
                "language",
                "rubric_sha256",
                "evaluator_template_sha256",
            ]:
                if old[k] != r[k]:
                    raise ValueError("Comparison mismatch: " + k)
            pairs.append(
                dict(
                    question_id=r["question_id"],
                    evaluation_metric=r["evaluation_metric"],
                    language=r["language"],
                    metric_role=r["metric_role"],
                    comparison_model=model,
                    apertus_score=r["score"],
                    comparison_score=old["score"],
                    apertus_minus_comparison=r["score"] - old["score"],
                    apertus_answer=r["model_answer"],
                    comparison_answer=old["model_answer"],
                    apertus_reason=r["judge_reason"],
                    comparison_reason=old["judge_reason"],
                    question=r["question"],
                    reference_answer=r["reference_answer"],
                    context_supporting_summary=r["context_supporting_summary"],
                    result_label=LABEL,
                )
            )
    table(directory / "apertus_model_comparison_pairs", pairs)
    summaries = []
    for axes in [(), ("language",), ("metric_role",)]:
        grouped = defaultdict(list)
        for r in pairs:
            grouped[(r["comparison_model"], r["evaluation_metric"], *(r[k] for k in axes))].append(
                r
            )
        for key, group in sorted(grouped.items()):
            summaries.append(
                dict(
                    comparison_model=key[0],
                    evaluation_metric=key[1],
                    grouping="/".join(axes) or "metric",
                    **dict(zip(axes, key[2:])),
                    pairs=len(group),
                    apertus_mean=statistics.mean(r["apertus_score"] for r in group),
                    comparison_mean=statistics.mean(r["comparison_score"] for r in group),
                    mean_difference=statistics.mean(r["apertus_minus_comparison"] for r in group),
                    result_label=LABEL,
                )
            )
    table(directory / "apertus_model_comparison_summaries", summaries)
    book = load_workbook(directory / "full_results.xlsx")
    for title, values in [
        ("Generation metadata", list(meta.values())),
        ("Apertus original outputs", enriched),
        ("Completion repetition groups", subgroups),
        ("Model comparison pairs", pairs),
        ("Model comparison summaries", summaries),
    ]:
        add_sheet(book, title, values)
    book.save(directory / "as_generated_comparison.xlsx")
    return enriched, summaries, subgroups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "analyse"])
    args = parser.parse_args()
    if args.command == "prepare":
        plan = prepare()
        print(plan["run_id"], plan["task_count"], file_hash(PLAN), flush=True)
    else:
        rows, _, _ = analyse()
        print("Analysed", len(rows), "Apertus evaluations", flush=True)


if __name__ == "__main__":
    main()
