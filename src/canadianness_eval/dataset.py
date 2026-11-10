import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .metric_definitions import IDS


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    model_answer: str = Field(min_length=1)
    reference_answer: str | None = None
    reference_context: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    reference_ids: list[str] = Field(default_factory=list)
    applicable_metrics: list[str]
    model_variant: str = Field(min_length=1)
    provenance: str = "unspecified"
    illustrative: bool = False
    expected_quality: str | None = None

    @field_validator("applicable_metrics")
    @classmethod
    def known_metrics(cls, values):
        if len(set(values)) != len(values) or not set(values).issubset(IDS):
            raise ValueError("Explicit unique applicability labels M1-M7 required")
        return values


def load_dataset(path):
    cases, seen = [], set()
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            case = EvaluationCase.model_validate(json.loads(line))
        except ValueError as exc:
            raise ValueError(f"Invalid dataset line {line_number}: {exc}") from None
        key = (case.question_id, case.model_variant)
        if key in seen:
            raise ValueError(f"Duplicate question/variant at line {line_number}")
        seen.add(key)
        cases.append(case)
    if not cases:
        raise ValueError("Dataset is empty")
    # Comparisons must hold the question and reference evidence constant across variants.
    pairs = {}
    for case in cases:
        evidence = (
            case.question,
            case.reference_answer,
            case.reference_context,
            case.reference_ids,
            case.source_urls,
            sorted(case.applicable_metrics),
        )
        if case.question_id in pairs and evidence != pairs[case.question_id]:
            raise ValueError(
                f"Question/evidence/applicability differs across variants: {case.question_id}"
            )
        pairs[case.question_id] = evidence
    return cases
