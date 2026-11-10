"""V2 records are separate so historic event hashes and audit identities remain intact."""

import json
from typing import Literal

from pydantic import Field

from .models import (
    Claim,
    ClaimResult,
    Coverage,
    Extraction,
    MetricAssessment,
    Record,
    Research,
    Verdict,
)


class ClaimV2(Claim):
    assertion: str = Field(min_length=1)


class ClaimDraft(Record):
    assertion: str = Field(min_length=1)
    answer_quote: str = Field(min_length=1)
    temporal_scope: Literal["historical", "current", "timeless"]
    relevant_date: str
    jurisdiction: str = Field(min_length=1)


class ExtractionDraft(Record):
    claims: list[ClaimDraft] = Field(min_length=1)
    nonfactual_spans: list[str]
    coverage_explanation: str


class ExtractionV2(Extraction):
    claims: list[ClaimV2]


class ClaimResultV2(ClaimResult):
    claim: ClaimV2


class CoverageV2(Coverage):
    assertion_alignment_errors: list[str]


class EvidenceUnit(Record):
    evidence_id: str
    source_url: str
    source_sha256: str
    locator: str
    exact_excerpt: str
    source_title: str
    historical: bool
    archive_date: str


class EvidenceUse(Record):
    evidence_id: str
    temporal_match: bool
    jurisdiction_match: bool
    explanation: str = Field(min_length=1)


class EvidenceJudgment(Record):
    verdict: Verdict
    evidence: list[EvidenceUse]
    explanation: str = Field(min_length=1)


class MetricV2(MetricAssessment):
    tested_operation: Literal[
        "recall",
        "institutional_roles",
        "application",
        "language",
        "cultural_understanding",
        "uncertainty",
        "context_recognition",
    ]
    required_relationships: list[str]
    review_flags: list[str] = Field(default_factory=list)


class ResearchV2(Research):
    pipeline_version: Literal[2] = 2
    baseline_event_id: str = ""
    extraction: ExtractionV2
    coverage: CoverageV2
    claims: list[ClaimResultV2]
    metric: MetricV2
    reference_status: Literal[
        "fully_supported", "contradicted", "needs_more_evidence", "extraction_error"
    ]
    alignment_errors: list[str]
    evidence_catalog: list[EvidenceUnit]
    discovery_log: list[dict]
    citation_selection_errors: list[str]


def research_from_json(payload):
    schema = ResearchV2 if json.loads(payload).get("pipeline_version") == 2 else Research
    return schema.model_validate_json(payload)
