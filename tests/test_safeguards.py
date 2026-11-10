import json

import httpx
import pandas as pd
import pytest
from openpyxl import load_workbook
from test_gateway import completion
from test_research_workflow import STEPS, approve, build_workbook

from canadianness_eval.api_client import GatewayError
from canadianness_eval.dataset import EvaluationCase, load_dataset
from canadianness_eval.freeze_metrics import freeze
from canadianness_eval.generate_steps import generate_all
from canadianness_eval.judge_adapter import RemoteJudge
from canadianness_eval.metric_definitions import load_metrics
from canadianness_eval.results_export import export_results


def test_auth_failure_not_repeated_across_calls(gateway_factory):
    gateway = gateway_factory(lambda _: httpx.Response(401))
    for _ in range(2):
        with pytest.raises(GatewayError):
            gateway.generate("test")
    assert gateway.attempts == 1


def test_transient_recovers(gateway_factory):
    replies = iter([httpx.Response(429), httpx.Response(503), completion("ok")])
    gateway = gateway_factory(lambda _: next(replies))
    assert gateway.generate("test") == "ok"
    assert gateway.attempts == 3


def test_model_discovery_http_boundary(gateway_factory):
    gateway = gateway_factory(
        lambda _: httpx.Response(200, json={"data": [{"id": "org/GPT-OSS-120B-prod"}]})
    )
    assert gateway.discover() == ["org/GPT-OSS-120B-prod"]
    assert gateway.model_id == "org/GPT-OSS-120B-prod"


def test_invalid_discovery_response(gateway_factory):
    gateway = gateway_factory(lambda _: httpx.Response(200, json={"data": [{}]}))
    with pytest.raises(GatewayError, match="Invalid /models"):
        gateway.discover()


def test_force_archives_original_outputs(gateway_factory, tmp_path):
    gateway = gateway_factory(lambda _: completion(json.dumps({"steps": STEPS})))
    judge = RemoteJudge(gateway)
    generate_all(load_metrics()[:1], judge, tmp_path, runs=3)
    generate_all(load_metrics()[:1], judge, tmp_path, runs=3, force=True)
    assert len(list(tmp_path.glob("M*/history/*.json"))) == 3
    assert gateway.attempts == 6


def test_changed_generation_definition_rejected(gateway_factory, tmp_path):
    gateway = gateway_factory(lambda _: completion(json.dumps({"steps": STEPS})))
    judge = RemoteJudge(gateway)
    metrics = load_metrics()[:1]
    generate_all(metrics, judge, tmp_path, runs=3)
    metrics[0]["criteria"] += "Changed."
    with pytest.raises(ValueError, match="inputs changed"):
        generate_all(metrics, judge, tmp_path, runs=3)
    assert gateway.attempts == 3


def test_pair_evidence_mismatch_rejected(tmp_path):
    base = EvaluationCase(
        question_id="pair",
        question="Question",
        model_answer="A",
        model_variant="base",
        applicable_metrics=["M7"],
        reference_answer="R",
        reference_context=["same evidence"],
    )
    tuned = base.model_copy(
        update={"model_variant": "fine_tuned", "reference_context": ["different evidence"]}
    )
    path = tmp_path / "pairs.jsonl"
    path.write_text(base.model_dump_json() + "\n" + tuned.model_dump_json())
    with pytest.raises(ValueError, match="differs across variants"):
        load_dataset(path)


def test_failed_pairs_reported_without_zero(tmp_path):
    rows = [
        dict(question_id="pair", metric_id="M7", model_variant="base", score=0.8, status="success"),
        dict(
            question_id="pair",
            metric_id="M7",
            model_variant="fine_tuned",
            score=None,
            status="failed",
        ),
    ]
    export_results(rows, tmp_path)
    pair = pd.read_csv(tmp_path / "paired_comparison.csv")
    assert pair.valid_pairs.iloc[0] == 0 and pair.unmatched_or_failed.iloc[0] == 1
    assert pd.isna(pair.paired_difference.iloc[0])


def test_contradictory_selection_rejected(tmp_path):
    path = tmp_path / "review.xlsx"
    build_workbook(path)
    approve(path)
    book = load_workbook(path)
    sheet = book["Step Candidates"]
    sheet["K2"] = "Check the jurisdiction"
    sheet["J3"] = "Revise"
    sheet["K3"] = "Do not check the jurisdiction"
    sheet["L3"] = 2
    book.save(path)
    with pytest.raises(ValueError, match="contradictory"):
        freeze(path, tmp_path / "v1.yaml", "reviewer")
