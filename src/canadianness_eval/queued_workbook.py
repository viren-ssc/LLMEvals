"""User-authorized three-model workbook queue; local ten-minute supervision."""

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime

from openpyxl import load_workbook

from .calibration.schema import CalibrationCase, load_cases
from .final_metrics import file_hash
from .gc_as_generated import repetition_indicator
from .hpc_ingestion import read_records
from .hpc_workflow import save_jsonl
from .research_exports import add_sheet, table
from .research_run import LABEL, authorize, confirmation, exclusive, require_approval, verify_plan
from .research_run import prepare as prepare_research
from .settings import ROOT
from .storage import now, write_json
from .verification.db import Conflict, process_lock

SOURCE = ROOT / "canadianness_756_three_model_answers_MIXED_TEMPERATURE_COMPLETE.xlsx"
QUEUE = ROOT / "config/research/mixed_temperature_three_model_queue_v1"
STATE = ROOT / "outputs/queues/mixed_temperature_three_model_queue_v1"
CURRENT_ID = "apertus_full_as_generated_c4_20261107_v2"
MODELS = ["llama", "gc_llm", "apertus"]
INTERVAL = 600


def run_id(model):
    return f"{model}_mixed_temperature_workbook_c4_20261107_v2"


def event(kind, **values):
    STATE.mkdir(parents=True, exist_ok=True)
    row = dict(timestamp=now(), event=kind, **values)
    with (STATE / "supervision.jsonl").open("a", encoding="utf8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(row, ensure_ascii=False), flush=True)


def workbook_rows(path):
    book = load_workbook(path, read_only=True, data_only=True)
    sheet = book["Evaluation Dataset"]
    iterator = sheet.iter_rows(values_only=True)
    keys = next(iterator)
    rows = [dict(zip(keys, r)) for r in iterator]
    provenance = (
        list(book["Replacement Provenance"].values)
        if "Replacement Provenance" in book.sheetnames
        else []
    )
    book.close()
    if len(rows) != 756 or len({r["question_id"] for r in rows}) != 756:
        raise ValueError("Workbook must contain 756 unique questions")
    return rows, provenance


def initialize():
    rows, provenance = workbook_rows(SOURCE)
    base = {
        c.question_id: c for c in load_cases(ROOT / "data/processed/llama_756_v1/all_cases.jsonl")
    }
    if {r["question_id"] for r in rows} != set(base):
        raise ValueError("Workbook question IDs differ from benchmark")
    for r in rows:
        case = base[r["question_id"]]
        for k in ["question", "reference_answer", "language", "primary_metric"]:
            if r[k] != getattr(case, k):
                raise ValueError("Workbook benchmark mismatch: " + k)
        if [r["context_text"]] != case.reference_context:
            raise ValueError("Context mismatch")
        if {s.strip() for s in r["applicable_metrics"].split(",")} != set(case.applicable_metrics):
            raise ValueError("Metric assignments differ")
        for model in MODELS:
            if not isinstance(r[model + "_answer"], str) or not r[model + "_answer"].strip():
                raise ValueError("Empty answer: " + model + "/" + r["question_id"])
    STATE.mkdir(parents=True, exist_ok=True)
    copied = ROOT / "data/incoming/mixed_temperature_three_model" / SOURCE.name
    copied.parent.mkdir(parents=True, exist_ok=True)
    if copied.exists() and file_hash(copied) != file_hash(SOURCE):
        raise ValueError("Source copy changed")
    if not copied.exists():
        copied.write_bytes(SOURCE.read_bytes())
    software = {}
    for name in ["queued_workbook.py", "concurrent_research.py"]:
        path = ROOT / "src/canadianness_eval" / name
        software[path.relative_to(ROOT).as_posix()] = file_hash(path)
    manifest = dict(
        queue_id=QUEUE.name,
        source_workbook=copied.relative_to(ROOT).as_posix(),
        source_workbook_sha256=file_hash(copied),
        order=MODELS,
        run_ids=[run_id(m) for m in MODELS],
        prerequisite_run=CURRENT_ID,
        questions_per_model=756,
        metric_tasks_per_model=1814,
        total_metric_tasks=5442,
        concurrency=4,
        monitor_interval_seconds=INTERVAL,
        software_sha256=software,
        rubric_sha256="bb9889807b7babc8feed6a97ddd0c12c0fa334627e5d295017167fbd0a767cb2",
        evaluator_template_sha256="ecb714aa746f7bdce82d86fd9bcc288d4e26ffd15cfa210bbd19a356e095793f",
        source_provenance=provenance,
        gc_temperature_question_counts=dict(Counter(str(r["gc_llm_temperature"]) for r in rows)),
        gc_reused_answers=sum(bool(r["gc_llm_answer_reused"]) for r in rows),
        scientific_validity_approved=False,
        team_approval=False,
        rubric_empirically_calibrated=False,
        result_label=LABEL,
    )
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
                authorized_by="User instruction in this conversation",
                queue_manifest_sha256=file_hash(QUEUE / "queue.json"),
                verbatim_instruction="This file contains all the 3 models answers, run its evaluation 1 by 1 after this job is done! Be checking every 10 minutes to ensure there is no error and if there is fix it and let it continue.",
                scope="Three complete as-supplied workbook research runs in queue order, plus identical-configuration failed/missing-task recovery",
                execution_authorized=True,
                scientific_validity_approved=False,
                team_approval=False,
                rubric_empirically_calibrated=False,
            ),
        )
    event(
        "QUEUE_AUTHORIZED",
        total_metric_tasks=5442,
        source_sha256=manifest["source_workbook_sha256"],
    )
    return manifest


def validate_queue():
    manifest = json.loads((QUEUE / "queue.json").read_text(encoding="utf8"))
    auth = json.loads((QUEUE / "execution_authorization.json").read_text(encoding="utf8"))
    if (
        auth["status"] != "EXECUTION_AUTHORIZED"
        or auth["execution_authorized"] is not True
        or auth["queue_manifest_sha256"] != file_hash(QUEUE / "queue.json")
    ):
        raise ValueError("Queue execution authorization differs")
    if file_hash(ROOT / manifest["source_workbook"]) != manifest["source_workbook_sha256"]:
        raise ValueError("Frozen source workbook changed")
    for p, sha in manifest["software_sha256"].items():
        if file_hash(ROOT / p) != sha:
            raise ValueError("Frozen queue software changed: " + p)
    return manifest


def prepare_model(model, queue):
    plan_path = ROOT / "config/research" / run_id(model) / "experiment.json"
    approval = plan_path.parent / "execution_approval.json"
    if plan_path.exists():
        return plan_path, approval, verify_plan(plan_path)
    rows, _ = workbook_rows(ROOT / queue["source_workbook"])
    base = {
        c.question_id: c for c in load_cases(ROOT / "data/processed/llama_756_v1/all_cases.jsonl")
    }
    prepared = ROOT / "data/processed" / run_id(model)
    prepared.mkdir(parents=True, exist_ok=True)
    cases = []
    generations = []
    metadata = []
    for r in rows:
        values = base[r["question_id"]].model_dump()
        answer = r[model + "_answer"]
        values.update(
            model_variant=model,
            model_answer=answer,
            dataset_version="mixed-workbook-" + queue["source_workbook_sha256"][:12],
            provenance="Original mixed-temperature workbook; exact answer string unchanged; row provenance in sidecar",
        )
        cases.append(CalibrationCase.model_validate(values))
        generations.append(
            dict(
                question_id=r["question_id"], evaluated_model=model, answer=answer, status="success"
            )
        )
        meta = dict(
            question_id=r["question_id"],
            evaluated_model=model,
            source_workbook_sha256=queue["source_workbook_sha256"],
            generation_temperature=r.get("gc_llm_temperature") if model == "gc_llm" else None,
            answer_reused=r.get("gc_llm_answer_reused") if model == "gc_llm" else None,
            source_generation_run_id=r.get("gc_llm_source_run_id") if model == "gc_llm" else None,
            generation_metadata_limitations="Workbook does not supply termination flags, output tokens, revision, cap or full inference configuration for these answer columns",
            **repetition_indicator(answer),
        )
        metadata.append(meta)
    cases_path = prepared / "all_cases.jsonl"
    generation_path = prepared / "generations.jsonl"
    sidecar = prepared / "generation_metadata.jsonl"
    save_jsonl(cases_path, [c.model_dump() for c in cases])
    save_jsonl(generation_path, generations)
    save_jsonl(sidecar, metadata)
    draft = prepare_research(
        prepared / "preparation_draft/experiment.json",
        run_id=run_id(model),
        model=model,
        cases_path=cases_path,
        generations_path=generation_path,
        workbook_path=ROOT / queue["source_workbook"],
    )
    draft.update(
        execution_engine="concurrent-research-v1",
        queue_manifest_sha256=file_hash(QUEUE / "queue.json"),
        queue_execution_authorization_sha256=file_hash(QUEUE / "execution_authorization.json"),
        policy_basis="Explicit user authorization for three sequential full workbook evaluations after the current Apertus run",
        execution_profile=dict(
            workers=4,
            scheduling_unit="question",
            checkpoint_unit="individual metric",
            scorer="unchanged evaluate_calibration",
            shared_retry_cooldown=True,
            coordinator_serialized_publication=True,
        ),
        missing_generation_metadata="GC has 755 temperature-0.7 answers and one reused temperature-0.0 answer. Llama/Apertus generation temperatures unknown. Other inference settings/revisions/termination flags are not supplied; not inferred from earlier runs.",
    )
    draft["judge"]["concurrency"] = 4
    for path in [
        sidecar,
        QUEUE / "queue.json",
        QUEUE / "execution_authorization.json",
        ROOT / "config/evaluator/execution_defaults.json",
    ]:
        draft["input_sha256"][path.relative_to(ROOT).as_posix()] = file_hash(path)
    draft["software_sha256"].update(queue["software_sha256"])
    # Protect authoritative prior checkpoints without pinning reports that may be opened or regenerated.
    for previous in ["llama_full_20261106_v2", "gc_llm_full_as_generated_20261106_v2", CURRENT_ID]:
        prior = ROOT / "outputs/evaluations" / previous
        for sub in ["records", "raw"]:
            for path in (prior / sub).glob("*.json"):
                draft["protected_pilot_sha256"][path.relative_to(ROOT).as_posix()] = file_hash(path)
    draft["as_generated_contract"] = dict(
        source_workbook_sha256=queue["source_workbook_sha256"],
        source_metadata_sidecar=sidecar.relative_to(ROOT).as_posix(),
        all_responses_retained=True,
        responses_regenerated=False,
        responses_cleaned=False,
        special_scoring_instructions=False,
    )
    exclusive(plan_path, draft)
    exclusive(
        plan_path.parent / "authorization_source.json",
        dict(
            queue_manifest_sha256=file_hash(QUEUE / "queue.json"),
            queue_execution_authorization_sha256=file_hash(QUEUE / "execution_authorization.json"),
            source="Explicit user workbook queue instruction",
            experiment_sha256=file_hash(plan_path),
            execution_permission_only=True,
            scientific_validity_approved=False,
        ),
    )
    authorize(
        plan_path,
        approval,
        approved_by="User: explicit three-model workbook queue instruction; scope bound to queue manifest",
        statement=confirmation(draft),
    )
    write_json(
        prepared / "validation_manifest.json",
        dict(
            status="VALID",
            questions=756,
            metric_tasks=1814,
            primary=756,
            secondary=1058,
            exact_workbook_response_strings_preserved=True,
            source_workbook_sha256=queue["source_workbook_sha256"],
            language_questions=dict(Counter(c.language for c in cases)),
        ),
    )
    return plan_path, approval, verify_plan(plan_path)


def checkpoint_status(plan):
    from .calibration.evaluate import read_results

    rows = [r for r in read_results(ROOT / plan["run_directory"]) if r["applicable"]]
    return dict(
        successful=sum(r["status"] == "SUCCESS" for r in rows),
        failed=sum(r["status"] != "SUCCESS" for r in rows),
        pending=plan["task_count"] - len(rows),
    )


def enrich(model, plan):
    directory = ROOT / plan["run_directory"]
    rows = read_records(directory / "all_results.jsonl")
    if len(rows) != 1814 or any(r["status"] != "SUCCESS" for r in rows):
        raise ValueError("Incomplete run")
    original = {
        r["question_id"]: r for r in workbook_rows(ROOT / validate_queue()["source_workbook"])[0]
    }
    sidecar = ROOT / plan["as_generated_contract"]["source_metadata_sidecar"]
    metadata = {r["question_id"]: r for r in read_records(sidecar)}
    assert (
        len({(r["question_id"], r["evaluated_model"], r["evaluation_metric"]) for r in rows})
        == 1814
    )
    assert all(r["model_answer"] == original[r["question_id"]][model + "_answer"] for r in rows)
    values = [dict(r, generation_metadata=metadata[r["question_id"]]) for r in rows]
    table(directory / "as_generated_results", values)
    book = load_workbook(directory / "full_results.xlsx")
    add_sheet(book, "Source generation provenance", list(metadata.values()))
    add_sheet(book, "Original workbook answers", values)
    book.save(directory / "as_generated_results.xlsx")
    write_json(
        directory / "completion_verification.json",
        dict(
            status="PASS",
            successful=1814,
            failed=0,
            missing=0,
            response_strings_unchanged=True,
            experiment_sha256=file_hash(
                ROOT / "config/research" / run_id(model) / "experiment.json"
            ),
            source_workbook_sha256=plan["as_generated_contract"]["source_workbook_sha256"],
            rubric_sha256=plan["rubric_sha256"],
            evaluator_template_sha256=plan["evaluator_template_sha256"],
            concurrency=4,
            result_label=LABEL,
            scientific_validity_approved=False,
            team_approval=False,
        ),
    )


def supervise():
    queue = validate_queue()
    STATE.mkdir(parents=True, exist_ok=True)
    with process_lock(STATE / "supervisor.lock"):
        event("WAITING_FOR_CURRENT_APERTUS", run_id=CURRENT_ID)
        prerequisite = ROOT / "config/research" / CURRENT_ID / "experiment.json"
        current = json.loads(prerequisite.read_text(encoding="utf8"))
        current_previous = 0
        current_stalls = 0
        while True:
            status = checkpoint_status(current)
            event("PREREQUISITE_CHECK", run_id=CURRENT_ID, **status)
            summary = ROOT / current["run_directory"] / "full_run_summary.json"
            if (
                status["successful"] == 1814
                and summary.exists()
                and json.loads(summary.read_text(encoding="utf8"))["successful"] == 1814
            ):
                verify_plan(prerequisite)
                break
            # Test the existing kernel lock; never launch a second active runner.
            busy = False
            try:
                with process_lock(ROOT / current["run_directory"] / "run.lock"):
                    pass
            except Conflict:
                busy = True
            if not busy:
                validate_queue()
                current_approval = prerequisite.parent / "execution_approval.json"
                require_approval(prerequisite, current_approval)
                current_stalls = (
                    0 if status["successful"] > current_previous else current_stalls + 1
                )
                current_previous = status["successful"]
                if current_stalls >= 3:
                    raise RuntimeError(
                        "Persistent current Apertus infrastructure failure without progress"
                    )
                log = (
                    STATE
                    / f"current_apertus_recovery_{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}.log"
                )
                with log.open("w", encoding="utf8") as handle:
                    process = subprocess.Popen(
                        [
                            sys.executable,
                            "-m",
                            "canadianness_eval.concurrent_research",
                            "--plan",
                            str(prerequisite),
                            "--approval",
                            str(current_approval),
                        ],
                        cwd=ROOT,
                        stdout=handle,
                        stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                    )
                event("CURRENT_APERTUS_RECOVERY", pid=process.pid, **status)
            time.sleep(INTERVAL)
        for model in MODELS:
            validate_queue()
            plan_path, approval, plan = prepare_model(model, queue)
            # A crash after plan creation but before authorization is recoverable only under this explicit queue scope.
            if not approval.exists():
                if plan.get("queue_manifest_sha256") != file_hash(QUEUE / "queue.json"):
                    raise ValueError("Run outside queue scope")
                authorize(
                    plan_path,
                    approval,
                    approved_by="User: explicit workbook queue authorization",
                    statement=confirmation(plan),
                )
            require_approval(plan_path, approval)
            stalls = 0
            previous = checkpoint_status(plan)["successful"]
            attempt = 0
            while previous < 1814:
                attempt += 1
                log = (
                    STATE
                    / f"{model}_execution_{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}_{attempt}.log"
                )
                command = [
                    sys.executable,
                    "-m",
                    "canadianness_eval.concurrent_research",
                    "--plan",
                    str(plan_path),
                    "--approval",
                    str(approval),
                ]
                with log.open("w", encoding="utf8") as handle:
                    process = subprocess.Popen(
                        command,
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
                    event("RUN_STARTED", model=model, run_id=plan["run_id"], pid=process.pid)
                    while True:
                        try:
                            code = process.wait(timeout=INTERVAL)
                            break
                        except subprocess.TimeoutExpired:
                            validate_queue()
                            event("TEN_MINUTE_CHECK", model=model, **checkpoint_status(plan))
                status = checkpoint_status(plan)
                event("RUN_PROCESS_EXIT", model=model, exit_code=code, **status)
                if code == 0 and status["successful"] == 1814:
                    break
                # Integrity/authorization checks precede every restart and cannot be bypassed.
                validate_queue()
                require_approval(plan_path, approval)
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
                    raise ValueError("Integrity/configuration stop; inspect " + str(log))
                stalls = 0 if status["successful"] > previous else stalls + 1
                previous = status["successful"]
                if stalls >= 3:
                    raise RuntimeError(
                        "Persistent infrastructure failure after three no-progress restarts; inspect "
                        + str(log)
                    )
                event("RECOVERY_WAIT", model=model, seconds=INTERVAL, **status)
                time.sleep(INTERVAL)
            enrich(model, plan)
            event("MODEL_COMPLETED", model=model, successful=1814)
        event("QUEUE_COMPLETED", successful=5442, result_label=LABEL)
        write_json(
            STATE / "completion.json",
            dict(
                status="COMPLETED",
                successful=5442,
                failed=0,
                run_ids=queue["run_ids"],
                result_label=LABEL,
            ),
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["initialize", "supervise"])
    args = parser.parse_args()
    if args.command == "initialize":
        initialize()
    else:
        try:
            supervise()
        except Exception as exc:
            event("SUPERVISOR_STOPPED", error=str(exc))
            raise


if __name__ == "__main__":
    main()
