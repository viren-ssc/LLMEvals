import json
import time
from pathlib import Path

from deepeval.metrics import GEval
from deepeval.metrics.g_eval import Rubric
from deepeval.test_case import LLMTestCase, SingleTurnParams

from .dataset import load_dataset
from .freeze_metrics import load_frozen
from .storage import digest, now, versions, write_json


def evaluate_hpc_pilot(
    input_path, judge, directory, *, config_path, run_metadata, resume=False, retry_failures=False
):
    """Explicit provisional pilot; reuse the final-rubric checkpoint engine.

    Does not change the legacy frozen production gate or permit a full dataset run.
    """
    from .calibration.evaluate import evaluate_calibration
    from .calibration.schema import load_cases
    from .verification.db import process_lock

    cases = load_cases(input_path)
    if (
        run_metadata.get("phase") != "PILOT_PROVISIONAL"
        or len(cases) > 20
        or sum(len(c.applicable_metrics) for c in cases) > 60
    ):
        raise ValueError("Only a bounded provisional HPC pilot is authorized by this entry point")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with process_lock(directory / "run.lock"):
        return evaluate_calibration(
            input_path,
            judge,
            directory,
            config_path=config_path,
            repeats=1,
            resume=resume,
            retry_failures=retry_failures,
            run_metadata=run_metadata,
        )


def make_metric(definition, judge):
    return GEval(
        name=definition["metric_name"],
        evaluation_steps=definition["evaluation_steps"] + [definition["rubric_guidance"]],
        evaluation_params=[SingleTurnParams[x] for x in definition["evaluation_params"]],
        rubric=[
            Rubric(score_range=tuple(b["score_range"]), expected_outcome=b["description"])
            for b in definition["rubric"]
        ],
        model=judge,
        async_mode=False,
        threshold=None,
    )


def test_case(case, definition):
    for field in definition["required_evidence"]:
        if not getattr(case, field):
            raise ValueError("Missing approved evidence field: " + field)
    # Populate ONLY fields explicitly approved in evaluation_params.
    mapping = {
        "INPUT": ("input", case.question),
        "ACTUAL_OUTPUT": ("actual_output", case.model_answer),
        "EXPECTED_OUTPUT": ("expected_output", case.reference_answer),
        "CONTEXT": ("context", case.reference_context),
    }
    return LLMTestCase(**{mapping[p][0]: mapping[p][1] for p in definition["evaluation_params"]})


def evaluate(input_path, frozen_path, judge, output_path, resume=True):
    config = load_frozen(frozen_path)
    cases = load_dataset(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "configuration_hash": config["configuration_hash"],
        "judge_model": judge.get_model_name(),
        "dataset_hash": digest([c.model_dump() for c in cases]),
        "package_versions": versions(),
    }
    manifest_path = output_path.with_suffix(".manifest.json")
    previous = {}
    if output_path.exists():
        if (
            not resume
            or not manifest_path.exists()
            or json.loads(manifest_path.read_text()) != manifest
        ):
            raise ValueError(
                "Existing evaluation output belongs to different inputs; choose a new output path"
            )
        for line in output_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            previous[(row["question_id"], row["model_variant"], row["metric_id"])] = row
    else:
        write_json(manifest_path, manifest)
    rows = []
    for case in cases:
        for definition in config["metrics"]:
            mid = definition["metric_id"]
            key = (case.question_id, case.model_variant, mid)
            if key in previous and previous[key]["status"] in ("success", "not_applicable"):
                rows.append(previous[key])
                continue
            row = dict(
                question_id=case.question_id,
                model_variant=case.model_variant,
                metric_id=mid,
                metric_name=definition["metric_name"],
                score=None,
                reason=None,
                judge_model=judge.get_model_name(),
                rubric_version=config["rubric_version"],
                configuration_hash=config["configuration_hash"],
                timestamp=now(),
                reference_ids=case.reference_ids,
                source_urls=case.source_urls,
                provenance=case.provenance,
                illustrative=case.illustrative,
                applicable=mid in case.applicable_metrics,
                status="not_applicable",
                error=None,
                latency_seconds=0,
                judge_configuration={"sampling": "gateway default", "logprobs": False},
            )
            start = time.perf_counter()
            before = judge.gateway.attempts
            if row["applicable"]:
                try:
                    tc = test_case(case, definition)
                    metric = make_metric(definition, judge)
                    metric.measure(tc)
                    score = float(metric.score)
                    if not 0 <= score <= 1:
                        raise ValueError("GEval normalized score outside [0,1]")
                    row.update(score=score, reason=metric.reason, status="success")
                except Exception as exc:
                    row.update(status="failed", error=judge.gateway.safe_error(exc))
            row["latency_seconds"] = time.perf_counter() - start
            row["attempt_count"] = judge.gateway.attempts - before
            row["judge_configuration"]["structured_mode"] = judge.gateway.structured_mode
            with output_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            rows.append(row)
            print(f"{case.question_id} {mid}: {row['status']}", flush=True)
    return rows
