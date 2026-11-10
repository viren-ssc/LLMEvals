import json

import httpx
import pytest
from deepeval.metrics.g_eval import GEvalTemplate

from canadianness_eval.calibration.evaluate import read_results
from canadianness_eval.calibration.schema import CalibrationCase, EvidenceReview
from canadianness_eval.evaluation_runner import evaluate_hpc_pilot
from canadianness_eval.final_metrics import FINAL_JSON, load_final
from canadianness_eval.hpc_workflow import (
    audit_requests,
    export_reports,
    save_jsonl,
    write_review_workbook,
)
from canadianness_eval.judge_adapter import RemoteJudge

META = {"phase": "PILOT_PROVISIONAL", "evidence_attestation": "Synthetic test only"}


def cases():
    return [
        CalibrationCase(
            question_id=f"test-{mid}",
            question=f"QUESTION {mid}: What is required?",
            model_answer=f"LLAMA ANSWER {mid}",
            reference_answer=f"REFERENCE {mid}",
            reference_context=[f"SUPPORTING SUMMARY {mid}: Canada's text.\nNot a quotation."],
            applicable_metrics=[mid],
            primary_metric=mid,
            secondary_metrics=[],
            model_variant="llama",
            dataset_version="test-only",
            case_family="fixture",
            language="fr" if i % 2 else "en",
            expected_behavior="test",
            evidence_review=EvidenceReview(
                status="verified",
                reference_answer_verified=True,
                sufficient_for_metrics=[mid],
                verified_by="fixture only",
                verification_date="2026-11-06",
                source_ids=["fixture"],
            ),
        )
        for i, mid in enumerate([f"M{n}" for n in range(1, 8)])
    ]


def run(path, judge, directory, **kwargs):
    return evaluate_hpc_pilot(
        path, judge, directory, config_path=FINAL_JSON, run_metadata=META, **kwargs
    )


def test_fixed_seven_metric_payloads_and_resume(gateway_factory, tmp_path, monkeypatch):
    def no_generation(**kwargs):
        pytest.fail("Dynamic step generation forbidden")

    monkeypatch.setattr(GEvalTemplate, "generate_evaluation_steps", no_generation)
    data = tmp_path / "cases.jsonl"
    examples = cases()
    # Preserve two applicable metric assignments on one answer.
    examples[2].secondary_metrics = ["M6"]
    examples[2].applicable_metrics = ["M3", "M6"]
    examples[2].evidence_review.sufficient_for_metrics = ["M3", "M6"]
    save_jsonl(data, [c.model_dump() for c in examples])
    gateway = gateway_factory(
        lambda _: httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"score":8,"reason":"Complete synthetic evaluation"}'}}
                ]
            },
        )
    )
    directory = tmp_path / "run"
    rows = run(data, RemoteJudge(gateway), directory)
    scored = [r for r in rows if r["applicable"]]
    assert len(scored) == 8 and all(r["score"] == 0.8 for r in scored)
    assert all(r["evaluated_model"] == "llama" and r["provisional"] for r in scored)
    assert {r["metric_role"] for r in scored} == {"primary", "secondary"}
    assert audit_requests(directory, examples, load_final())["passed"]
    original = {p.name: p.read_bytes() for p in (directory / "records").glob("*.json")}
    run(data, RemoteJudge(gateway), directory, resume=True)
    assert gateway.attempts == 8
    assert original == {p.name: p.read_bytes() for p in (directory / "records").glob("*.json")}
    report = export_reports(directory)
    assert report["successes"] == 8
    exported = [
        json.loads(s)
        for s in (directory / "question_scores.jsonl").read_text(encoding="utf8").splitlines()
    ]
    assert len(exported) == 8 and all(r["judge_reason"] for r in exported)
    assert (directory / "metric_summaries.csv").exists()
    write_review_workbook(directory, data)
    from openpyxl import load_workbook

    book = load_workbook(directory / "pilot_review.xlsx", read_only=True)
    assert book["Individual scores"].max_row == 9
    assert book["Fixed steps and rubrics"].max_row == 78
    book.close()


def test_failed_call_resumes_and_repairs_torn_log(gateway_factory, tmp_path):
    available = False

    def handler(_):
        if not available:
            return httpx.Response(503)
        return httpx.Response(
            200, json={"choices": [{"message": {"content": '{"score":7,"reason":"Recovered"}'}}]}
        )

    gateway = gateway_factory(handler)
    data = tmp_path / "cases.jsonl"
    save_jsonl(data, [cases()[5].model_dump()])
    directory = tmp_path / "run"
    run(data, RemoteJudge(gateway), directory)
    assert next(r for r in read_results(directory) if r["applicable"])["status"] == "FAILED"
    assert gateway.attempts == 3
    (directory / "calibration_results.jsonl").write_text('{"torn', encoding="utf8")
    available = True
    run(data, RemoteJudge(gateway), directory, resume=True, retry_failures=True)
    scored = next(r for r in read_results(directory) if r["applicable"])
    assert scored["attempt"] == 2 and scored["score"] == 0.7 and gateway.attempts == 4
    attempts = [json.loads(p.read_text()) for p in (directory / "records").glob("*.json")]
    assert len([r for r in attempts if r["applicable"]]) == 2
    log = [
        json.loads(s) for s in (directory / "calibration_results.jsonl").read_text().splitlines()
    ]
    assert len(log) == len(attempts) and len({r["result_id"] for r in log}) == len(log)
    run(data, RemoteJudge(gateway), directory, resume=True)
    assert gateway.attempts == 4
    stats = export_reports(directory)
    assert stats["successes"] == 1 and stats["failed_evaluation_attempts"] == 1
    assert stats["scoring_http_attempts"] == 4
    # Input signature changes cannot reuse prior success.
    changed = cases()[5]
    changed.model_answer = "Changed answer"
    new_data = tmp_path / "changed.jsonl"
    save_jsonl(new_data, [changed.model_dump()])
    with pytest.raises(ValueError, match="manifest mismatch"):
        run(new_data, RemoteJudge(gateway), directory, resume=True)


def test_full_run_cannot_enter_pilot_path(gateway_factory, tmp_path):
    data = tmp_path / "cases.jsonl"
    save_jsonl(data, [cases()[0].model_dump()])
    gateway = gateway_factory(lambda _: pytest.fail("No request permitted"))
    with pytest.raises(ValueError, match="bounded provisional"):
        evaluate_hpc_pilot(
            data,
            RemoteJudge(gateway),
            tmp_path / "full",
            config_path=FINAL_JSON,
            run_metadata={"phase": "FULL"},
        )


def test_versioned_clarification_is_generic_and_invalidates_resume(
    gateway_factory, tmp_path, monkeypatch
):
    from canadianness_eval.calibration import factory

    text = factory.INTERPRETATION_PATH.read_text(encoding="utf-8-sig")
    assert all(qid not in text for qid in ["CA-XP-20261103-192", "CA-EXP-037", "CA-EXP2-059"])
    received = []

    def handler(request):
        received.append(json.loads(request.content)["messages"][0]["content"])
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"score":6,"reason":"Specific omission under current metric"}'
                        }
                    }
                ]
            },
        )

    gateway = gateway_factory(handler)
    data = tmp_path / "cases.jsonl"
    save_jsonl(data, [cases()[0].model_dump()])
    directory = tmp_path / "run"
    run(data, RemoteJudge(gateway), directory)
    assert text in received[0]
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf8"))
    assert manifest["judge_configuration"]["evaluator_template_version"] == "final-json-factory-v2"
    assert len(manifest["judge_configuration"]["evaluator_template_sha256"]) == 64
    changed = tmp_path / "clarification.txt"
    changed.write_text(text + "\nChanged interpretation", encoding="utf8")
    monkeypatch.setattr(factory, "INTERPRETATION_PATH", changed)
    with pytest.raises(ValueError, match="manifest mismatch"):
        run(data, RemoteJudge(gateway), directory, resume=True)
    assert gateway.attempts == 1
