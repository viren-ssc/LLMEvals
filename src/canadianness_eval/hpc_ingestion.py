"""Offline import contract for benchmark and HPC exports; never invokes a judge."""

import argparse
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

METRICS = {f"M{i}" for i in range(1, 8)}
MODELS = ("gc_llm", "apertus", "llama")


class BenchmarkRow(BaseModel):
    model_config = ConfigDict(extra="allow")
    question_id: str
    language: str
    primary_metric: str
    applicable_metrics: list[str]
    context_text: str
    question: str
    reference_answer: str

    @field_validator("question_id", "question", "reference_answer")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Required text is blank")
        return value

    @field_validator("applicable_metrics", mode="before")
    @classmethod
    def parse_labels(cls, value):
        if isinstance(value, str):
            return (
                json.loads(value)
                if value.lstrip().startswith("[")
                else [label.strip() for label in value.replace(";", ",").split(",")]
            )
        return value

    @model_validator(mode="after")
    def labels(self):
        if self.language not in ("en", "fr", "EN", "FR", "English", "French"):
            raise ValueError("Language must identify English or French")
        if (
            not self.applicable_metrics
            or len(set(self.applicable_metrics)) != len(self.applicable_metrics)
            or not set(self.applicable_metrics) <= METRICS
            or self.primary_metric not in self.applicable_metrics
        ):
            raise ValueError("Unique M1-M7 labels required; include primary_metric")
        return self


class Generation(BaseModel):
    model_config = ConfigDict(extra="allow")  # Retain inference settings and metadata.
    question_id: str
    evaluated_model: str
    answer: str | None = None
    status: str = "success"


class EvaluationResult(BaseModel):
    question_id: str
    evaluated_model: str
    language: str
    primary_metric: str
    evaluation_metric: str
    score: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    judge_reason: str | None = None
    judge_model: str
    rubric_version: str
    evaluation_steps_version: str
    evaluation_run_id: str
    evaluation_timestamp: str
    status: str
    error_message: str | None = None

    @model_validator(mode="after")
    def score_status(self):
        if (self.status == "success") != (self.score is not None):
            raise ValueError("Only successful evaluations must have a score")
        if self.evaluation_metric not in METRICS:
            raise ValueError("Unknown metric")
        return self


def read_records(path):
    path = Path(path)
    if path.suffix.lower() == ".xlsx":
        from openpyxl import load_workbook

        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            rows = iter(workbook.active.values)
            header = next(rows, ())
            if not header or len(set(header)) != len(header):
                raise ValueError("Missing or duplicate Excel headers")
            return [dict(zip(header, row)) for row in rows if any(v is not None for v in row)]
        finally:
            workbook.close()
    if path.suffix.lower() == ".jsonl":
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]
    if path.suffix.lower() == ".parquet":
        import pandas as pd

        try:
            frame = pd.read_parquet(path)
        except ImportError:
            raise ValueError("Parquet requires optional pyarrow: install it in .venv") from None
        return frame.astype(object).where(frame.notna(), None).to_dict("records")
    raise ValueError("Expected .xlsx, .jsonl or .parquet")


def load_benchmark(path, expected_count=None):
    rows = []
    for index, raw in enumerate(read_records(path), 1):
        try:
            rows.append(BenchmarkRow.model_validate(raw))
        except ValueError as exc:
            raise ValueError(f"Invalid benchmark record {index}: {exc}") from None
    ids = [r.question_id for r in rows]
    if not rows or len(set(ids)) != len(ids):
        raise ValueError("Empty benchmark or duplicate question_id")
    if expected_count is not None and len(rows) != expected_count:
        raise ValueError(f"Expected {expected_count} questions; received {len(rows)}")
    return rows


def wide_generations(rows):
    records = []
    for row in rows:
        raw = row.model_dump()
        for model in MODELS:
            field = model + "_answer"
            if field not in raw:
                raise ValueError(f"Missing HPC column {field}")
            answer = raw[field]
            records.append(
                Generation(
                    question_id=row.question_id,
                    evaluated_model=model,
                    answer=answer,
                    status="success" if isinstance(answer, str) and answer.strip() else "missing",
                )
            )
    return records


def join_generations(rows, generations, models=MODELS):
    benchmark = {row.question_id: row for row in rows}
    indexed = {}
    for item in generations:
        key = (item.question_id, item.evaluated_model)
        if item.question_id not in benchmark or item.evaluated_model not in models:
            raise ValueError("Unknown generation question_id or evaluated_model")
        if key in indexed:
            raise ValueError("Duplicate generation question/model")
        indexed[key] = item
    joined = []
    for row in rows:
        for model in models:
            item = indexed.get((row.question_id, model))
            ready = bool(item and item.status == "success" and item.answer and item.answer.strip())
            joined.append((row, model, item, ready))
    return joined


def workload(joined):
    eligible = sum(len(row.applicable_metrics) for row, _, _, ready in joined if ready)
    return {
        "answer_slots": len(joined),
        "missing_or_failed": sum(not ready for *_, ready in joined),
        "metric_evaluations": eligible,
        "judge_requests_baseline": eligible,
        "judge_requests_note": "Fixed steps: baseline one request per metric; validation, schema fallback and transient retries increase this. No throughput claim without live measurement.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("benchmark")
    parser.add_argument("--generations")
    parser.add_argument("--wide", action="store_true")
    parser.add_argument("--expected-count", type=int, default=756)
    args = parser.parse_args()
    rows = load_benchmark(args.benchmark, args.expected_count)
    if args.generations and args.wide:
        parser.error("Choose --wide or --generations")
    generations = (
        wide_generations(rows)
        if args.wide
        else [Generation.model_validate(r) for r in read_records(args.generations)]
        if args.generations
        else []
    )
    print(json.dumps(workload(join_generations(rows, generations)), indent=2))


if __name__ == "__main__":
    main()
