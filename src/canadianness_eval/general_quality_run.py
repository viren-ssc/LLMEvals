"""User-supplied general metrics, using the existing GEval factory and gateway.

The original seven-metric schemas/runners remain byte-for-byte unchanged. This
adapter supplies the two new definitions to the same scorer, and reuses atomic
metric checkpoint primitives with bounded four-worker scheduling.
"""

import argparse
import json
import math
import re
import subprocess
import sys
import threading
import time
import uuid
from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from types import SimpleNamespace

from openpyxl import Workbook
from pydantic import create_model

from .api_client import Gateway
from .calibration.evaluate import exclusive_json, read_results
from .calibration.factory import judge_case, make_final_metric, normalized_score, template_metadata
from .final_metrics import Band, file_hash
from .general_quality_setup import PROCESSED
from .hpc_ingestion import read_records
from .judge_adapter import RemoteJudge
from .queued_cleaned import STATE as PREVIOUS_STATE
from .research_exports import LABEL, add_sheet, table
from .research_run import CODE_FILES, exclusive
from .settings import ROOT, Settings
from .storage import digest, now, versions, write_json
from .verification.db import process_lock

SOURCE = ROOT / "Canadianness_General_Correctness_Completeness_Proposed_v1.md"
CONFIG = ROOT / "config/general_answer_quality/2026-11-07-user-v1"
PLAN = CONFIG / "experiment.json"
APPROVAL = CONFIG / "execution_approval.json"
STATE = ROOT / "outputs/queues/general_quality_cleaned_20261107_v1"
MODELS = ["llama", "gc_llm", "apertus"]
INTERVAL = 600


def run_id(model):
    return f"{model}_general_quality_cleaned_20261107_v1"


def extract_definitions(path=SOURCE):
    text = Path(path).read_text(encoding="utf-8-sig")
    metrics = []
    for mid, title in [
        ("correctness", "Answer Correctness"),
        ("completeness", "Answer Completeness"),
    ]:
        section = text.split("## " + title + "\n", 1)[1].split("\n## ", 1)[0]
        criteria = section.split("### Six fixed G-Eval steps", 1)[0].strip()
        steps = re.findall(r"^\d+\. (.+)$", section, re.MULTILINE)
        bands = []
        for line in section.splitlines():
            match = re.match(r"^\| \*\*(\d+)\D+(\d+)\*\* \| (.+) \|$", line)
            if match:
                bands.append(dict(min=int(match[1]), max=int(match[2]), expected_outcome=match[3]))
        boundary = section.split("**Metric boundary:** ", 1)[1].strip()
        if len(steps) != 6 or [(b["min"], b["max"]) for b in bands] != [
            (0, 2),
            (3, 4),
            (5, 6),
            (7, 8),
            (9, 10),
        ]:
            raise ValueError("Expected exactly six steps and five supplied bands for " + mid)
        metrics.append(
            dict(
                metric_id=mid,
                name=title,
                criteria=criteria,
                scope_exclusions=boundary,
                evaluation_steps=steps,
                rubric_0_to_10=bands,
                required_evaluation_params=["INPUT", "ACTUAL_OUTPUT", "EXPECTED_OUTPUT", "CONTEXT"],
            )
        )
    common = text.split("## Common scoring rules\n", 1)[1].split("\n## ", 1)[0].strip()
    declared = re.search(r"Metric-definitions SHA-256:\*\* `([a-f0-9]{64})`", text)
    version = re.search(r"Version:\*\* `([^`]+)`", text)
    return dict(
        version=version[1],
        metrics=metrics,
        common_scoring_rules=common,
        declared_definition_sha256=declared[1],
        source_markdown_sha256=file_hash(path),
    )


def definition_object(definition, common):
    return SimpleNamespace(
        **dict(
            definition,
            criteria=definition["criteria"]
            + "\n\nCommon scoring rules (verbatim user-supplied):\n"
            + common,
            rubric_0_to_10=[Band.model_validate(b) for b in definition["rubric_0_to_10"]],
        )
    )


class EvidenceJudge(RemoteJudge):
    """Same transport and scoring schema, with the requested evidence-review metadata."""

    def generate(self, prompt, schema=None):
        if schema is None or set(schema.model_fields) != {"score", "reason"}:
            raise ValueError(
                "Only fixed-rubric scoring is allowed; dynamic step generation prohibited"
            )
        extended = create_model(
            "GeneralQualityReasonScore",
            __base__=schema,
            evidence_review_required=(bool, ...),
            evidence_review_notes=(list[str], ...),
        )
        return self.gateway.generate(
            prompt
            + "\nOutput metadata: populate evidence_review_required and evidence_review_notes "
            "to flag material evidence conflicts or decisive uncheckable claims as required by the supplied common rules. "
            "These fields do not add evaluation steps or change scoring bands.",
            extended,
        )


def event(kind, **values):
    STATE.mkdir(parents=True, exist_ok=True)
    row = dict(timestamp=now(), event=kind, queue_id=STATE.name, **values)
    with (STATE / "supervision.jsonl").open("a", encoding="utf8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(row, ensure_ascii=False), flush=True)


def prepare():
    definitions = extract_definitions()
    definitions_path = CONFIG / "metrics_extracted.json"
    if not definitions_path.exists():
        exclusive(definitions_path, definitions)
    elif json.loads(definitions_path.read_text(encoding="utf8")) != definitions:
        raise ValueError("Definitions changed")
    setup = json.loads(
        (ROOT / "config/general_answer_quality/v1/setup_manifest.json").read_text(encoding="utf8")
    )
    if file_hash(ROOT / setup["source_jsonl"]) != setup["source_jsonl_sha256"]:
        raise ValueError("Cleaned source changed")
    tasks = read_records(PROCESSED / "planned_tasks.jsonl")
    if (
        len(tasks) != 4536
        or len({(r["question_id"], r["evaluated_model"], r["evaluation_metric"]) for r in tasks})
        != 4536
    ):
        raise ValueError("Invalid task inventory")
    source = {r["question_id"]: r for r in read_records(ROOT / setup["source_jsonl"])}
    for model in MODELS:
        cases = read_records(PROCESSED / model / "cases.jsonl")
        if len(cases) != 756:
            raise ValueError("Missing cases")
        for c in cases:
            original = source[c["question_id"]]
            if c["evaluated_model"] != model or c["model_answer"] != original[model + "_answer"]:
                raise ValueError("Model answer mismatch")
            for name in MODELS:
                if name + "_answer" in c:
                    raise ValueError("Cross-model response field")
            if (
                c["question"] != original["question"]
                or c["reference_answer"] != original["reference_answer"]
                or c["reference_context"] != [original["context_text"]]
            ):
                raise ValueError("Evidence mismatch")
    inputs = [
        SOURCE,
        definitions_path,
        ROOT / setup["source_jsonl"],
        PROCESSED / "planned_tasks.jsonl",
        PROCESSED / "shared_question_evidence.jsonl",
        *[PROCESSED / m / "cases.jsonl" for m in MODELS],
        ROOT / "config/evaluator/execution_defaults.json",
    ]
    settings = Settings.load()
    plan = dict(
        experiment_id=STATE.name,
        status="EXECUTION_READY_PENDING_AUTHORIZATION",
        models=MODELS,
        run_ids={m: run_id(m) for m in MODELS},
        metric_ids=["correctness", "completeness"],
        metrics_path=definitions_path.relative_to(ROOT).as_posix(),
        questions=756,
        tasks_per_model=1512,
        total_tasks=4536,
        tasks_path=(PROCESSED / "planned_tasks.jsonl").relative_to(ROOT).as_posix(),
        source_markdown_sha256=file_hash(SOURCE),
        extracted_definition_sha256=file_hash(definitions_path),
        document_declared_definition_sha256=definitions["declared_definition_sha256"],
        declared_checksum_note="Retained verbatim. The document does not provide the original serialized JSON payload; its declared checksum is not asserted equal to the independently hashed extraction.",
        input_sha256={p.relative_to(ROOT).as_posix(): file_hash(p) for p in inputs},
        software_sha256={p: file_hash(ROOT / p) for p in CODE_FILES},
        package_versions=versions(),
        python_version=sys.version,
        judge=dict(
            model="gpt-oss-120b",
            endpoint=settings.base,
            timeout_seconds=settings.timeout,
            concurrency=4,
            sampling="gateway default; temperature/top_p omitted; determinism not established",
            min_seconds_between_task_starts=0.25,
            transient_http_attempts=3,
            validation_attempts=3,
            stop_after_consecutive_failed_tasks=5,
            retry_after_max_wait_seconds=60,
        ),
        **template_metadata(),
        normalization="DeepEval native 0-1 exactly once; no second division; raw schema score must be integer 0-10",
        metric_steps=12,
        rubric_bands=10,
        dynamic_step_generation_allowed=False,
        shared_metric_definitions_across_models=True,
        parent_completion=str((PREVIOUS_STATE / "completion.json").relative_to(ROOT)),
        evidence_provenance="Imported benchmark attestation; not independent human validation for new metrics",
        original_primary_secondary_assignments_preserved_as_provenance=True,
        scientific_validity_approved=False,
        team_approval=False,
        rubric_empirically_calibrated=False,
        result_label=LABEL,
    )
    own = Path(__file__)
    plan["software_sha256"][own.relative_to(ROOT).as_posix()] = file_hash(own)
    if not PLAN.exists():
        exclusive(PLAN, plan)
    elif json.loads(PLAN.read_text(encoding="utf8")) != plan:
        raise ValueError("Immutable general-quality experiment differs")
    if not APPROVAL.exists():
        exclusive(
            APPROVAL,
            dict(
                status="EXECUTION_AUTHORIZED",
                execution_authorized=True,
                authorized_at=now(),
                authorized_by="User: explicit instruction in this conversation",
                experiment_sha256=file_hash(PLAN),
                verbatim_instruction="This file contains the evaluation steps and rubric for our two metrics, read it carefully, extract it and start the queue for all 3 models on the 2 additional metrics and use it on the cleaned data that we have",
                source_markdown_sha256=file_hash(SOURCE),
                scope="One 4,536-task provisional cleaned-data experiment plus identical-configuration failed/missing-task resumption",
                user_definition_execution_permission=True,
                scientific_validity_approved=False,
                team_approval=False,
                rubric_empirically_calibrated=False,
            ),
        )
    return verify()


def verify():
    plan = json.loads(PLAN.read_text(encoding="utf8"))
    approval = json.loads(APPROVAL.read_text(encoding="utf8"))
    if (
        approval["status"] != "EXECUTION_AUTHORIZED"
        or approval["execution_authorized"] is not True
        or approval["experiment_sha256"] != file_hash(PLAN)
    ):
        raise ValueError("Execution authorization mismatch")
    for value in [plan, approval]:
        if any(
            value[k] is not False
            for k in [
                "scientific_validity_approved",
                "team_approval",
                "rubric_empirically_calibrated",
            ]
        ):
            raise ValueError("Provisional execution does not grant scientific approval")
    for group in ["input_sha256", "software_sha256"]:
        for p, sha in plan[group].items():
            if file_hash(ROOT / p) != sha:
                raise ValueError("Frozen input/software changed: " + p)
    if plan["package_versions"] != versions() or plan["python_version"] != sys.version:
        raise ValueError("Runtime changed")
    if template_metadata()["evaluator_template_sha256"] != plan["evaluator_template_sha256"]:
        raise ValueError("Fixed factory changed")
    definitions = json.loads((ROOT / plan["metrics_path"]).read_text(encoding="utf8"))
    if definitions != extract_definitions():
        raise ValueError("Extraction no longer matches source verbatim")
    return plan


def publish(path, value):
    """Atomic immutable checkpoints, with bounded retries for transient Windows file locks."""
    for attempt in range(4):
        try:
            if path.exists():
                if json.loads(path.read_text(encoding="utf8")) != value:
                    raise ValueError("Conflicting checkpoint")
                return
            exclusive_json(path, value)
            return
        except PermissionError:
            if attempt == 3:
                raise
            time.sleep(0.2 * (2**attempt))


def latest(directory):
    return [r for r in read_results(directory) if r["applicable"]]


def status(model):
    rows = latest(ROOT / "outputs/evaluations" / run_id(model))
    planned = len(read_records(PROCESSED / model / "cases.jsonl")) * 2
    return dict(
        successful=sum(r["status"] == "SUCCESS" for r in rows),
        failed=sum(r["status"] != "SUCCESS" for r in rows),
        pending=planned - len(rows),
    )


def execute(model):
    plan = verify()
    directory = ROOT / "outputs/evaluations" / run_id(model)
    directory.mkdir(parents=True, exist_ok=True)
    with process_lock(directory / "run.lock"):
        plan = verify()
        session = uuid.uuid4().hex
        started = now()
        definitions = json.loads((ROOT / plan["metrics_path"]).read_text(encoding="utf8"))
        defs = {
            d["metric_id"]: definition_object(d, definitions["common_scoring_rules"])
            for d in definitions["metrics"]
        }
        cases = {c["question_id"]: c for c in read_records(PROCESSED / model / "cases.jsonl")}
        manifest = dict(
            run_id=run_id(model),
            evaluated_model=model,
            experiment_sha256=file_hash(PLAN),
            execution_approval_sha256=file_hash(APPROVAL),
            metrics_sha256=plan["extracted_definition_sha256"],
            judge_configuration=plan["judge"],
            result_label=LABEL,
        )
        if (directory / "manifest.json").exists():
            if json.loads((directory / "manifest.json").read_text(encoding="utf8")) != manifest:
                raise ValueError("Resume manifest mismatch")
        else:
            exclusive(directory / "manifest.json", manifest)
        lock = threading.Lock()
        stop = threading.Event()
        state = dict(next_start=0.0, consecutive_failures=0, http_attempts=0)
        input_stats = {
            p: ((ROOT / p).stat().st_size, (ROOT / p).stat().st_mtime_ns)
            for p in plan["input_sha256"]
        }

        def guard():
            while True:
                if stop.is_set():
                    raise RuntimeError("Shared infrastructure stop")
                with lock:
                    for p, sha in plan["software_sha256"].items():
                        if file_hash(ROOT / p) != sha:
                            stop.set()
                            raise ValueError("Frozen software changed")
                    for p, expected in input_stats.items():
                        info = (ROOT / p).stat()
                        if (info.st_size, info.st_mtime_ns) != expected:
                            stop.set()
                            raise ValueError("Frozen input changed")
                    if (
                        file_hash(PLAN) != manifest["experiment_sha256"]
                        or file_hash(APPROVAL) != manifest["execution_approval_sha256"]
                    ):
                        stop.set()
                        raise ValueError("Authorization or experiment changed")
                    delay = state["next_start"] - time.monotonic()
                    if delay <= 0:
                        state["next_start"] = (
                            time.monotonic() + plan["judge"]["min_seconds_between_task_starts"]
                        )
                        return
                stop.wait(min(delay, 0.25))

        def cooldown(seconds):
            with lock:
                state["next_start"] = max(state["next_start"], time.monotonic() + seconds)
            if stop.wait(seconds):
                raise RuntimeError("Shared stop during retry")

        existing = {(r["question_id"], r["metric_id"]): r for r in latest(directory)}
        tasks = iter(
            (qid, mid)
            for qid in cases
            for mid in defs
            if existing.get((qid, mid), {}).get("status") != "SUCCESS"
        )
        settings = Settings.load()
        if (
            settings.base != plan["judge"]["endpoint"]
            or settings.timeout != plan["judge"]["timeout_seconds"]
            or settings.model not in ["auto", "gpt-oss-120b"]
        ):
            raise ValueError("Configured judge changed")

        def worker(task):
            qid, mid = task
            guard()
            case = cases[qid]
            definition = defs[mid]
            gateway = Gateway(settings, sleep=cooldown)
            gateway.model_id = "gpt-oss-120b"
            judge = EvidenceJudge(gateway)
            previous = existing.get(task)
            attempt = previous["attempt"] + 1 if previous else 1
            token = digest([qid, model, mid, 1])[:20] + f"_attempt_{attempt:03}"
            while (directory / "raw" / f"{token}.json").exists() or (
                directory / "records" / f"{token}.json"
            ).exists():
                attempt += 1
                token = digest([qid, model, mid, 1])[:20] + f"_attempt_{attempt:03}"
            row = dict(
                question_id=qid,
                model_variant=model,
                evaluated_model=model,
                metric_id=mid,
                evaluation_metric=mid,
                metric_name=definition.name,
                repeat=1,
                attempt=attempt,
                evaluation_run_id=run_id(model),
                result_id=uuid.uuid4().hex,
                applicable=True,
                language=case["language"],
                metric_role="general",
                original_primary_metric=case["original_primary_metric"],
                original_secondary_metrics=case["original_secondary_metrics"],
                timestamp=now(),
                status="FAILED",
                score=None,
                reason=None,
                error=None,
                deepeval_score=None,
                normalized_score=None,
                judge_model="gpt-oss-120b",
                judge_configuration=dict(plan["judge"], **template_metadata()),
                rubric_version=definitions["version"],
                metric_version=definitions["version"],
                metric_json_sha256=plan["extracted_definition_sha256"],
                source_markdown_sha256=plan["source_markdown_sha256"],
                experiment_sha256=manifest["experiment_sha256"],
                execution_approval_sha256=manifest["execution_approval_sha256"],
                response_variant="user_provided_cleaned",
                evidence_review_required=False,
                evidence_review_notes=[],
                evidence_provenance=plan["evidence_provenance"],
                result_label=LABEL,
                provisional=True,
                scientific_validity_approved=False,
            )
            start = time.perf_counter()
            try:
                metric = make_final_metric(definition, judge)
                score = metric.measure(
                    judge_case(SimpleNamespace(**case), definition), _show_indicator=False
                )
                value = normalized_score(score)
                if not math.isclose(value * 10, round(value * 10), abs_tol=1e-8):
                    raise ValueError("Judge did not select integer raw score")
                if not isinstance(metric.reason, str) or not metric.reason.strip():
                    raise ValueError("Missing judge explanation")
                content = gateway.history[-1]["raw_response"]["choices"][0]["message"][
                    "content"
                ].strip()
                if content.startswith("```"):
                    content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                extra = json.loads(content)
                row.update(
                    status="SUCCESS",
                    score=value,
                    normalized_score=value,
                    deepeval_score=score,
                    raw_rubric_score=round(value * 10),
                    reason=metric.reason,
                    evidence_review_required=extra["evidence_review_required"],
                    evidence_review_notes=extra["evidence_review_notes"],
                )
            except Exception as exc:
                row.update(
                    error=gateway.safe_error(exc),
                    evidence_review_required=True,
                    evidence_review_notes=["Evaluation failed; not an adjudicated answer defect"],
                )
            finally:
                row.update(
                    completion_timestamp=now(),
                    latency_seconds=time.perf_counter() - start,
                    request_attempts=gateway.attempts,
                    raw_output_file=str(Path("raw") / f"{token}.json"),
                )
                try:
                    with lock:
                        publish(
                            directory / "raw" / f"{token}.json",
                            dict(result_id=row["result_id"], responses=gateway.history),
                        )
                        publish(directory / "records" / f"{token}.json", row)
                        with (directory / "calibration_results.jsonl").open(
                            "a", encoding="utf8"
                        ) as handle:
                            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                        state["http_attempts"] += gateway.attempts
                        state["consecutive_failures"] = (
                            state["consecutive_failures"] + 1 if row["status"] == "FAILED" else 0
                        )
                        for n in range(4):
                            try:
                                write_json(
                                    directory / "progress.json",
                                    dict(
                                        run_id=run_id(model),
                                        session=session,
                                        last_question_id=qid,
                                        last_metric=mid,
                                        last_status=row["status"],
                                        timestamp=now(),
                                        concurrency=4,
                                        result_label=LABEL,
                                    ),
                                )
                                break
                            except PermissionError:
                                if n == 3:
                                    raise
                                time.sleep(0.2 * (2**n))
                        if (
                            gateway.auth_failed
                            or "HTTP 429" in (row["error"] or "")
                            or "Rate limit requests" in (row["error"] or "")
                            or state["consecutive_failures"] >= 5
                        ):
                            stop.set()
                except Exception:
                    stop.set()
                    raise
                finally:
                    gateway.close()
            print(run_id(model), qid, mid, row["status"], row["score"], flush=True)
            return row

        discovery = Gateway(settings)
        failure = None
        try:
            discovery.discover()
            if discovery.model_id != "gpt-oss-120b":
                raise ValueError("Judge identity changed")
            publish(
                directory / "sessions" / f"{session}_discovery.json", dict(events=discovery.history)
            )
            # Immutable metric checkpoints are authoritative after interruptions.
            records = [
                json.loads(p.read_text(encoding="utf8"))
                for p in sorted((directory / "records").glob("*.json"))
            ]
            (directory / "calibration_results.jsonl").write_text(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf8"
            )
            with ThreadPoolExecutor(max_workers=4) as pool:
                active = set()
                for _ in range(4):
                    task = next(tasks, None)
                    if task:
                        active.add(pool.submit(worker, task))
                while active:
                    done, active = wait(active, return_when=FIRST_COMPLETED)
                    for future in done:
                        try:
                            future.result()
                        except Exception:
                            stop.set()
                            raise
                        if not stop.is_set():
                            task = next(tasks, None)
                            if task:
                                active.add(pool.submit(worker, task))
            if stop.is_set():
                failure = "Shared infrastructure stop; resume failed/missing tasks"
        except Exception as exc:
            stop.set()
            failure = discovery.safe_error(exc)
        finally:
            publish(
                directory / "sessions" / f"{session}.json",
                dict(
                    started=started,
                    ended=now(),
                    error=failure,
                    http_attempts=state["http_attempts"] + discovery.attempts,
                    discovery_events=discovery.history,
                ),
            )
            discovery.close()
            export_model(model, plan)
        verify()
        counts = status(model)
        print(json.dumps(dict(model=model, **counts, error=failure)), flush=True)
        return 0 if counts["successful"] == len(cases) * len(defs) and failure is None else 1


def export_model(model, plan):
    directory = ROOT / "outputs/evaluations" / run_id(model)
    cases = {r["question_id"]: r for r in read_records(PROCESSED / model / "cases.jsonl")}
    indexed = {(r["question_id"], r["metric_id"]): r for r in latest(directory)}
    rows = []
    for qid, case in cases.items():
        for mid in plan["metric_ids"]:
            saved = indexed.get((qid, mid), {})
            rows.append(
                dict(
                    **case,
                    evaluation_metric=mid,
                    score=saved.get("score"),
                    raw_rubric_score=saved.get("raw_rubric_score"),
                    judge_reason=saved.get("reason"),
                    status=saved.get("status", "PENDING"),
                    evaluation_run_id=run_id(model),
                    evidence_review_required=saved.get("evidence_review_required"),
                    evidence_review_notes=saved.get("evidence_review_notes"),
                    judge_configuration=saved.get("judge_configuration", plan["judge"]),
                    rubric_version="2026-11-07-proposed-v1",
                    metric_definitions_sha256=plan["extracted_definition_sha256"],
                    experiment_sha256=file_hash(PLAN),
                    raw_output_file=saved.get("raw_output_file"),
                    attempt=saved.get("attempt"),
                    timestamp=saved.get("timestamp"),
                    completion_timestamp=saved.get("completion_timestamp"),
                    result_label=LABEL,
                    scientific_validity_approved=False,
                )
            )
    table(directory / "all_results", rows)
    for mid in plan["metric_ids"]:
        table(directory / f"{mid}_results", [r for r in rows if r["evaluation_metric"] == mid])
    summaries = []
    for axes in [
        ("evaluation_metric",),
        ("evaluation_metric", "language"),
        ("evaluation_metric", "original_primary_metric"),
    ]:
        groups = defaultdict(list)
        for row in rows:
            groups[tuple(row[k] for k in axes)].append(row)
        for key, values in sorted(groups.items()):
            good = [r for r in values if r["status"] == "SUCCESS"]
            summaries.append(
                dict(
                    zip(axes, key),
                    grouping="/".join(axes),
                    planned=len(values),
                    successful=len(good),
                    mean_score=sum(r["score"] for r in good) / len(good) if good else None,
                    evidence_review_required=sum(bool(r["evidence_review_required"]) for r in good),
                    result_label=LABEL,
                )
            )
    table(directory / "metric_summaries", summaries)
    table(
        directory / "evidence_review_required", [r for r in rows if r["evidence_review_required"]]
    )
    table(directory / "failures", [r for r in rows if r["status"] == "FAILED"])
    table(directory / "missing_tasks", [r for r in rows if r["status"] == "PENDING"])
    attempts = [
        json.loads(p.read_text(encoding="utf8"))
        for p in sorted((directory / "records").glob("*.json"))
    ]
    table(directory / "attempts", attempts)
    table(
        directory / "retry_report",
        [r for r in attempts if r["attempt"] > 1 or r["request_attempts"] > 1],
    )
    events = []
    usage = Counter()
    http = Counter()
    orphans = []
    linked = {r["raw_output_file"] for r in attempts}
    for path in (directory / "raw").glob("*.json"):
        raw = json.loads(path.read_text(encoding="utf8"))
        if str(path.relative_to(directory)) not in linked:
            orphans.append(str(path.relative_to(directory)))
        for e in raw["responses"]:
            http[str(e["status"])] += 1
            events.append(e)
            for k, v in e.get("raw_response", {}).get("usage", {}).items():
                if isinstance(v, int):
                    usage[k] += v
    summary = dict(
        **status(model),
        planned=len(rows),
        scoring_http_attempts=len(events),
        http_status_counts=dict(http),
        api_reported_tokens=dict(usage),
        raw_files_without_metric_checkpoint=orphans,
        usage_missing_events=sum(not e.get("raw_response", {}).get("usage") for e in events),
        no_overall_combined_score=True,
        result_label=LABEL,
    )
    write_json(directory / "full_run_summary.json", summary)
    book = Workbook()
    book.remove(book.active)
    for title, values in [
        ("Individual judgments", rows),
        ("Metric language summaries", summaries),
        ("Evidence review", [r for r in rows if r["evidence_review_required"]]),
        ("Attempts and retries", attempts),
        ("Configuration", [dict(plan)]),
    ]:
        add_sheet(book, title, values)
    book.save(directory / "full_results.xlsx")
    report = [
        f"# {model}: general correctness and completeness",
        "",
        LABEL,
        "",
        f"Successful {summary['successful']}/{summary['planned']}; failed {summary['failed']}; pending {summary['pending']}.",
        "",
        "| Metric | Successful | Mean score | Evidence review flags |",
        "|---|---:|---:|---:|",
    ]
    for row in summaries:
        if row["grouping"] == "evaluation_metric":
            mean = f"{row['mean_score']:.4f}" if row["mean_score"] is not None else "pending"
            report.append(
                f"| {row['evaluation_metric']} | {row['successful']} | {mean} | {row['evidence_review_required']} |"
            )
    report += [
        "",
        "The user-supplied six steps and five bands for each metric are fixed across all models. "
        "Scoring uses the existing G-Eval factory, question, selected cleaned response, reference answer and judge-side supporting context. "
        "Other model responses and prior scores are excluded. Every score, explanation, evidence-review flag, raw response, "
        "attempt and retry is retained. No additional cleaning, answer generation, dynamic step generation or second normalization occurred. "
        "There is no combined overall score.",
        "",
        "Judge sampling uses the gateway default and is not established deterministic. Imported benchmark evidence is not "
        "new independent verification. User execution permission is not empirical calibration or scientific/team approval.",
        "",
        f"Definition SHA-256: `{plan['extracted_definition_sha256']}`",
        "",
        f"Source Markdown SHA-256: `{plan['source_markdown_sha256']}`",
        "",
        "Files: full_results.xlsx, all_results.*, correctness_results.*, completeness_results.*, metric_summaries.*, "
        "evidence_review_required.*, failures.*, missing_tasks.*, attempts.*, retry_report.*, raw/, records/, sessions/.",
        "",
    ]
    (directory / "full_run_report.md").write_text("\n".join(report), encoding="utf8")


def supervise():
    plan = verify()
    STATE.mkdir(parents=True, exist_ok=True)
    awake = None
    if sys.platform == "win32":
        import ctypes

        awake = ctypes.windll.kernel32.SetThreadExecutionState
        awake(0x80000001)
    try:
        with process_lock(STATE / "supervisor.lock"):
            event("WAITING_FOR_CLEANED_M1_M7_QUEUE")
            prerequisite = ROOT / plan["parent_completion"]
            while not (
                prerequisite.exists()
                and json.loads(prerequisite.read_text(encoding="utf8")).get("successful_all_six")
                == 10884
            ):
                time.sleep(INTERVAL)
            for model in MODELS:
                verify()
                previous = status(model)["successful"]
                stalls = 0
                while previous < 1512:
                    log = STATE / f"{model}_{time.time_ns()}.log"
                    with log.open("w", encoding="utf8") as handle:
                        child = subprocess.Popen(
                            [
                                sys.executable,
                                "-m",
                                "canadianness_eval.general_quality_run",
                                "run",
                                "--model",
                                model,
                            ],
                            cwd=ROOT,
                            stdout=handle,
                            stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NO_WINDOW
                            if sys.platform == "win32"
                            else 0,
                        )
                        write_json(
                            STATE / "active_process.json",
                            dict(
                                model=model,
                                run_id=run_id(model),
                                pid=child.pid,
                                log=str(log),
                                timestamp=now(),
                            ),
                        )
                        event("RUN_STARTED", model=model, pid=child.pid)
                        while True:
                            try:
                                code = child.wait(timeout=INTERVAL)
                                break
                            except subprocess.TimeoutExpired:
                                verify()
                                event("TEN_MINUTE_CHECK", model=model, **status(model))
                    current = status(model)
                    event("RUN_EXIT", model=model, exit_code=code, **current)
                    if code == 0 and current["successful"] == 1512:
                        break
                    verify()
                    text = log.read_text(encoding="utf8", errors="replace")
                    if any(
                        s in text
                        for s in ["Frozen", "mismatch", "Conflicting", "Configured judge changed"]
                    ):
                        raise ValueError("Integrity/configuration stop; inspect " + str(log))
                    stalls = 0 if current["successful"] > previous else stalls + 1
                    previous = current["successful"]
                    if stalls >= 3:
                        raise RuntimeError(
                            "Persistent infrastructure failures; no progress in three recovery attempts"
                        )
                    event("RECOVERY_WAIT", model=model, seconds=INTERVAL)
                    time.sleep(INTERVAL)
                export_model(model, plan)
                event("MODEL_COMPLETED", model=model, successful=1512)
            combined = []
            for model in MODELS:
                combined += read_records(
                    ROOT / "outputs/evaluations" / run_id(model) / "all_results.jsonl"
                )
            table(STATE / "all_three_model_results", combined)
            summaries = []
            for axes in [
                ("evaluated_model", "evaluation_metric"),
                ("evaluated_model", "evaluation_metric", "language"),
            ]:
                groups = defaultdict(list)
                for row in combined:
                    groups[tuple(row[k] for k in axes)].append(row)
                for key, values in sorted(groups.items()):
                    summaries.append(
                        dict(
                            zip(axes, key),
                            grouping="/".join(axes),
                            tasks=len(values),
                            mean_score=sum(r["score"] for r in values) / len(values),
                            evidence_review_required=sum(
                                bool(r["evidence_review_required"]) for r in values
                            ),
                            result_label=LABEL,
                        )
                    )
            table(STATE / "three_model_metric_language_summaries", summaries)
            book = Workbook()
            book.remove(book.active)
            add_sheet(book, "All three model judgments", combined)
            add_sheet(book, "Metric language comparison", summaries)
            groups = defaultdict(dict)
            for row in combined:
                groups[(row["question_id"], row["evaluation_metric"])][row["evaluated_model"]] = row
            matched = []
            for key, values in sorted(groups.items()):
                if set(values) != set(MODELS):
                    raise ValueError("Incomplete model comparison")
                first = values["llama"]
                for row in values.values():
                    for field in [
                        "question",
                        "reference_answer",
                        "reference_context",
                        "language",
                        "metric_definitions_sha256",
                    ]:
                        if row[field] != first[field]:
                            raise ValueError("Comparison evidence mismatch")
                row = dict(
                    question_id=key[0],
                    evaluation_metric=key[1],
                    language=first["language"],
                    question=first["question"],
                    reference_answer=first["reference_answer"],
                    reference_context=first["reference_context"],
                    result_label=LABEL,
                )
                for model, value in values.items():
                    row.update(
                        {
                            model + "_score": value["score"],
                            model + "_reason": value["judge_reason"],
                            model + "_answer": value["model_answer"],
                            model + "_evidence_review_required": value["evidence_review_required"],
                        }
                    )
                matched.append(row)
            table(STATE / "question_metric_model_comparisons", matched)
            add_sheet(book, "Matched model scores", matched)
            book.save(STATE / "three_model_general_quality_results.xlsx")
            write_json(
                STATE / "completion.json",
                dict(status="COMPLETED", successful=4536, failed=0, missing=0, result_label=LABEL),
            )
            event("QUEUE_COMPLETED", successful=4536)
            report = [
                "# Three-model general answer-quality results",
                "",
                LABEL,
                "",
                "Completed 4,536/4,536 evaluations: correctness and completeness for 756 cleaned responses per model. "
                "All models use identical user-supplied definitions, parameters, rubric bands, scorer and judge configuration.",
                "",
                "| Model | Metric | Mean | Evidence review flags |",
                "|---|---|---:|---:|",
            ]
            for row in summaries:
                if row["grouping"] == "evaluated_model/evaluation_metric":
                    report.append(
                        f"| {row['evaluated_model']} | {row['evaluation_metric']} | {row['mean_score']:.4f} | {row['evidence_review_required']} |"
                    )
            report += [
                "",
                "Every individual answer, score, explanation and evidence-review flag is retained, with English/French "
                "and original-topic breakdowns, paired model comparisons and run-level failure/retry/usage reports. "
                "No overall combined Canadian-ness or general-quality score was calculated. Judge defaults, human calibration "
                "and evidence sufficiency remain limitations; execution approval is not scientific or team approval.",
                "",
                f"Definition SHA-256: `{plan['extracted_definition_sha256']}`",
                "",
                f"Source Markdown SHA-256: `{plan['source_markdown_sha256']}`",
                "",
                "Files: three_model_general_quality_results.xlsx, all_three_model_results.*, "
                "three_model_metric_language_summaries.*, question_metric_model_comparisons.*, and each separate evaluation run folder.",
                "",
            ]
            (STATE / "final_report.md").write_text("\n".join(report), encoding="utf8")
            (ROOT / "docs/general_quality_three_model_results.md").write_text(
                "\n".join(report), encoding="utf8"
            )
    except Exception as exc:
        event("SUPERVISOR_STOPPED", error=str(exc))
        raise
    finally:
        if awake:
            awake(0x80000000)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "check", "run", "supervise", "status"])
    parser.add_argument("--model", choices=MODELS)
    args = parser.parse_args()
    if args.command == "prepare":
        p = prepare()
        print("Prepared and execution-authorized:", p["total_tasks"], file_hash(PLAN))
        return 0
    if args.command == "check":
        verify()
        print("GO: user-authorized, unchanged fixed definitions")
        return 0
    if args.command == "status":
        for model in MODELS:
            print(json.dumps(dict(model=model, **status(model))))
        return 0
    if args.command == "run":
        if not args.model:
            parser.error("--model required")
        return execute(args.model)
    supervise()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
