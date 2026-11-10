"""Bounded scheduling around the unchanged fixed-rubric/checkpoint evaluator.

Each isolated question shard uses evaluate_calibration verbatim. Its metric
checkpoints are immediately promoted under a single coordinator lock. Shards
are durable recovery journals, not a second scoring implementation.
"""

import argparse
import json
import threading
import time
import uuid
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

from .api_client import Gateway
from .calibration.evaluate import evaluate_calibration, exclusive_json, read_results
from .calibration.schema import load_cases
from .final_metrics import FINAL_JSON, file_hash
from .hpc_workflow import save_jsonl
from .judge_adapter import RemoteJudge
from .research_exports import export_research_results
from .research_run import LABEL, exclusive, require_approval, verify_plan
from .settings import ROOT, Settings
from .storage import now, write_json
from .verification.db import process_lock


def promote(directory, shard, row, concurrency):
    """Idempotent publication; caller holds the coordinator lock."""
    if not row["applicable"]:
        return False
    raw = row.get("raw_output_file")
    if raw:
        source, target = shard / raw, directory / raw
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if json.loads(source.read_text(encoding="utf8")) != json.loads(
                target.read_text(encoding="utf8")
            ):
                raise ValueError("Conflicting raw checkpoint")
        else:
            exclusive_json(target, json.loads(source.read_text(encoding="utf8")))
    saved = dict(row, evaluation_run_id=directory.name)
    saved["judge_configuration"] = dict(
        row["judge_configuration"],
        concurrency=concurrency,
        execution_engine="concurrent-research-v1",
        scheduling_unit="question; independent metric checkpoints",
    )
    name = (
        Path(raw).name
        if raw
        else next(
            p.name
            for p in (shard / "records").glob("*.json")
            if json.loads(p.read_text(encoding="utf8"))["result_id"] == row["result_id"]
        )
    )
    target = directory / "records" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if json.loads(target.read_text(encoding="utf8")) != saved:
            raise ValueError("Conflicting metric checkpoint")
        return False
    exclusive_json(target, saved)
    with (directory / "calibration_results.jsonl").open("a", encoding="utf8") as handle:
        handle.write(json.dumps(saved, ensure_ascii=False, allow_nan=False) + "\n")
        handle.flush()
    return True


def execute(plan_path, approval_path):
    plan_path, approval_path = Path(plan_path), Path(approval_path)
    plan, approval = require_approval(plan_path, approval_path)
    concurrency = plan["judge"]["concurrency"]
    if plan.get("execution_engine") != "concurrent-research-v1" or concurrency != 4:
        raise ValueError("Explicit four-worker concurrent manifest required")
    settings = Settings.load()
    if (
        settings.base != plan["judge"]["endpoint"]
        or settings.timeout != plan["judge"]["timeout_seconds"]
        or settings.model not in ("auto", plan["judge"]["model"])
    ):
        raise ValueError("Configured judge differs from frozen plan")
    directory = ROOT / plan["run_directory"]
    directory.mkdir(parents=True, exist_ok=True)
    with process_lock(directory / "run.lock"):
        plan, approval = require_approval(plan_path, approval_path)
        session = uuid.uuid4().hex
        metadata = dict(
            phase="FULL_PROVISIONAL_RESEARCH",
            experiment_sha256=file_hash(plan_path),
            execution_approval_sha256=file_hash(approval_path),
            result_label=LABEL,
            scientific_validity_approved=False,
            team_approval=False,
            rubric_empirically_calibrated=False,
            model=plan["evaluated_model"],
            known_scoring_limitations=plan["known_scoring_limitations"],
            execution_engine="concurrent-research-v1",
            concurrency=concurrency,
        )
        manifest = dict(
            run_id=plan["run_id"],
            run_metadata=metadata,
            judge_configuration=plan["judge"],
            dataset_hash=plan["dataset_hash"],
        )
        manifest_path = directory / "manifest.json"
        if manifest_path.exists():
            if json.loads(manifest_path.read_text(encoding="utf8")) != manifest:
                raise ValueError("Resume manifest mismatch")
        else:
            exclusive(manifest_path, manifest)
        lock = threading.Lock()
        stop = threading.Event()
        scheduling = {"next_start": 0.0, "failures": 0, "completed": 0, "http_attempts": 0}
        input_stats = {
            p: ((ROOT / p).stat().st_size, (ROOT / p).stat().st_mtime_ns)
            for p in plan["input_sha256"]
        }

        def integrity():
            for p, expected in plan["software_sha256"].items():
                if file_hash(ROOT / p) != expected:
                    stop.set()
                    raise ValueError("Execution software changed: " + p)
            for p, expected in input_stats.items():
                info = (ROOT / p).stat()
                if (info.st_size, info.st_mtime_ns) != expected:
                    stop.set()
                    raise ValueError("Frozen input changed: " + p)
            if (
                file_hash(plan_path) != metadata["experiment_sha256"]
                or file_hash(approval_path) != metadata["execution_approval_sha256"]
            ):
                stop.set()
                raise ValueError("Manifest or authorization changed")

        def guard():
            while True:
                if stop.is_set():
                    raise RuntimeError("Shared execution stop; resume missing/failed tasks")
                with lock:
                    integrity()
                    delay = scheduling["next_start"] - time.monotonic()
                    if delay <= 0:
                        scheduling["next_start"] = (
                            time.monotonic() + plan["judge"]["min_seconds_between_task_starts"]
                        )
                        return
                stop.wait(min(delay, 0.25))

        def shared_retry_sleep(seconds):
            with lock:
                scheduling["next_start"] = max(scheduling["next_start"], time.monotonic() + seconds)
            if stop.wait(seconds):
                raise RuntimeError("Shared execution stop during retry cooldown")

        def worker(case):
            shard = directory / "shards" / case.question_id
            input_path = shard / "case.jsonl"
            save_jsonl(input_path, [case.model_dump()])
            gateway = Gateway(settings, sleep=shared_retry_sleep)
            gateway.model_id = plan["judge"]["model"]

            def checkpoint(row):
                with lock:
                    promote(directory, shard, row, concurrency)
                    scheduling["completed"] += 1
                    scheduling["failures"] = (
                        scheduling["failures"] + 1 if row["status"] == "FAILED" else 0
                    )
                    gateway.history.clear()
                    write_json(
                        directory / "progress.json",
                        dict(
                            run_id=plan["run_id"],
                            session=session,
                            completed_this_session=scheduling["completed"],
                            last_question_id=row["question_id"],
                            last_metric=row["metric_id"],
                            last_status=row["status"],
                            timestamp=now(),
                            concurrency=concurrency,
                            result_label=LABEL,
                        ),
                    )
                    error = row.get("error") or ""
                    if (
                        gateway.auth_failed
                        or "HTTP 429" in error
                        or "Rate limit requests" in error
                        or scheduling["failures"]
                        >= plan["judge"]["stop_after_consecutive_failed_tasks"]
                    ):
                        stop.set()
                        raise RuntimeError("Shared infrastructure stop after durable checkpoint")

            try:
                return evaluate_calibration(
                    input_path,
                    RemoteJudge(gateway),
                    shard,
                    config_path=FINAL_JSON,
                    repeats=1,
                    resume=True,
                    retry_failures=True,
                    run_metadata=metadata,
                    execution_guard=guard,
                    checkpoint_callback=checkpoint,
                )
            finally:
                if gateway.history:
                    write_json(
                        directory
                        / "sessions"
                        / f"{session}_{case.question_id}_uncheckpointed_events.json",
                        gateway.history,
                    )
                with lock:
                    scheduling["http_attempts"] += gateway.attempts
                gateway.close()

        started = now()
        failure = None
        discovery = Gateway(settings)
        try:
            integrity()
            discovery.discover()
            if discovery.model_id != plan["judge"]["model"]:
                raise ValueError("Judge discovery identity mismatch")
            write_json(directory / "sessions" / f"{session}_discovery.json", discovery.history)
            # Recover a crash between shard commit and coordinator publication before scheduling.
            for shard in (directory / "shards").glob("*"):
                for path in sorted((shard / "records").glob("*.json")):
                    promote(
                        directory, shard, json.loads(path.read_text(encoding="utf8")), concurrency
                    )
            checkpoint_rows = [
                json.loads(p.read_text(encoding="utf8"))
                for p in sorted((directory / "records").glob("*.json"))
            ]
            # JSONL is a derived journal; immutable metric checkpoints are authoritative.
            (directory / "calibration_results.jsonl").write_text(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in checkpoint_rows),
                encoding="utf8",
            )
            latest = {(r["question_id"], r["metric_id"]): r for r in read_results(directory)}
            pending = iter(
                c
                for c in load_cases(ROOT / plan["cases_path"])
                if any(
                    latest.get((c.question_id, m), {}).get("status") != "SUCCESS"
                    for m in c.applicable_metrics
                )
            )
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                active = set()
                for _ in range(concurrency):
                    case = next(pending, None)
                    if case is not None:
                        active.add(pool.submit(worker, case))
                while active:
                    done, active = wait(active, return_when=FIRST_COMPLETED)
                    for future in done:
                        try:
                            future.result()
                        except Exception:
                            stop.set()
                            raise
                        if not stop.is_set():
                            case = next(pending, None)
                            if case is not None:
                                active.add(pool.submit(worker, case))
        except Exception as exc:
            stop.set()
            failure = discovery.safe_error(exc)
        finally:
            discovery.close()
            write_json(
                directory / "sessions" / f"{session}.json",
                dict(
                    started=started,
                    ended=now(),
                    outcome="STOPPED_WITH_ERROR" if failure else "COMPLETED_ENGINE_PASS",
                    error=failure,
                    completed_this_session=scheduling["completed"],
                    http_attempts=scheduling["http_attempts"] + discovery.attempts,
                    concurrency=concurrency,
                    approval_sha256=metadata["execution_approval_sha256"],
                    result_label=LABEL,
                ),
            )
            export_research_results(directory, plan)
        verify_plan(plan_path)
        successes = sum(
            r["status"] == "SUCCESS" for r in read_results(directory) if r["applicable"]
        )
        print(
            f"{plan['run_id']}: {successes}/{plan['task_count']} successful; error={failure}",
            flush=True,
        )
        return 0 if successes == plan["task_count"] and failure is None else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--approval", required=True)
    args = parser.parse_args()
    return execute(args.plan, args.approval)


if __name__ == "__main__":
    raise SystemExit(main())
