import json

import pandas as pd
import pytest
from test_gateway import completion
from test_research_workflow import approve, build_workbook

from canadianness_eval.dataset import EvaluationCase, load_dataset
from canadianness_eval.evaluation_runner import evaluate
from canadianness_eval.evaluation_runner import test_case as build_case
from canadianness_eval.freeze_metrics import freeze
from canadianness_eval.judge_adapter import RemoteJudge
from canadianness_eval.results_export import export_results
from canadianness_eval.settings import ROOT


def test_dataset_validation(tmp_path):
    cases = load_dataset(ROOT / "data/examples/pilot.jsonl")
    assert len(cases) == 21 and all(c.illustrative for c in cases)
    with pytest.raises(ValueError):
        EvaluationCase(
            question_id="x",
            question="q",
            model_answer="a",
            model_variant="base",
            applicable_metrics=["M8"],
        )
    path = tmp_path / "duplicate.jsonl"
    line = cases[0].model_dump_json()
    path.write_text(line + "\n" + line)
    with pytest.raises(ValueError, match="Duplicate"):
        load_dataset(path)


def test_geval_scoring_evidence_and_applicability(gateway_factory, tmp_path):
    workbook = tmp_path / "review.xlsx"
    frozen_path = tmp_path / "frozen.yaml"
    build_workbook(workbook)
    approve(workbook)
    config = freeze(workbook, frozen_path, "test-human")
    prompts = []

    def handler(request):
        prompt = json.loads(request.content)["messages"][0]["content"]
        prompts.append(prompt)
        return completion('{"score":9,"reason":"Mocked scoring explanation"}')

    gateway = gateway_factory(handler)
    judge = RemoteJudge(gateway)
    case = EvaluationCase(
        question_id="x",
        question="Which authority?",
        model_answer="Province.",
        model_variant="base",
        applicable_metrics=["M2"],
        reference_answer="EXPECTED_SENTINEL",
        reference_context=["INDEPENDENT_EVIDENCE_SENTINEL"],
    )
    dataset = tmp_path / "input.jsonl"
    dataset.write_text(case.model_dump_json() + "\n")
    rows = evaluate(dataset, frozen_path, judge, tmp_path / "results.jsonl")
    assert len(rows) == 7 and rows[1]["score"] == pytest.approx(0.9)
    assert rows[0]["status"] == "not_applicable" and rows[0]["score"] is None
    assert "INDEPENDENT_EVIDENCE_SENTINEL" in prompts[0]
    assert "EXPECTED_SENTINEL" in prompts[0]
    assert gateway.attempts == 1
    evaluate(dataset, frozen_path, judge, tmp_path / "results.jsonl")
    assert gateway.attempts == 1  # no unnecessary repeat calls
    export_results(rows, tmp_path)
    assert pd.read_csv(tmp_path / "results.csv").shape[0] == 7
    assert (tmp_path / "summary.csv").exists()
    missing = case.model_copy(update={"reference_context": []})
    with pytest.raises(ValueError, match="Missing approved evidence"):
        build_case(missing, config["metrics"][1])


def test_pairing_statistics(tmp_path):
    rows = [
        dict(
            question_id=f"q{i}",
            model_variant=variant,
            metric_id="M7",
            status="success",
            score=score,
        )
        for i in range(12)
        for variant, score in [("base", 0.5), ("fine_tuned", 0.7)]
    ]
    export_results(rows, tmp_path)
    paired = pd.read_csv(tmp_path / "paired_comparison.csv")
    assert paired.valid_pairs.iloc[0] == 12
    assert paired.paired_difference.iloc[0] == pytest.approx(0.2)
    assert paired.ci_low.iloc[0] == pytest.approx(0.2)
