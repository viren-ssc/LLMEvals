import hashlib
import json
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


Metric = Literal["M1", "M2", "M3", "M4", "M5", "M6", "M7"]
Verdict = Literal["supported", "contradicted", "insufficient", "retrieval_failed"]


class Question(Record):
    question_id: str
    question: str
    answer: str
    metric: Metric
    source_urls: list[str]
    original_row: dict[str, str]
    queue_row: dict[str, str]
    prior_claims: list[dict[str, str]] = Field(default_factory=list)
    original_evidence: list[dict[str, str]] = Field(default_factory=list)

    @property
    def fingerprint(self):
        return digest(self.model_dump())


class Claim(Record):
    text: str = Field(min_length=1)
    answer_start: int = Field(ge=0)
    answer_end: int = Field(gt=0)
    material: bool
    temporal_scope: Literal["historical", "current", "timeless"]
    relevant_date: str
    jurisdiction: str = Field(min_length=1)


class Extraction(Record):
    claims: list[Claim] = Field(min_length=1)
    nonfactual_spans: list[str]
    coverage_explanation: str = Field(min_length=1)


class Coverage(Record):
    complete: bool
    omitted_claims: list[str]
    explanation: str = Field(min_length=1)


class Source(Record):
    url: str
    final_url: str = ""
    title: str = ""
    retrieved_at: str = Field(default_factory=now)
    status: Literal["ok", "blocked", "failed", "unsupported_format", "soft_failed"]
    text: str = ""
    sha256: str = ""
    raw_path: str = ""
    authoritative: bool = False
    historical: bool = False
    archive_date: str = ""
    archive_container_path: str = ""
    archive_container_sha256: str = ""
    archive_record_id: str = ""
    error: str = ""


class Citation(Record):
    source_url: str
    source_sha256: str
    locator: str = Field(min_length=1)
    exact_excerpt: str = Field(min_length=1, max_length=1800)
    attributed_summary: str
    temporal_match: bool
    jurisdiction_match: bool
    explanation: str = Field(min_length=1)


class Judgment(Record):
    verdict: Verdict
    citations: list[Citation]
    explanation: str = Field(min_length=1)


class ClaimResult(Record):
    claim_id: str
    claim: Claim
    judgment: Judgment


class MetricAssessment(Record):
    primary_metric: Metric
    suitable: bool
    explanation: str = Field(min_length=1)


class Proposal(Record):
    corrected_answer: str
    missing_information: list[str]
    disposition: Literal["accept", "revise", "reject", "unresolved", "needs_more_evidence"]
    explanation: str = Field(min_length=1)


class Research(Record):
    question_id: str
    input_fingerprint: str
    created_at: str = Field(default_factory=now)
    extraction: Extraction
    coverage: Coverage
    claims: list[ClaimResult]
    sources: list[Source]
    metric: MetricAssessment
    proposal: Proposal
    fully_supported: bool
    gate_errors: list[str]
    judge_model: str
    instructions_sha256: str
    # Draft corrected answers never inherit support for the original reference answer.
    corrected_answer_verified: bool = False

    @property
    def event_id(self):
        return "VR-" + digest(self.model_dump())[:24]
