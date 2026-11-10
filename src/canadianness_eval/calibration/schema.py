import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..dataset import EvaluationCase


class EvidenceReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["verified", "unverified", "missing", "not_required"] = "unverified"
    reference_answer_verified: bool = False
    sufficient_for_metrics: list[str] = Field(default_factory=list)
    verified_by: str = ""
    verification_date: str = ""
    source_ids: list[str] = Field(default_factory=list)
    note: str = ""


class CalibrationCase(EvaluationCase):
    dataset_version: str
    primary_metric: str
    secondary_metrics: list[str] = Field(default_factory=list)
    evidence_review: EvidenceReview = Field(default_factory=EvidenceReview)
    case_family: str
    synthetic: bool = True
    development_example: bool = True
    intended_score_ranges: dict[str, list[float]] = Field(default_factory=dict)
    expected_behavior: str
    comparison_group: str | None = None
    comparison_role: str | None = None
    language: str = "en"
    system_prompt: str = "Answer the user's question accurately and concisely."

    @model_validator(mode="after")
    def mapping_valid(self):
        if self.applicable_metrics != [self.primary_metric, *self.secondary_metrics]:
            raise ValueError("Applicability must equal explicit primary plus secondary metrics")
        for mid, interval in self.intended_score_ranges.items():
            if (
                mid not in self.applicable_metrics
                or len(interval) != 2
                or not 0 <= interval[0] <= interval[1] <= 1
            ):
                raise ValueError("Invalid synthetic diagnostic score interval")
        return self


def evidence_readiness(case, metric):
    if "CONTEXT" not in metric.required_evaluation_params:
        return True, "NOT_REQUIRED", None
    review = case.evidence_review
    missing = []
    if (
        not case.reference_answer
        or not case.reference_context
        or not all(x.strip() for x in case.reference_context)
    ):
        missing.append("reference answer or source text missing")
    if review.status != "verified" or not review.reference_answer_verified:
        missing.append("reference/evidence verification incomplete")
    if metric.metric_id not in review.sufficient_for_metrics:
        missing.append("evidence not attested sufficient for this metric")
    if not review.verified_by or not review.verification_date or not review.source_ids:
        missing.append("verification provenance missing")
    return (
        not missing,
        ("VERIFIED" if not missing else "NOT_READY_FOR_FACTUAL_EVALUATION"),
        "; ".join(missing) or None,
    )


def load_cases(path):
    cases, seen = [], set()
    for number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            case = CalibrationCase.model_validate_json(line)
        except ValueError as exc:
            raise ValueError(f"Invalid calibration line {number}: {exc}") from None
        key = case.question_id, case.model_variant
        if key in seen:
            raise ValueError("Duplicate calibration question/variant")
        seen.add(key)
        cases.append(case)
    if not cases:
        raise ValueError("No calibration cases")
    return cases


def closed_book_messages(case):
    """Pure input builder for a future tested-model client; never calls a model."""
    return [
        {"role": "system", "content": case.system_prompt},
        {"role": "user", "content": case.question},
    ]


def dataset_hash(cases):
    from ..storage import digest

    return digest([json.loads(case.model_dump_json()) for case in cases])
