"""Additive, authorized cleaned-response queue; never changes active frozen runs."""

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter

from .calibration.evaluate import read_results
from .calibration.schema import CalibrationCase, load_cases
from .final_metrics import file_hash
from .gc_as_generated import repetition_indicator
from .hpc_ingestion import read_records
from .hpc_workflow import save_jsonl
from .queued_workbook import MODELS, workbook_rows
from .queued_workbook import QUEUE as PARENT_QUEUE
from .queued_workbook import STATE as PARENT_STATE
from .queued_workbook import run_id as parent_run_id
from .queued_workbook import validate_queue as validate_parent
from .research_exports import LABEL, add_sheet, table
from .research_run import authorize, confirmation, exclusive, require_approval, verify_plan
from .research_run import prepare as prepare_research
from .settings import ROOT
from .storage import now, write_json
from .verification.db import process_lock

SOURCE = ROOT / "Canadian_ness_Three_Models_Cleaned_for_Evaluation.jsonl"
QUEUE = ROOT / "config/research/cleaned_three_model_queue_v1"
STATE = ROOT / "outputs/queues/cleaned_three_model_queue_v1"
INTERVAL = 600


def run_id(model):
    return f"{model}_cleaned_responses_c4_20261107_v2"


def event(kind, **values):
    STATE.mkdir(parents=True, exist_ok=True)
    row = dict(timestamp=now(), queue_id=QUEUE.name, event=kind, **values)
    for directory in [STATE, PARENT_STATE]:
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "supervision.jsonl").open("a", encoding="utf8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(row, ensure_ascii=False), flush=True)


def digest_answer(answer):
    return hashlib.sha256(answer.encode("utf8")).hexdigest()


def initialize():
    parent = validate_parent()
    source_rows = read_records(SOURCE)
    if len(source_rows) != 756 or len({r["question_id"] for r in source_rows}) != 756:
        raise ValueError("Cleaned source requires 756 unique questions")
    base = {
        c.question_id: c for c in load_cases(ROOT / "data/processed/llama_756_v1/all_cases.jsonl")
    }
    original = {r["question_id"]: r for r in workbook_rows(ROOT / parent["source_workbook"])[0]}
    if {r["question_id"] for r in source_rows} != set(base):
        raise ValueError("Question IDs differ")
    changed = {m: 0 for m in MODELS}
    for r in source_rows:
        c = base[r["question_id"]]
        for key in ["question", "reference_answer", "language", "primary_metric"]:
            if r[key] != getattr(c, key):
                raise ValueError("Benchmark mismatch: " + key)
        if [r["context_text"]] != c.reference_context:
            raise ValueError("Context mismatch")
        if {m.strip() for m in r["applicable_metrics"].split(",")} != set(c.applicable_metrics):
            raise ValueError("Metric assignments differ")
        for m in MODELS:
            if not isinstance(r[m + "_answer"], str) or not r[m + "_answer"].strip():
                raise ValueError("Missing answer")
            changed[m] += r[m + "_answer"] != original[r["question_id"]][m + "_answer"]
    intake = ROOT / "data/incoming/cleaned_three_model"
    intake.mkdir(parents=True, exist_ok=True)
    copied = intake / SOURCE.name
    if copied.exists() and file_hash(copied) != file_hash(SOURCE):
        raise ValueError("Source copy changed")
    if not copied.exists():
        copied.write_bytes(SOURCE.read_bytes())
    workbook = intake / "cleaned_source_ingestion.xlsx"
    if not workbook.exists():
        book = Workbook()
        sheet = book.active
        sheet.title = "Evaluation Dataset"
        keys = list(source_rows[0])
        sheet.append(keys)
        for r in source_rows:
            sheet.append([r[k] for k in keys])
        for cells in sheet:
            for cell in cells:
                if isinstance(cell.value, str):
                    cell.data_type = "s"
        book.save(workbook)
    book = load_workbook(workbook, read_only=True, data_only=True)
    it = book.active.iter_rows(values_only=True)
    keys = next(it)
    converted = [dict(zip(keys, r)) for r in it]
    book.close()
    if converted != source_rows:
        # Excel XML must entity-encode CR to preserve source CRLF literally.
        # This changes only the derived ingestion container, never response strings.
        xml = [
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
        ]
        for number, values in enumerate(
            [list(source_rows[0])] + [list(r.values()) for r in source_rows], 1
        ):
            xml.append(f'<row r="{number}">')
            for column, value in enumerate(values, 1):
                text = escape(value).replace("\r", "&#13;")
                cell = f"{get_column_letter(column)}{number}"
                xml.append(
                    f'<c r="{cell}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'
                )
            xml.append("</row>")
        xml.append("</sheetData></worksheet>")
        repaired = workbook.with_suffix(".repair.xlsx")
        with ZipFile(workbook) as original, ZipFile(repaired, "w", ZIP_DEFLATED) as replacement:
            for info in original.infolist():
                data = (
                    "".join(xml).encode("utf8")
                    if info.filename == "xl/worksheets/sheet1.xml"
                    else original.read(info.filename)
                )
                replacement.writestr(info, data)
        repaired.replace(workbook)
        book = load_workbook(workbook, read_only=True, data_only=True)
        it = book.active.iter_rows(values_only=True)
        keys = next(it)
        converted = [dict(zip(keys, r)) for r in it]
        book.close()
        if converted != source_rows:
            raise ValueError("Derived ingestion workbook changes source content")
    manifest = dict(
        queue_id=QUEUE.name,
        append_after_queue_manifest_sha256=file_hash(PARENT_QUEUE / "queue.json"),
        append_after_completion=str((PARENT_STATE / "completion.json").relative_to(ROOT)),
        source_jsonl=copied.relative_to(ROOT).as_posix(),
        source_jsonl_sha256=file_hash(copied),
        ingestion_workbook=workbook.relative_to(ROOT).as_posix(),
        ingestion_workbook_sha256=file_hash(workbook),
        order=MODELS,
        run_ids=[run_id(m) for m in MODELS],
        questions_per_model=756,
        metric_tasks_per_model=1814,
        total_metric_tasks=5442,
        combined_six_run_metric_tasks=10884,
        concurrency=4,
        monitor_interval_seconds=600,
        changed_answers_versus_parent_workbook=changed,
        source_generation_metadata="Not supplied in cleaned JSONL; not inferred",
        interpretation="User-provided edited-answer experiment; score changes do not by themselves establish judge repetition bias",
        software_sha256={},
        scientific_validity_approved=False,
        team_approval=False,
        rubric_empirically_calibrated=False,
        result_label=LABEL,
    )
    for name in ["queued_cleaned.py", "concurrent_research.py", "gc_as_generated.py"]:
        path = ROOT / "src/canadianness_eval" / name
        manifest["software_sha256"][path.relative_to(ROOT).as_posix()] = file_hash(path)
    if (QUEUE / "queue.json").exists():
        if json.loads((QUEUE / "queue.json").read_text(encoding="utf8")) != manifest:
            raise ValueError("Frozen queue differs")
    else:
        exclusive(QUEUE / "queue.json", manifest)
    if not (QUEUE / "execution_authorization.json").exists():
        exclusive(
            QUEUE / "execution_authorization.json",
            dict(
                status="EXECUTION_AUTHORIZED",
                authorized_at=now(),
                authorized_by="User: explicit request to append cleaned benchmark for all three models",
                verbatim_instruction="Can you also add this evalaution dataset to the current queue of 3 currently ongoing evaluations? Make sure there is no leakage and we get clean results from all the 6 evaluations",
                queue_manifest_sha256=file_hash(QUEUE / "queue.json"),
                execution_authorized=True,
                scope="Three full cleaned-source research runs after the original three runs, plus identical-configuration missing/failed-task recovery",
                scientific_validity_approved=False,
                team_approval=False,
                rubric_empirically_calibrated=False,
            ),
        )
    write_json(
        STATE / "validation_manifest.json",
        dict(
            status="PASS",
            questions=756,
            language_questions=dict(Counter(r["language"] for r in source_rows)),
            models=3,
            metric_tasks_per_model=1814,
            primary_per_model=756,
            secondary_per_model=1058,
            source_answers_preserved=True,
            benchmark_evidence_unchanged=True,
            changed_answers=changed,
            source_jsonl_sha256=file_hash(copied),
        ),
    )
    event(
        "CLEANED_RUNS_APPENDED", additional_runs=3, additional_tasks=5442, total_six_run_tasks=10884
    )
    return manifest


def validate_queue():
    q = json.loads((QUEUE / "queue.json").read_text(encoding="utf8"))
    a = json.loads((QUEUE / "execution_authorization.json").read_text(encoding="utf8"))
    if (
        a["status"] != "EXECUTION_AUTHORIZED"
        or a["execution_authorized"] is not True
        or a["queue_manifest_sha256"] != file_hash(QUEUE / "queue.json")
    ):
        raise ValueError("Queue authorization changed")
    if file_hash(PARENT_QUEUE / "queue.json") != q["append_after_queue_manifest_sha256"]:
        raise ValueError("Parent queue changed")
    for field in ["source_jsonl", "ingestion_workbook"]:
        if file_hash(ROOT / q[field]) != q[field + "_sha256"]:
            raise ValueError("Frozen source changed")
    for p, sha in q["software_sha256"].items():
        if file_hash(ROOT / p) != sha:
            raise ValueError("Frozen software changed: " + p)
    validate_parent()
    return q


def prepare_model(model, q):
    plan_path = ROOT / "config/research" / run_id(model) / "experiment.json"
    approval = plan_path.parent / "execution_approval.json"
    if plan_path.exists():
        return plan_path, approval, verify_plan(plan_path)
    source = read_records(ROOT / q["source_jsonl"])
    parent = validate_parent()
    original = {r["question_id"]: r for r in workbook_rows(ROOT / parent["source_workbook"])[0]}
    base = {
        c.question_id: c for c in load_cases(ROOT / "data/processed/llama_756_v1/all_cases.jsonl")
    }
    prepared = ROOT / "data/processed" / run_id(model)
    prepared.mkdir(parents=True, exist_ok=True)
    cases = []
    generations = []
    metadata = []
    for r in source:
        answer = r[model + "_answer"]
        raw = original[r["question_id"]][model + "_answer"]
        values = base[r["question_id"]].model_dump()
        values.update(
            model_variant=model,
            model_answer=answer,
            dataset_version="cleaned-source-" + q["source_jsonl_sha256"][:12],
            provenance="User-provided cleaned JSONL; selected answer string unchanged; no other model responses or earlier judgments in judge input",
        )
        cases.append(CalibrationCase.model_validate(values))
        generations.append(
            dict(
                question_id=r["question_id"], evaluated_model=model, answer=answer, status="success"
            )
        )
        metadata.append(
            dict(
                question_id=r["question_id"],
                evaluated_model=model,
                response_variant="user_provided_cleaned",
                source_jsonl_sha256=q["source_jsonl_sha256"],
                cleaned_answer_sha256=digest_answer(answer),
                comparison_workbook_answer_sha256=digest_answer(raw),
                answer_changed_versus_parent_workbook=answer != raw,
                cleaned_characters=len(answer),
                comparison_workbook_characters=len(raw),
                generation_temperature=None,
                finish_reason=None,
                truncated=None,
                model_revision=None,
                generation_metadata_status="Not supplied; comparison is an edited-answer experiment",
                **repetition_indicator(answer),
            )
        )
    cases_path = prepared / "all_cases.jsonl"
    generations_path = prepared / "generations.jsonl"
    sidecar = prepared / "cleaning_provenance.jsonl"
    save_jsonl(cases_path, [c.model_dump() for c in cases])
    save_jsonl(generations_path, generations)
    save_jsonl(sidecar, metadata)
    draft = prepare_research(
        prepared / "preparation_draft/experiment.json",
        run_id=run_id(model),
        model=model,
        cases_path=cases_path,
        generations_path=generations_path,
        workbook_path=ROOT / q["ingestion_workbook"],
    )
    draft.update(
        execution_engine="concurrent-research-v1",
        queue_manifest_sha256=file_hash(QUEUE / "queue.json"),
        queue_execution_authorization_sha256=file_hash(QUEUE / "execution_authorization.json"),
        response_variant="user_provided_cleaned",
        policy_basis="Explicit user instruction to append three full cleaned-dataset runs; execution-only permission",
        missing_generation_metadata="Generation settings, revisions, source run IDs and termination flags absent from cleaned JSONL. Do not infer from earlier responses. Cleaning effects are not automatically judge bias.",
    )
    draft["judge"]["concurrency"] = 4
    draft["software_sha256"].update(q["software_sha256"])
    for path in [
        ROOT / q["source_jsonl"],
        sidecar,
        QUEUE / "queue.json",
        QUEUE / "execution_authorization.json",
        ROOT / "config/evaluator/execution_defaults.json",
    ]:
        draft["input_sha256"][path.relative_to(ROOT).as_posix()] = file_hash(path)
    draft["as_generated_contract"] = dict(
        source_metadata_sidecar=sidecar.relative_to(ROOT).as_posix(),
        all_supplied_cleaned_responses_retained=True,
        additional_cleaning_applied=False,
        responses_regenerated=False,
        source_jsonl_sha256=q["source_jsonl_sha256"],
        comparison_queue_manifest_sha256=q["append_after_queue_manifest_sha256"],
    )
    exclusive(plan_path, draft)
    exclusive(
        plan_path.parent / "authorization_source.json",
        dict(
            queue_manifest_sha256=file_hash(QUEUE / "queue.json"),
            experiment_sha256=file_hash(plan_path),
            source="Explicit user cleaned-dataset queue instruction",
            execution_permission_only=True,
        ),
    )
    authorize(
        plan_path,
        approval,
        approved_by="User: explicit three-model cleaned JSONL queue request",
        statement=confirmation(draft),
    )
    return plan_path, approval, verify_plan(plan_path)


def status(plan):
    rows = [r for r in read_results(ROOT / plan["run_directory"]) if r["applicable"]]
    return dict(
        successful=sum(r["status"] == "SUCCESS" for r in rows),
        failed=sum(r["status"] != "SUCCESS" for r in rows),
        pending=1814 - len(rows),
    )


def enrich(model, plan):
    q = validate_queue()
    directory = ROOT / plan["run_directory"]
    rows = read_records(directory / "all_results.jsonl")
    source = {r["question_id"]: r for r in read_records(ROOT / q["source_jsonl"])}
    metadata = {
        r["question_id"]: r
        for r in read_records(ROOT / plan["as_generated_contract"]["source_metadata_sidecar"])
    }
    assert len(rows) == 1814 and all(
        r["status"] == "SUCCESS"
        and r["model_answer"] == source[r["question_id"]][model + "_answer"]
        for r in rows
    )
    enriched = [
        dict(
            r,
            cleaning_metadata=metadata[r["question_id"]],
            response_variant="user_provided_cleaned",
        )
        for r in rows
    ]
    table(directory / "cleaned_results", enriched)
    book = load_workbook(directory / "full_results.xlsx")
    add_sheet(book, "Cleaning provenance", list(metadata.values()))
    add_sheet(book, "Cleaned answers and judgments", enriched)
    book.save(directory / "cleaned_results.xlsx")
    write_json(
        directory / "completion_verification.json",
        dict(
            status="PASS",
            successful=1814,
            failed=0,
            missing=0,
            supplied_cleaned_answer_strings_unchanged=True,
            concurrency=4,
            result_label=LABEL,
            scientific_validity_approved=False,
            team_approval=False,
        ),
    )


def finalize_six():
    q = validate_queue()
    combined = []
    matched = []
    for model in MODELS:
        raw_path = ROOT / "config/research" / parent_run_id(model) / "experiment.json"
        raw_plan = verify_plan(raw_path)
        clean_path = ROOT / "config/research" / run_id(model) / "experiment.json"
        clean_plan = verify_plan(clean_path)
        raw = read_records(ROOT / raw_plan["run_directory"] / "as_generated_results.jsonl")
        clean = read_records(ROOT / clean_plan["run_directory"] / "cleaned_results.jsonl")
        indexed = {(r["question_id"], r["evaluation_metric"]): r for r in raw}
        combined.extend(dict(r, response_variant="original_workbook") for r in raw)
        combined.extend(clean)
        for r in clean:
            original = indexed[r["question_id"], r["evaluation_metric"]]
            for key in [
                "question",
                "reference_answer",
                "context_supporting_summary",
                "language",
                "metric_role",
                "rubric_sha256",
                "evaluator_template_sha256",
            ]:
                if r[key] != original[key]:
                    raise ValueError("Paired comparison differs: " + key)
            matched.append(
                dict(
                    question_id=r["question_id"],
                    evaluated_model=model,
                    evaluation_metric=r["evaluation_metric"],
                    metric_role=r["metric_role"],
                    language=r["language"],
                    answer_changed=r["cleaning_metadata"]["answer_changed_versus_parent_workbook"],
                    original_score=original["score"],
                    cleaned_score=r["score"],
                    cleaned_minus_original=r["score"] - original["score"],
                    original_answer=original["model_answer"],
                    cleaned_answer=r["model_answer"],
                    original_reason=original["judge_reason"],
                    cleaned_reason=r["judge_reason"],
                    question=r["question"],
                    reference_answer=r["reference_answer"],
                    context_supporting_summary=r["context_supporting_summary"],
                    cleaning_metadata=r["cleaning_metadata"],
                    result_label=LABEL,
                )
            )
    assert len(combined) == 10884 and len(matched) == 5442
    assert (
        len(
            {
                (
                    r["question_id"],
                    r["evaluated_model"],
                    r["evaluation_metric"],
                    r["response_variant"],
                )
                for r in combined
            }
        )
        == 10884
    )
    summaries = []
    for dims in [
        ("evaluated_model", "evaluation_metric"),
        ("evaluated_model", "evaluation_metric", "answer_changed"),
        ("evaluated_model", "evaluation_metric", "language"),
        ("evaluated_model", "evaluation_metric", "metric_role"),
    ]:
        groups = defaultdict(list)
        for r in matched:
            groups[tuple(r[k] for k in dims)].append(r)
        for key, values in sorted(groups.items()):
            summaries.append(
                dict(
                    zip(dims, key),
                    grouping="/".join(dims),
                    pairs=len(values),
                    original_mean=statistics.mean(r["original_score"] for r in values),
                    cleaned_mean=statistics.mean(r["cleaned_score"] for r in values),
                    mean_paired_change=statistics.mean(r["cleaned_minus_original"] for r in values),
                    score_changed_count=sum(r["cleaned_minus_original"] != 0 for r in values),
                    result_label=LABEL,
                )
            )
    directory = STATE / "final_results"
    directory.mkdir(exist_ok=True)
    table(directory / "all_six_run_results", combined)
    table(directory / "original_vs_cleaned_metric_pairs", matched)
    table(directory / "original_vs_cleaned_summaries", summaries)
    book = Workbook()
    book.remove(book.active)
    for title, values in [
        ("All six run judgments", combined),
        ("Original vs cleaned pairs", matched),
        ("Metric and subgroup summaries", summaries),
    ]:
        add_sheet(book, title, values)
    book.save(directory / "six_run_original_vs_cleaned_results.xlsx")
    report = [
        "# Original versus cleaned three-model evaluation",
        "",
        LABEL,
        "",
        "Completed six distinct runs: 10,884 metric evaluations, 1,814 per run, with four-worker scheduling and the unchanged v2 scorer/rubric. "
        "Question IDs, reference evidence, language and primary/secondary assignments are aligned across the six runs. "
        "All supplied cleaned strings were preserved; the evaluator performed no additional editing or generation.",
        "",
        f"Changed answers versus original workbook: {q['changed_answers_versus_parent_workbook']}.",
        "",
        "| Model | Metric | Pairs | Original mean | Cleaned mean | Mean change |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in summaries:
        if r["grouping"] == "evaluated_model/evaluation_metric":
            report.append(
                f"| {r['evaluated_model']} | {r['evaluation_metric']} | {r['pairs']} | {r['original_mean']:.4f} | {r['cleaned_mean']:.4f} | {r['mean_paired_change']:+.4f} |"
            )
    report += [
        "",
        "Changed and unchanged answer subsets are exported separately by metric. Score changes for identical answers reflect repeat-judging variation, "
        "which helps interpret but does not eliminate uncertainty in cleaning comparisons. Cleaning may remove correct information or alter meaning as well as repetition. "
        "This is an edited-response experiment, not proof of judge bias or improved original model behavior. Generation and cleaning-method metadata were not supplied in the cleaned JSONL. "
        "The original workbook GC temperature mixture remains a limitation of the original condition. Judge-server default temperature, caching and load are uncontrolled. "
        "No combined Canadian-ness score or scientific/team approval is claimed.",
        "",
        f"Cleaned source SHA-256: `{q['source_jsonl_sha256']}`",
        "",
        "Files: `six_run_original_vs_cleaned_results.xlsx`, `all_six_run_results.*`, `original_vs_cleaned_metric_pairs.*`, `original_vs_cleaned_summaries.*`. "
        "Each model/variant run separately retains all scores, reasons, input provenance, checkpoint attempts, retries, usage and immutable execution configuration.",
        "",
    ]
    (directory / "final_report.md").write_text("\n".join(report), encoding="utf8")
    (ROOT / "docs/six_run_original_vs_cleaned_results.md").write_text(
        "\n".join(report), encoding="utf8"
    )
    write_json(
        STATE / "completion.json",
        dict(
            status="COMPLETED",
            successful_additional=5442,
            successful_all_six=10884,
            result_label=LABEL,
        ),
    )
    event("ALL_SIX_RUNS_COMPLETED", successful=10884)


def supervise():
    q = validate_queue()
    STATE.mkdir(parents=True, exist_ok=True)
    with process_lock(STATE / "supervisor.lock"):
        event("WAITING_FOR_ORIGINAL_THREE_RUNS")
        while True:
            prerequisite = PARENT_STATE / "completion.json"
            if (
                prerequisite.exists()
                and json.loads(prerequisite.read_text(encoding="utf8")).get("successful") == 5442
            ):
                break
            # If the parent supervisor stops, wait safely rather than starting the cleaned queue early.
            time.sleep(INTERVAL)
        for model in MODELS:
            validate_queue()
            path, approval, plan = prepare_model(model, q)
            if not approval.exists():
                if plan.get("queue_manifest_sha256") != file_hash(QUEUE / "queue.json"):
                    raise ValueError("Plan outside queue scope")
                authorize(
                    path,
                    approval,
                    approved_by="User: explicit cleaned-data queue request",
                    statement=confirmation(plan),
                )
            require_approval(path, approval)
            previous = status(plan)["successful"]
            stalls = 0
            attempt = 0
            while previous < 1814:
                attempt += 1
                log = STATE / f"{model}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}_{attempt}.log"
                with log.open("w", encoding="utf8") as handle:
                    process = subprocess.Popen(
                        [
                            sys.executable,
                            "-m",
                            "canadianness_eval.concurrent_research",
                            "--plan",
                            str(path),
                            "--approval",
                            str(approval),
                        ],
                        cwd=ROOT,
                        stdout=handle,
                        stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                    )
                    write_json(
                        STATE / "active_process.json",
                        dict(
                            pid=process.pid,
                            model=model,
                            run_id=plan["run_id"],
                            log=str(log),
                            started_at=now(),
                        ),
                    )
                    event(
                        "CLEANED_RUN_STARTED", model=model, run_id=plan["run_id"], pid=process.pid
                    )
                    while True:
                        try:
                            code = process.wait(timeout=INTERVAL)
                            break
                        except subprocess.TimeoutExpired:
                            validate_queue()
                            event("TEN_MINUTE_CHECK_CLEANED", model=model, **status(plan))
                current = status(plan)
                event("CLEANED_PROCESS_EXIT", model=model, exit_code=code, **current)
                if code == 0 and current["successful"] == 1814:
                    break
                validate_queue()
                require_approval(path, approval)
                text = log.read_text(encoding="utf8", errors="replace")
                if any(
                    s in text
                    for s in [
                        "Locked experiment file changed",
                        "mismatch",
                        "Conflicting",
                        "Frozen input changed",
                        "software changed",
                        "authorization changed",
                    ]
                ):
                    raise ValueError("Integrity/configuration failure; inspect " + str(log))
                stalls = 0 if current["successful"] > previous else stalls + 1
                previous = current["successful"]
                if stalls >= 3:
                    raise RuntimeError("Persistent infrastructure failure without progress")
                event("CLEANED_RECOVERY_WAIT", model=model, seconds=INTERVAL)
                time.sleep(INTERVAL)
            enrich(model, plan)
            event("CLEANED_MODEL_COMPLETED", model=model, successful=1814)
        finalize_six()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["initialize", "prepare", "supervise"])
    args = parser.parse_args()
    if args.command == "initialize":
        initialize()
    elif args.command == "prepare":
        q = validate_queue()
        for model in MODELS:
            path, approval, plan = prepare_model(model, q)
            require_approval(path, approval)
            print("READY", model, plan["task_count"], file_hash(path), flush=True)
    else:
        try:
            supervise()
        except Exception as exc:
            event("CLEANED_SUPERVISOR_STOPPED", error=str(exc))
            raise


if __name__ == "__main__":
    main()
