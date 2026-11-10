import json

import pytest
import yaml
from openpyxl import load_workbook
from test_gateway import completion

from canadianness_eval.consolidate_steps import consolidate
from canadianness_eval.freeze_metrics import freeze, load_frozen
from canadianness_eval.generate_steps import ResearchTemplate, generate_all
from canadianness_eval.judge_adapter import RemoteJudge
from canadianness_eval.metric_definitions import load_metrics
from canadianness_eval.review_workbook import create_workbook
from canadianness_eval.rubric_builder import load_rubrics, validate_bands
from canadianness_eval.storage import digest

STEPS = [f"Check observable Canadian jurisdiction evidence condition {i}." for i in range(6)]


def build_workbook(path):
    metrics = load_metrics()
    records = [
        dict(
            metric_id=m["metric_id"],
            metric_name=m["metric_name"],
            run_number=1,
            status="success",
            evaluation_steps=STEPS,
        )
        for m in metrics
    ]
    candidates, coverage = consolidate(records, metrics)
    create_workbook(
        path,
        candidates,
        coverage,
        load_rubrics(),
        {"attempted": 7, "metric_definitions_hash": digest(metrics)},
    )
    return candidates


def approve(path):
    book = load_workbook(path)
    sheet = book["Step Candidates"]
    seen = set()
    for row in sheet.iter_rows(min_row=2):
        mid = row[0].value
        if mid not in seen:
            row[9].value = "Revise"
            row[10].value = "Check the relevant approved metric requirement against the evidence."
            row[11].value = 1
            seen.add(mid)
    for row in book["Rubric Review"].iter_rows(min_row=2):
        row[4].value = "Yes"
    book.save(path)


def test_definitions_and_rubrics():
    metrics = load_metrics()
    assert len(metrics) == 7
    assert "CONTEXT" in metrics[5]["evaluation_params"]
    assert "CONTEXT" not in metrics[0]["evaluation_params"]
    rubrics = load_rubrics()
    assert len(rubrics) == 7 and all(not r["approved"] for r in rubrics.values())
    with pytest.raises(ValueError):
        validate_bands([{"score_range": [0, 10], "description": "generic"}])


def test_four_runs_and_resumption(gateway_factory, tmp_path):
    gateway = gateway_factory(lambda _: completion(json.dumps({"steps": STEPS})))
    judge = RemoteJudge(gateway)
    records = generate_all(load_metrics(), judge, tmp_path)
    assert len(records) == 28 and gateway.attempts == 28
    assert len(list(tmp_path.glob("M*/run_*.json"))) == 28
    assert records[0]["responses"][0]["raw_response"]["choices"]
    assert len(generate_all(load_metrics(), judge, tmp_path)) == 28
    assert gateway.attempts == 28
    assert "5-8" in ResearchTemplate.generate_evaluation_steps("Input", "test")


def test_failed_runs_are_recorded(gateway_factory, tmp_path):
    import httpx

    gateway = gateway_factory(lambda _: httpx.Response(401))
    records = generate_all(load_metrics()[:1], RemoteJudge(gateway), tmp_path, runs=3)
    assert len(records) == 3 and all(r["status"] == "failed" for r in records)
    assert all(not r["evaluation_steps"] for r in records)


def test_duplicates_keep_provenance():
    metric = load_metrics()[0]
    records = [
        dict(
            metric_id="M1",
            metric_name=metric["metric_name"],
            status="success",
            run_number=n,
            evaluation_steps=["Check Canadian jurisdiction against the question."],
        )
        for n in (1, 2)
    ]
    candidates, coverage = consolidate(records, [metric])
    assert len(candidates) == 2 and candidates.appearances_across_runs.tolist() == [2, 2]
    assert coverage.distinct_lexical_groups.iloc[0] == 1


def test_workbook_freeze_and_tamper(tmp_path):
    path = tmp_path / "review.xlsx"
    build_workbook(path)
    book = load_workbook(path)
    assert book.sheetnames == [
        "Step Candidates",
        "Metric Coverage",
        "Rubric Review",
        "Review Summary",
    ]
    assert book["Step Candidates"].freeze_panes == "A2"
    assert book["Step Candidates"]["J2"].value is None
    frozen = tmp_path / "v1.yaml"
    with pytest.raises(ValueError, match="select at least one"):
        freeze(path, frozen, "researcher")
    assert not frozen.exists()
    approve(path)
    result = freeze(path, frozen, "researcher")
    assert result["status"] == "FROZEN" and len(result["metrics"]) == 7
    assert load_frozen(frozen)["configuration_hash"] == result["configuration_hash"]
    with pytest.raises(ValueError, match="overwrite forbidden"):
        freeze(path, frozen, "researcher")
    result["metrics"][0]["evaluation_steps"] = ["tampered"]
    frozen.write_text(yaml.safe_dump(result))
    with pytest.raises(ValueError, match="altered"):
        load_frozen(frozen)


def test_workbook_overwrite_protected(tmp_path):
    path = tmp_path / "review.xlsx"
    build_workbook(path)
    with pytest.raises(ValueError, match="already exists"):
        build_workbook(path)


def test_conflicting_order_rejected(tmp_path):
    path = tmp_path / "review.xlsx"
    build_workbook(path)
    approve(path)
    book = load_workbook(path)
    sheet = book["Step Candidates"]
    sheet["J3"] = "Keep"
    sheet["L3"] = 1
    book.save(path)
    with pytest.raises(ValueError, match="unique positive"):
        freeze(path, tmp_path / "v1.yaml", "reviewer")
