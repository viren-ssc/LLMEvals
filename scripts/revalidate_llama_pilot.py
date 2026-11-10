"""One blinded, versioned revalidation of the existing 22-evaluation Llama pilot."""

import argparse
import csv
import json
import sys
from pathlib import Path

from canadianness_eval.api_client import Gateway
from canadianness_eval.calibration.factory import INTERPRETATION_PATH, template_metadata
from canadianness_eval.calibration.schema import load_cases
from canadianness_eval.evaluation_runner import evaluate_hpc_pilot
from canadianness_eval.final_metrics import FINAL_JSON, file_hash, load_final
from canadianness_eval.hpc_workflow import (
    EXPECTED_RUBRIC_HASH,
    PREPARED,
    RUN,
    audit_requests,
    export_reports,
    write_review_workbook,
)
from canadianness_eval.judge_adapter import RemoteJudge
from canadianness_eval.settings import ROOT, Settings
from canadianness_eval.storage import write_json

DESTINATION = ROOT / "outputs/evaluations/llama_pilot_20261106_v2"


def ledger():
    return {str(p.relative_to(ROOT)): file_hash(p) for p in RUN.rglob("*") if p.is_file()}


def compare():
    old = [
        json.loads(s)
        for s in (RUN / "question_scores.jsonl").read_text(encoding="utf8").splitlines()
    ]
    new = [
        json.loads(s)
        for s in (DESTINATION / "question_scores.jsonl").read_text(encoding="utf8").splitlines()
    ]

    def key(r):
        return r["question_id"], r["evaluated_model"], r["evaluation_metric"]

    baseline = {key(r): r for r in old}
    assert len(new) == len({key(r) for r in new}) == 22 and {key(r) for r in new} == set(baseline)
    comparison = []
    for row in new:
        prior = baseline[key(row)]
        comparison.append(
            dict(
                question_id=row["question_id"],
                evaluated_model=row["evaluated_model"],
                language=row["language"],
                evaluation_metric=row["evaluation_metric"],
                metric_role=row["metric_role"],
                old_score=prior["score"],
                new_score=row["score"],
                delta=row["score"] - prior["score"] if row["score"] is not None else None,
                old_reason=prior["judge_reason"],
                new_reason=row["judge_reason"],
                status=row["status"],
            )
        )
    write_json(DESTINATION / "comparison.json", comparison)
    with (DESTINATION / "comparison.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(comparison[0]))
        writer.writeheader()
        writer.writerows(comparison)
    return comparison


def run(resume=False):
    DESTINATION.mkdir(parents=True, exist_ok=True)
    ledger_path = DESTINATION / "baseline_integrity_ledger.json"
    if ledger_path.exists():
        expected = json.loads(ledger_path.read_text(encoding="utf8"))
        assert ledger() == expected, "Baseline changed"
    else:
        expected = ledger()
        write_json(ledger_path, expected)
    prepared = json.loads((PREPARED / "preparation.json").read_text(encoding="utf8"))
    original = json.loads((RUN / "manifest.json").read_text(encoding="utf8"))
    assert file_hash(FINAL_JSON) == EXPECTED_RUBRIC_HASH == original["metric_json_sha256"]
    from canadianness_eval.calibration.schema import dataset_hash

    cases = load_cases(PREPARED / "pilot_cases.jsonl")
    assert dataset_hash(cases) == original["dataset_hash"]
    metadata = {
        k: v
        for k, v in prepared.items()
        if k
        not in ("question_count", "metric_evaluations", "pilot_question_ids", "pilot_evaluations")
    }
    metadata.update(
        phase="PILOT_PROVISIONAL",
        revalidation="One full 22-evaluation pilot, fresh blinded judging",
        **template_metadata(),
    )
    snapshot = DESTINATION / "evaluator_snapshot"
    snapshot.mkdir(exist_ok=True)
    from canadianness_eval.calibration import factory

    for source, name in (
        (Path(factory.__file__), "factory_v2.py"),
        (INTERPRETATION_PATH, "scoring_interpretation_v2.txt"),
    ):
        target = snapshot / name
        if target.exists():
            assert target.read_bytes() == source.read_bytes()
        else:
            target.write_bytes(source.read_bytes())
    settings = Settings.load()
    assert settings.base == original["judge_configuration"]["endpoint"]
    assert settings.timeout == original["judge_configuration"]["timeout_seconds"]
    gateway = Gateway(settings)
    try:
        gateway.discover()
        assert gateway.model_id == original["judge_model"]
        discovery_attempts = gateway.attempts
        judge = RemoteJudge(gateway)
        evaluate_hpc_pilot(
            PREPARED / "pilot_cases.jsonl",
            judge,
            DESTINATION,
            config_path=FINAL_JSON,
            run_metadata=metadata,
            resume=resume,
        )
        calls = gateway.attempts
        before = {p.name: file_hash(p) for p in (DESTINATION / "records").glob("*.json")}
        evaluate_hpc_pilot(
            PREPARED / "pilot_cases.jsonl",
            judge,
            DESTINATION,
            config_path=FINAL_JSON,
            run_metadata=metadata,
            resume=True,
        )
        after = {p.name: file_hash(p) for p in (DESTINATION / "records").glob("*.json")}
        assert calls == gateway.attempts and before == after
        write_json(
            DESTINATION / "resume_check.json",
            dict(passed=True, extra_http_attempts=0, checkpoint_files_unchanged=True),
        )
        audit = audit_requests(DESTINATION, cases, load_final())
        stats = export_reports(DESTINATION)
        write_review_workbook(DESTINATION)
        comparison = compare()
        # Inspect actual saved requests: no baseline judgments or review notes entered prompts.
        past_reasons = [r["old_reason"] for r in comparison]
        instruction = INTERPRETATION_PATH.read_text(encoding="utf-8-sig")
        isolated = []
        for path in (DESTINATION / "raw").glob("*.json"):
            for response in json.loads(path.read_text(encoding="utf8"))["responses"]:
                body = response["request_body"]
                prompt = body["messages"][0]["content"]
                isolated.append(
                    instruction in prompt
                    and all(reason not in prompt for reason in past_reasons)
                    and set(body["response_format"]["json_schema"]["schema"]["properties"])
                    == {"score", "reason"}
                )
        assert ledger() == expected
        assert file_hash(FINAL_JSON) == EXPECTED_RUBRIC_HASH
        passed = (
            audit["passed"]
            and len(isolated) == 22
            and all(isolated)
            and stats["successes"] == 22
            and stats["errors"] == 0
        )
        acceptance = dict(
            technical_passed=passed,
            scoring_quality_review_pending=True,
            rubric_sha256=EXPECTED_RUBRIC_HASH,
            **template_metadata(),
            session_http_attempts=gateway.attempts,
            discovery_http_attempts=discovery_attempts,
            session_scoring_http_attempts=calls - discovery_attempts,
            baseline_unchanged=True,
            dataset_unchanged=True,
            no_prior_judgments_in_requests=all(isolated),
            full_run_started=False,
            human_approval_gate_unchanged=True,
        )
        write_json(DESTINATION / "revalidation_acceptance.json", acceptance)
        print(json.dumps(dict(**acceptance, statistics=stats), indent=2))
        return 0 if passed else 1
    finally:
        gateway.close()
        assert ledger() == expected, "Original pilot baseline changed"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    sys.exit(run(args.resume))
