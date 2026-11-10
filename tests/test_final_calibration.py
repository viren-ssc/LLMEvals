import json

import httpx
import pytest
from openpyxl import load_workbook
from test_gateway import completion

from canadianness_eval.calibration.evaluate import (
    artifact_ledger,
    evaluate_calibration,
    read_results,
    verify_ledger,
)
from canadianness_eval.calibration.factory import make_final_metric, normalized_score
from canadianness_eval.calibration.pilot_cases import build_cases
from canadianness_eval.calibration.reports import compare_humans, generate_reports, variability
from canadianness_eval.calibration.schema import closed_book_messages, evidence_readiness
from canadianness_eval.final_metrics import (
    FINAL_JSON,
    SOURCE_JSON,
    FinalConfig,
    file_hash,
    install_final,
    load_final,
    validate_final,
)
from canadianness_eval.judge_adapter import RemoteJudge
from canadianness_eval.settings import ROOT


def write_case(path, cases):
    path.write_text("\n".join(c.model_dump_json() for c in cases) + "\n", encoding="utf-8")
    return path


def subset(name):
    return next(c for c in build_cases() if c.question_id == name)


def test_exact_final_configuration_and_workbook():
    result = validate_final()
    assert result["valid"] and result["steps"] == 42
    config = load_final()
    original = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    assert file_hash(FINAL_JSON) == file_hash(SOURCE_JSON)
    for metric, supplied in zip(config.metrics, original["metrics"]):
        assert metric.evaluation_steps == supplied["evaluation_steps"]
        assert len(metric.evaluation_steps) == 6 and len(metric.rubric_0_to_10) == 5


@pytest.mark.parametrize("change", ["count", "rubric", "params", "ids"])
def test_invalid_final_configuration(change):
    config = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    if change == "count":
        config["metrics"][0]["evaluation_steps"].pop()
    elif change == "rubric":
        config["metrics"][0]["rubric_0_to_10"][1]["min"] = 2
    elif change == "params":
        config["metrics"][0]["required_evaluation_params"].append("CONTEXT")
    else:
        config["metrics"][0]["steps_provenance"][1]["step_id"] = "M1-S1"
    with pytest.raises(ValueError):
        FinalConfig.model_validate(config)


@pytest.mark.parametrize(
    "value,method,expected",
    [
        (0.9, "deepeval_normalized", 0.9),
        (9, "raw_integer_0_to_10", 0.9),
        (0, "deepeval_normalized", 0),
        (1, "deepeval_normalized", 1),
    ],
)
def test_normalization_once(value, method, expected):
    assert normalized_score(value, method) == pytest.approx(expected)


@pytest.mark.parametrize(
    "value,method",
    [
        (1.1, "deepeval_normalized"),
        (-0.1, "deepeval_normalized"),
        (float("nan"), "deepeval_normalized"),
        (float("inf"), "deepeval_normalized"),
        (8.5, "raw_integer_0_to_10"),
    ],
)
def test_invalid_scores_fail_without_clipping(value, method):
    with pytest.raises(ValueError):
        normalized_score(value, method)


def test_closed_book_and_judge_evidence(gateway_factory, tmp_path):
    case = subset("CAL-M7-CONCISE")
    messages = closed_book_messages(case)
    assert messages == [
        {"role": "system", "content": case.system_prompt},
        {"role": "user", "content": case.question},
    ]
    assert "1870" not in json.dumps(messages)
    prompts = []

    def handler(request):
        prompt = json.loads(request.content)["messages"][0]["content"]
        prompts.append(prompt)
        return completion('{"score":9,"reason":"TEST: verified evidence and complete facts"}')

    gateway = gateway_factory(handler)
    judge = RemoteJudge(gateway)
    metric = make_final_metric(load_final().metrics[6], judge)
    assert metric.evaluation_steps == load_final().metrics[6].evaluation_steps
    data = write_case(tmp_path / "cases.jsonl", [case])
    rows = evaluate_calibration(data, judge, tmp_path / "run", repeats=3)
    success = [r for r in rows if r["status"] == "SUCCESS"]
    assert len(success) == 3 and {r["repeat"] for r in success} == {1, 2, 3}
    assert all(r["metric_id"] == "M7" and r["score"] == 0.9 for r in success)
    assert all(r["deepeval_score"] == 0.9 for r in success)
    assert len(prompts) == 3 and "July 15, 1870" in prompts[0]
    assert "1870" in prompts[0] and load_final().metrics[6].scope_exclusions in prompts[0]
    assert len(list((tmp_path / "run/raw").glob("*.json"))) == 3
    assert len(variability(rows)) == 1  # six N/A dimensions are excluded
    assert len(read_results(tmp_path / "run")) == 21
    original = (tmp_path / "run/calibration_results.jsonl").read_bytes()
    evaluate_calibration(data, judge, tmp_path / "run", repeats=3, resume=True)
    assert (
        gateway.attempts == 3
        and (tmp_path / "run/calibration_results.jsonl").read_bytes() == original
    )


def test_readiness_skip_without_api(gateway_factory, tmp_path):
    case = subset("CAL-M7-NO-EVIDENCE")
    gateway = gateway_factory(
        lambda _: pytest.fail("No inference allowed without verified evidence")
    )
    rows = evaluate_calibration(
        write_case(tmp_path / "cases.jsonl", [case]),
        RemoteJudge(gateway),
        tmp_path / "run",
        repeats=3,
    )
    applicable = [r for r in rows if r["applicable"]]
    assert all(
        r["status"] == "NOT_READY_FOR_FACTUAL_EVALUATION" and r["score"] is None for r in applicable
    )
    assert gateway.attempts == 0
    assert variability(rows).empty


def test_presence_is_not_verification():
    case = subset("CAL-M7-CONCISE")
    case.evidence_review.status = "unverified"
    assert not evidence_readiness(case, load_final().metrics[6])[0]


def test_m1_m4_exclude_optional_evidence(gateway_factory, tmp_path):
    prompts = []

    def handler(request):
        prompts.append(json.loads(request.content)["messages"][0]["content"])
        return completion('{"score":10,"reason":"Correct framing/language"}')

    gateway = gateway_factory(handler)
    case = subset("CAL-M1-CONCISE").model_copy(
        update={
            "reference_answer": "SECRET_GOLD_SENTINEL",
            "reference_context": ["EVIDENCE_SENTINEL"],
        }
    )
    evaluate_calibration(
        write_case(tmp_path / "cases.jsonl", [case]),
        RemoteJudge(gateway),
        tmp_path / "run",
        repeats=1,
    )
    assert "SECRET_GOLD_SENTINEL" not in prompts[0] and "EVIDENCE_SENTINEL" not in prompts[0]


def test_failure_isolated_and_raw_preserved(gateway_factory, tmp_path):
    replies = iter([httpx.Response(400), completion('{"score":8,"reason":"Second case succeeds"}')])
    gateway = gateway_factory(lambda _: next(replies))
    cases = [subset("CAL-M1-CONCISE"), subset("CAL-M1-VERBOSE")]
    rows = evaluate_calibration(
        write_case(tmp_path / "cases.jsonl", cases),
        RemoteJudge(gateway),
        tmp_path / "run",
        repeats=1,
    )
    assert [r["status"] for r in rows if r["applicable"]] == ["FAILED", "SUCCESS"]
    assert [r["score"] for r in rows if r["applicable"]] == [None, 0.8]


def test_human_export_fields_blank_and_no_fictional_agreement(gateway_factory, tmp_path):
    case = subset("CAL-M7-CONCISE")
    data = write_case(tmp_path / "cases.jsonl", [case])
    gateway = gateway_factory(lambda _: completion('{"score":10,"reason":"Correct facts"}'))
    directory = tmp_path / "run"
    rows = evaluate_calibration(data, RemoteJudge(gateway), directory, repeats=3)
    analysis = generate_reports(directory, data)
    assert analysis["human_calibration_status"] == "PENDING_REAL_HUMAN_LABELS"
    book = load_workbook(directory / "human_calibration_review.xlsx")
    sheet = book["Human review"]
    assert sheet["J2"].value is None and sheet["K2"].value is None and sheet["L2"].value is None
    assert sheet.column_dimensions["M"].hidden
    result = compare_humans(directory / "human_calibration_review.xlsx", tmp_path / "agreement")
    assert result["human_labels"] == 0
    with pytest.raises(ValueError, match="already exists"):
        generate_reports(directory, data)
    # Genuine input parsing is tested with synthetic reviewer entries, only in temporary files.
    sheet["J2"] = "test_reviewer"
    sheet["K2"] = 0.8
    book.save(directory / "human_calibration_review.xlsx")
    report = compare_humans(
        directory / "human_calibration_review.xlsx", tmp_path / "agreement_labels"
    )
    assert report["by_metric_and_reviewer"][0]["mean_absolute_error"] == pytest.approx(0.2)
    assert report["by_metric_and_reviewer"][0]["rank_correlation"] is None
    assert len(rows) == 21


def test_original_pilot_fields_unchanged():
    cases = {c.question_id: c for c in build_cases()}
    for line in (ROOT / "data/examples/pilot.jsonl").read_text(encoding="utf-8").splitlines():
        original = json.loads(line)
        new = cases[original["question_id"]].model_dump()
        assert all(new[key] == value for key, value in original.items())


def test_historical_artifact_ledger(tmp_path):
    directory = tmp_path / "outputs/pilot"
    directory.mkdir(parents=True)
    path = directory / "results.json"
    path.write_text('{"score":0.8}')
    ledger = artifact_ledger(tmp_path)
    assert verify_ledger(tmp_path, ledger)
    path.write_text('{"score":0.2}')
    with pytest.raises(ValueError, match="Prior artifact changed"):
        verify_ledger(tmp_path, ledger)


def test_run_manifest_change_rejected(gateway_factory, tmp_path):
    gateway = gateway_factory(lambda _: completion('{"score":9,"reason":"Correct"}'))
    data = write_case(tmp_path / "cases.jsonl", [subset("CAL-M1-CONCISE")])
    evaluate_calibration(data, RemoteJudge(gateway), tmp_path / "run", repeats=1)
    with pytest.raises(ValueError, match="manifest mismatch"):
        evaluate_calibration(data, RemoteJudge(gateway), tmp_path / "run", repeats=2, resume=True)


def test_versioned_json_never_overwritten(tmp_path):
    destination = tmp_path / "metrics_final.json"
    install_final(destination=destination)
    assert file_hash(destination) == file_hash(SOURCE_JSON)
    destination.write_text("{}")
    with pytest.raises(ValueError, match="differs"):
        install_final(destination=destination)


def test_cli_legacy_and_new_help():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "canadianness_eval.cli", "--help"], capture_output=True, text=True
    )
    assert result.returncode == 0
    for command in [
        "watch",
        "prepare-review",
        "freeze-review",
        "evaluate",
        "validate-metrics",
        "test-metrics",
        "calibrate",
        "calibration-report",
    ]:
        assert command in result.stdout


def test_failure_artifacts_do_not_expose_key(gateway_factory, tmp_path, caplog, capsys):
    gateway = gateway_factory(
        lambda _: httpx.Response(401, json={"error": "test-secret must never be exported"})
    )
    case = subset("CAL-M1-CONCISE")
    directory = tmp_path / "run"
    rows = evaluate_calibration(
        write_case(tmp_path / "cases.jsonl", [case]), RemoteJudge(gateway), directory, repeats=1
    )
    assert next(r for r in rows if r["applicable"])["status"] == "FAILED"
    assert "test-secret" not in capsys.readouterr().out + caplog.text
    for path in directory.rglob("*"):
        if path.is_file():
            assert "test-secret" not in path.read_text(encoding="utf-8")


def test_invalid_live_style_score_is_failure(gateway_factory, tmp_path):
    gateway = gateway_factory(lambda _: completion('{"score":11,"reason":"Out of native range"}'))
    case = subset("CAL-M1-CONCISE")
    rows = evaluate_calibration(
        write_case(tmp_path / "cases.jsonl", [case]),
        RemoteJudge(gateway),
        tmp_path / "run",
        repeats=1,
    )
    row = next(r for r in rows if r["applicable"])
    assert row["status"] == "FAILED" and row["score"] is None
    assert row["deepeval_score"] == pytest.approx(1.1)


def test_resume_repairs_interrupted_jsonl_from_checkpoints(gateway_factory, tmp_path):
    gateway = gateway_factory(lambda _: completion('{"score":9,"reason":"Correct framing"}'))
    data = write_case(tmp_path / "cases.jsonl", [subset("CAL-M1-CONCISE")])
    directory = tmp_path / "run"
    judge = RemoteJudge(gateway)
    evaluate_calibration(data, judge, directory, repeats=1)
    with (directory / "calibration_results.jsonl").open("a", encoding="utf-8") as handle:
        handle.write('{"interrupted":')
    evaluate_calibration(data, judge, directory, repeats=1, resume=True)
    assert gateway.attempts == 1
    lines = (directory / "calibration_results.jsonl").read_text(encoding="utf-8").splitlines()
    assert len([json.loads(line) for line in lines]) == 7
    assert len(list(directory.glob("interrupted_results_*.jsonl"))) == 1


def test_default_calibration_id_handles_utc_offset(monkeypatch):
    from types import SimpleNamespace

    from canadianness_eval.calibration import workflow

    monkeypatch.setattr(workflow, "now", lambda: "2026-11-03T16:00:00.123456+00:00")
    monkeypatch.setattr(workflow, "validate_final", lambda: None)
    monkeypatch.setattr(workflow, "install_final", lambda: None)

    def capture(directory, **kwargs):
        assert directory.name.startswith("final_v1_20261103T")
        assert "+" not in directory.name and ":" not in directory.name
        raise ValueError("RUN_ID_VERIFIED")

    monkeypatch.setattr(workflow, "create_run", capture)
    args = SimpleNamespace(
        command="calibrate", input="not-the-default.jsonl", resume=False, run_id=None
    )
    with pytest.raises(ValueError, match="RUN_ID_VERIFIED"):
        workflow.dispatch(args)


def test_gateway_unavailable_still_exports_human_review(tmp_path):
    data = write_case(tmp_path / "cases.jsonl", [subset("CAL-M7-CONCISE")])
    directory = tmp_path / "unavailable"
    rows = evaluate_calibration(
        data, None, directory, repeats=3, unavailable_reason="Gateway unavailable"
    )
    assert all(r["status"] == "SKIPPED_GATEWAY_UNAVAILABLE" for r in rows if r["applicable"])
    analysis = generate_reports(directory, data)
    assert analysis["status_counts"]["SKIPPED_GATEWAY_UNAVAILABLE"] == 3
    assert (directory / "human_calibration_review.xlsx").exists()
