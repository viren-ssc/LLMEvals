"""Sequential, checkpointed calibration. Existing experiment directories are immutable by default."""

import json
import re
import time
import uuid
from pathlib import Path

from ..final_metrics import FINAL_JSON, file_hash, load_final
from ..storage import digest, now, versions, write_json
from .factory import (
    FACTORY_VERSION,
    SCORING_METHOD,
    judge_case,
    make_final_metric,
    normalized_score,
    template_metadata,
)
from .schema import dataset_hash, evidence_readiness, load_cases


def exclusive_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # A unique completed checkpoint is atomically published. Never replace another attempt.
    if path.exists():
        raise ValueError("Checkpoint already exists")
    write_json(path, value)


def artifact_ledger(root):
    paths = []
    for directory in (
        "outputs/generations",
        "outputs/pilot",
        "outputs/consolidated",
        "review",
        "data/examples",
    ):
        paths += [
            p for p in (root / directory).rglob("*") if p.is_file() and p.suffix not in (".tmp",)
        ]
    paths += [
        root / "Canadianness_Final_GEVAL_Metrics.json",
        root / "Canadianness_Final_GEVAL_Evaluation_Steps.xlsx",
    ]
    return {str(p.relative_to(root)): file_hash(p) for p in sorted(paths) if p.exists()}


def verify_ledger(root, ledger):
    changes = [
        path
        for path, expected in ledger.items()
        if not (root / path).exists() or file_hash(root / path) != expected
    ]
    if changes:
        raise ValueError("Prior artifact changed: " + ", ".join(changes))
    return True


def create_run(directory, *, resume=False):
    directory = Path(directory)
    if directory.exists() and not resume:
        raise ValueError("Run directory exists. Use --resume explicitly or a new --run-id.")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def evaluate_calibration(
    input_path,
    judge,
    directory,
    *,
    config_path=FINAL_JSON,
    repeats=3,
    resume=False,
    retry_failures=False,
    unavailable_reason=None,
    run_metadata=None,
    execution_guard=None,
    checkpoint_callback=None,
):
    if not 1 <= repeats <= 5:
        raise ValueError("Calibration repeats must be between 1 and 5")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    config, cases = load_final(config_path), load_cases(input_path)
    settings = {
        "sampling": "gateway default; determinism not established",
        "concurrency": 1,
        "logprobs_requested": False,
        "factory_version": FACTORY_VERSION,
        **template_metadata(),
        "endpoint": judge.gateway.settings.base if judge else None,
        "timeout_seconds": judge.gateway.settings.timeout if judge else None,
    }
    manifest = dict(
        run_id=directory.name,
        metric_version=config.version,
        metric_json_sha256=file_hash(config_path),
        dataset_hash=dataset_hash(cases),
        dataset_versions=sorted({c.dataset_version for c in cases}),
        repeats=repeats,
        judge_model=judge.get_model_name() if judge else None,
        judge_configuration=settings,
        package_versions=versions(),
        research_state="CALIBRATION_NOT_FROZEN",
        applicability={c.question_id: c.applicable_metrics for c in cases},
    )
    if run_metadata is not None:
        manifest["run_metadata"] = run_metadata
    manifest_path = directory / "manifest.json"
    if manifest_path.exists():
        if not resume or json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
            raise ValueError(
                "Resume manifest mismatch; configuration, dataset, judge and settings must match"
            )
    else:
        exclusive_json(manifest_path, manifest)
    checkpoints = directory / "records"
    checkpoints.mkdir(exist_ok=True)
    latest = {}
    for path in sorted(checkpoints.glob("*.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        key = (row["question_id"], row["model_variant"], row["metric_id"], row["repeat"])
        if key not in latest or row["attempt"] > latest[key]["attempt"]:
            latest[key] = row
    results_path = directory / "calibration_results.jsonl"
    if not results_path.exists():
        results_path.touch()
    if resume:
        checkpoint_rows = [
            json.loads(p.read_text(encoding="utf-8")) for p in sorted(checkpoints.glob("*.json"))
        ]
        existing_text = results_path.read_text(encoding="utf-8")
        try:
            existing_rows = [
                json.loads(line) for line in existing_text.splitlines() if line.strip()
            ]
            consistent = len(existing_rows) == len(checkpoint_rows) and {
                r["result_id"] for r in existing_rows
            } == {r["result_id"] for r in checkpoint_rows}
        except (ValueError, KeyError):
            consistent = False
        if not consistent:
            backup = directory / f"interrupted_results_{time.time_ns()}.jsonl"
            backup.write_text(existing_text, encoding="utf-8")
            results_path.write_text(
                "\n".join(json.dumps(r, ensure_ascii=False) for r in checkpoint_rows)
                + ("\n" if checkpoint_rows else ""),
                encoding="utf-8",
            )
    for repeat in range(1, repeats + 1):
        for case in cases:
            for definition in config.metrics:
                mid = definition.metric_id
                key = (case.question_id, case.model_variant, mid, repeat)
                prior = latest.get(key)
                if prior and not (
                    retry_failures and prior["status"] in ("FAILED", "SKIPPED_GATEWAY_UNAVAILABLE")
                ):
                    continue
                if execution_guard is not None and mid in case.applicable_metrics:
                    execution_guard()
                attempt = prior["attempt"] + 1 if prior else 1
                token = digest(list(key))[:20] + f"_attempt_{attempt:03}"
                while (directory / "raw" / (token + ".json")).exists() or (
                    checkpoints / (token + ".json")
                ).exists():
                    attempt += (
                        1  # Preserve an orphan raw file left by an interrupted checkpoint write.
                    )
                    token = digest(list(key))[:20] + f"_attempt_{attempt:03}"
                row = dict(
                    question_id=case.question_id,
                    model_variant=case.model_variant,
                    metric_id=mid,
                    metric_name=definition.name,
                    repeat=repeat,
                    attempt=attempt,
                    evaluation_run_id=directory.name,
                    result_id=uuid.uuid4().hex,
                    metric_version=config.version,
                    metric_json_sha256=manifest["metric_json_sha256"],
                    dataset_version=case.dataset_version,
                    case_family=case.case_family,
                    judge_model=manifest["judge_model"],
                    judge_configuration=settings.copy(),
                    package_versions=manifest["package_versions"],
                    timestamp=now(),
                    research_state="CALIBRATION_NOT_FROZEN",
                    synthetic=case.synthetic,
                    applicable=mid in case.applicable_metrics,
                    metric_role="primary"
                    if mid == case.primary_metric
                    else "secondary"
                    if mid in case.secondary_metrics
                    else None,
                    deepeval_score=None,
                    normalized_score=None,
                    score=None,
                    reason=None,
                    scoring_method=SCORING_METHOD,
                    applicable_rubric=[b.model_dump() for b in definition.rubric_0_to_10],
                    evidence_status="NOT_REQUIRED",
                    evidence_review=case.evidence_review.model_dump(),
                    error=None,
                    skipped_reason=None,
                    status="NOT_APPLICABLE",
                    latency_seconds=0,
                    request_attempts=0,
                    raw_output_file=None,
                    intended_score_range=case.intended_score_ranges.get(mid),
                    expected_behavior=case.expected_behavior,
                )
                if run_metadata is not None:
                    row.update(
                        language=case.language,
                        primary_metric=case.primary_metric,
                        evaluated_model=case.model_variant,
                        evaluation_metric=mid,
                        rubric_version=config.version,
                        evaluation_steps_version=config.version,
                        provisional=True,
                        run_metadata=run_metadata,
                    )
                    if "result_label" in run_metadata:
                        row["result_label"] = run_metadata["result_label"]
                if row["applicable"]:
                    ready, evidence_status, why = evidence_readiness(case, definition)
                    row["evidence_status"] = evidence_status
                    if not ready:
                        row.update(status="NOT_READY_FOR_FACTUAL_EVALUATION", skipped_reason=why)
                    elif judge is None:
                        row.update(
                            status="SKIPPED_GATEWAY_UNAVAILABLE",
                            skipped_reason=unavailable_reason or "Gateway unavailable",
                        )
                    else:
                        offset, before = len(judge.gateway.history), judge.gateway.attempts
                        start = time.perf_counter()
                        try:
                            metric = make_final_metric(definition, judge)
                            measured = metric.measure(
                                judge_case(case, definition), _show_indicator=False
                            )
                            if not isinstance(metric.reason, str) or not metric.reason.strip():
                                raise ValueError("Judge returned no explanation")
                            import math

                            row["deepeval_score"] = (
                                measured if math.isfinite(float(measured)) else str(measured)
                            )
                            row.update(
                                deepeval_score=measured,
                                normalized_score=normalized_score(measured),
                                score=normalized_score(measured),
                                reason=metric.reason,
                                status="SUCCESS",
                            )
                        except Exception as exc:
                            row.update(status="FAILED", error=judge.gateway.safe_error(exc))
                        raw_file = directory / "raw" / (token + ".json")
                        exclusive_json(
                            raw_file,
                            {
                                "result_id": row["result_id"],
                                "responses": judge.gateway.history[offset:],
                            },
                        )
                        row.update(
                            latency_seconds=time.perf_counter() - start,
                            request_attempts=judge.gateway.attempts - before,
                            raw_output_file=str(raw_file.relative_to(directory)),
                        )
                        row["judge_configuration"]["structured_mode"] = (
                            judge.gateway.structured_mode
                        )
                row["completion_timestamp"] = now()
                exclusive_json(checkpoints / (token + ".json"), row)
                with results_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                latest[key] = row
                if row["applicable"]:
                    print(
                        f"{directory.name} repeat {repeat}/{repeats} {case.question_id} {mid}: {row['status']} score={row['score']}",
                        flush=True,
                    )
                    if checkpoint_callback is not None:
                        checkpoint_callback(row)
    rows = list(latest.values())
    counts = {
        status: sum(r["status"] == status for r in rows)
        for status in sorted({r["status"] for r in rows})
    }
    write_json(
        directory / "run_summary.json",
        dict(
            planned=len(cases) * 7 * repeats,
            saved=len(rows),
            attempted=sum(r["request_attempts"] > 0 for r in rows),
            request_attempts=sum(r["request_attempts"] for r in rows),
            counts=counts,
            research_state="CALIBRATION_NOT_FROZEN",
        ),
    )
    return rows


def read_results(directory):
    rows = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in (Path(directory) / "records").glob("*.json")
    ]
    latest = {}
    for row in rows:
        key = row["question_id"], row["model_variant"], row["metric_id"], row["repeat"]
        if key not in latest or latest[key]["attempt"] < row["attempt"]:
            latest[key] = row
    return list(latest.values())


def safe_run_id(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,90}", value) or ".." in value:
        raise ValueError("Run ID must be a simple unique identifier, not a path")
    return value
