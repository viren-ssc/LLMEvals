import json

import pytest
from openpyxl import Workbook

from canadianness_eval.hpc_ingestion import (
    BenchmarkRow,
    Generation,
    join_generations,
    load_benchmark,
    wide_generations,
    workload,
)


def record(qid="q1"):
    return dict(
        question_id=qid,
        language="fr",
        primary_metric="M7",
        applicable_metrics=["M7"],
        context_text="Résumé justificatif.",
        question="  Où est Québec ?  ",
        reference_answer="Au Canada.",
    )


def test_excel_preserves_text_and_checks_count(tmp_path):
    row = record()
    row["applicable_metrics"] = '["M7"]'
    book = Workbook()
    book.active.append(list(row))
    book.active.append(list(row.values()))
    path = tmp_path / "benchmark.xlsx"
    book.save(path)
    rows = load_benchmark(path, 1)
    assert rows[0].question == "  Où est Québec ?  "
    with pytest.raises(ValueError, match="Expected 756"):
        load_benchmark(path, 756)


@pytest.mark.parametrize(
    "update",
    [
        {"question": " "},
        {"reference_answer": None},
        {"applicable_metrics": ["M1"]},
        {"applicable_metrics": ["M7", "M7"]},
        {"language": "de"},
    ],
)
def test_invalid_rows(update):
    with pytest.raises(ValueError):
        BenchmarkRow.model_validate(record() | update)


def test_duplicate_ids_and_columns(tmp_path):
    path = tmp_path / "rows.jsonl"
    path.write_text("\n".join(json.dumps(record()) for _ in range(2)), encoding="utf8")
    with pytest.raises(ValueError, match="duplicate"):
        load_benchmark(path)
    with pytest.raises(ValueError, match="Missing HPC column"):
        wide_generations([BenchmarkRow(**record())])


def test_join_by_id_and_missing_failed():
    rows = [BenchmarkRow(**record("q1")), BenchmarkRow(**record("q2"))]
    generations = [
        Generation(question_id="q2", evaluated_model="llama", answer="Second"),
        Generation(question_id="q1", evaluated_model="gc_llm", answer="", status="failed"),
    ]
    joined = join_generations(rows, generations)
    assert joined[-1][2].answer == "Second"
    assert workload(joined)["metric_evaluations"] == 1
    assert workload(joined)["missing_or_failed"] == 5
    with pytest.raises(ValueError, match="Duplicate"):
        join_generations(rows, generations * 2)
    with pytest.raises(ValueError, match="Unknown"):
        join_generations(rows, [Generation(question_id="absent", evaluated_model="llama")])


def test_wide_missing_answers():
    row = BenchmarkRow(
        **(record() | {"gc_llm_answer": "Answer", "apertus_answer": None, "llama_answer": " "})
    )
    assert workload(join_generations([row], wide_generations([row])))["missing_or_failed"] == 2


def test_result_scores_require_success():
    from canadianness_eval.hpc_ingestion import EvaluationResult

    base = dict(
        question_id="q1",
        evaluated_model="llama",
        language="fr",
        primary_metric="M7",
        evaluation_metric="M7",
        judge_model="gpt-oss-120b",
        rubric_version="v1",
        evaluation_steps_version="v1",
        evaluation_run_id="synthetic",
        evaluation_timestamp="2026-11-06T00:00:00Z",
        status="failed",
    )
    assert EvaluationResult(**base).score is None
    for update in ({"score": 0.5}, {"status": "success"}, {"status": "success", "score": 1.1}):
        with pytest.raises(ValueError):
            EvaluationResult(**(base | update))
    assert EvaluationResult(**(base | {"status": "success", "score": 0.8})).score == 0.8
