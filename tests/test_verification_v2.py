import json
from pathlib import Path

import httpx
import pytest

from canadianness_eval.settings import Settings
from canadianness_eval.verification.config import Config
from canadianness_eval.verification.db import Database
from canadianness_eval.verification.discovery import Discovery
from canadianness_eval.verification.evidence import catalog, materialize, rank_units
from canadianness_eval.verification.export import export_package
from canadianness_eval.verification.gates import extraction_errors
from canadianness_eval.verification.models import Coverage, Question, Source
from canadianness_eval.verification.pipeline_v2 import (
    PipelineV2,
    SupportCheck,
    SupportChecks,
    align,
    assess_metric,
)
from canadianness_eval.verification.sources import SourceRetriever, soft_failure
from canadianness_eval.verification.v2_models import (
    ClaimDraft,
    CoverageV2,
    EvidenceJudgment,
    EvidenceUse,
    ExtractionDraft,
    MetricV2,
    ResearchV2,
)

URL = "https://www.canada.ca/current-program"
ANSWER = "The program began in 2004."


def draft():
    return ExtractionDraft(
        claims=[
            ClaimDraft(
                assertion=ANSWER,
                answer_quote=ANSWER,
                temporal_scope="historical",
                relevant_date="2004",
                jurisdiction="Canada",
            )
        ],
        nonfactual_spans=[],
        coverage_explanation="All facts covered",
    )


def question():
    return Question(
        question_id="GC-ADD-0012",
        question="When did the program begin?",
        answer=ANSWER,
        metric="M7",
        source_urls=[URL],
        original_row={},
        queue_row={"status": "Pending"},
    )


@pytest.mark.parametrize(
    "notice",
    [
        "The link you have bookmarked is no longer available.",
        "The requested content is no longer available.",
        "The page you are looking for has been moved.",
    ],
)
def test_http200_notice_is_never_evidence(tmp_path, notice):
    db = Database(tmp_path / "db")

    def handler(request):
        return (
            httpx.Response(404)
            if request.url.path == "/robots.txt"
            else httpx.Response(
                200, headers={"content-type": "text/html"}, text="<p>" + notice + "</p>"
            )
        )

    r = SourceRetriever(
        db,
        Config(cache=tmp_path / "cache"),
        transport=httpx.MockTransport(handler),
        resolve=False,
        sleep=lambda _: None,
    )
    try:
        s = r.fetch(URL)
        assert s.status == "soft_failed"
        assert catalog([s]) == []
        assert Path(s.raw_path).is_file()
    finally:
        r.close()


def test_soft_notice_false_positive_guard():
    assert not soft_failure(
        "Long substantive report", "An old page not found message was reported. " * 1000
    )


def test_recorded_search_rescues_failed_original_and_logs_provenance(tmp_path):
    old = "https://www.canada.ca/old-program"
    db = Database(tmp_path / "db")

    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        if req.url.path == "/old-program":
            return httpx.Response(404)
        return httpx.Response(
            200, headers={"content-type": "text/html"}, text="<p>" + ANSWER + "</p>"
        )

    r = SourceRetriever(
        db,
        Config(cache=tmp_path / "cache"),
        transport=httpx.MockTransport(handler),
        resolve=False,
        sleep=lambda _: None,
    )
    index = tmp_path / "index.json"
    index.write_text(
        json.dumps(
            [
                {
                    "question_id": question().question_id,
                    "url": URL,
                    "query": "official program date",
                    "provider": "test search",
                }
            ]
        )
    )
    search = Discovery(r, index)
    search.settings = {}
    found = search.collect(question().model_copy(update={"source_urls": [old]}))
    assert [s["status"] for s in found.sources] == ["failed", "ok"]
    assert any(row.get("query") == "official program date" for row in found.log)
    assert any(row.get("status") == "not_configured" for row in found.log)
    r.close()


def test_evidence_locations_are_generated_not_written_by_judge():
    source = Source(
        url=URL,
        status="ok",
        authoritative=True,
        sha256="abc",
        text="[L00001] A different statement about the program.\n[L00002] " + ANSWER,
    )
    extraction, _ = align(ANSWER, draft())
    units = rank_units(catalog([source]), ANSWER)
    selected = next(u for u in units if u.locator == "L00002")
    decision = EvidenceJudgment(
        verdict="supported",
        evidence=[
            EvidenceUse(
                evidence_id=selected.evidence_id,
                temporal_match=True,
                jurisdiction_match=True,
                explanation="Explicit founding date",
            )
        ],
        explanation="Direct evidence",
    )
    judgment, errors = materialize(extraction.claims[0], decision, units, [source])
    assert errors == []
    assert judgment.citations[0].exact_excerpt == ANSWER
    assert judgment.citations[0].locator == "L00002"
    decision.evidence[0].evidence_id = "invented-ID"
    judgment, errors = materialize(extraction.claims[0], decision, units, [source])
    assert errors and judgment.verdict == "insufficient" and judgment.citations == []


def test_long_document_can_find_evidence_past_old_prefix_limit():
    text = "\n".join(
        f"[L{i:05d}] Boilerplate filler concerning unrelated items." for i in range(1, 600)
    )
    text += "\n[L00600] " + ANSWER
    units = catalog([Source(url=URL, status="ok", authoritative=True, sha256="x", text=text)])
    assert any(u.locator == "L00600" for u in rank_units(units, ANSWER, limit=4))


def test_shared_sentence_anchors_keep_distinct_complete_assertions():
    data = draft()
    data.claims.append(
        data.claims[0].model_copy(update={"assertion": "The program existed during 2004."})
    )
    extraction, errors = align(ANSWER, data)
    assert errors == []
    assert (
        extraction_errors(
            ANSWER, extraction, Coverage(complete=True, omitted_claims=[], explanation="all")
        )
        == []
    )
    data.claims[0].answer_quote = "A nonexistent quote"
    _, errors = align(ANSWER, data)
    assert any("extraction_alignment" in e for e in errors)


def test_m2_guard_for_recall_operation():
    def call(*args):
        return MetricV2(
            primary_metric="M2",
            suitable=True,
            explanation="Named government program",
            tested_operation="recall",
            required_relationships=[],
        )

    result = assess_metric(question(), "M2 roles; M7 recall", call)
    assert result.primary_metric == "M7" and result.review_flags


def test_alignment_restores_case_typography_and_original_offsets_without_guessing_words():
    answer = "On the other hand, the CFIA is responsible for Canada’s labels."
    item = (
        draft()
        .claims[0]
        .model_copy(
            update={
                "answer_quote": "The CFIA is responsible for Canada's labels.",
                "assertion": "The CFIA is responsible for Canada's labels.",
            }
        )
    )
    data = draft().model_copy(
        update={"claims": [item], "nonfactual_spans": ["On the other hand, "]}
    )
    extraction, errors = align(answer, data)
    assert errors == []
    c = extraction.claims[0]
    assert answer[c.answer_start : c.answer_end] == answer
    assert c.assertion == "The CFIA is responsible for Canada's labels."
    changed = item.model_copy(
        update={"answer_quote": "The CFIA is not responsible for Canada's labels."}
    )
    with pytest.raises(ValueError, match="extraction_alignment"):
        align(answer, data.model_copy(update={"claims": [changed]}))


def test_short_atomic_anchors_keep_their_original_predicate_context():
    from canadianness_eval.verification.alignment import contextualize

    answer = "Canada can impose an arms embargo and an asset freeze."
    item = (
        draft()
        .claims[0]
        .model_copy(
            update={
                "answer_quote": "an asset freeze",
                "assertion": "Canada can impose an asset freeze.",
            }
        )
    )
    extraction, errors = align(answer, draft().model_copy(update={"claims": [item]}))
    assert errors == []
    assert extraction.claims[0].text == answer
    assert extraction.claims[0].assertion == item.assertion
    assert (
        contextualize(extraction.claims[0], answer).model_dump()
        == extraction.claims[0].model_dump()
    )


class Judge:
    model_id = "gpt-oss-120b-test"

    def __init__(self, calls, insufficient=False):
        self.calls, self.insufficient = calls, insufficient

    def discover(self):
        return [self.model_id]

    def close(self):
        pass

    def generate(self, prompt, schema):
        self.calls.append(schema.__name__)
        payload = json.loads(prompt.split("\nDATA:\n")[1])
        if schema == ExtractionDraft:
            return draft()
        if schema == CoverageV2:
            return CoverageV2(
                complete=True,
                omitted_claims=[],
                explanation="All covered",
                assertion_alignment_errors=[],
            )
        if schema == EvidenceJudgment:
            unit = next(p for p in payload["passages"] if ANSWER in p["exact_excerpt"])
            return EvidenceJudgment(
                verdict="insufficient" if self.insufficient else "supported",
                evidence=[]
                if self.insufficient
                else [
                    EvidenceUse(
                        evidence_id=unit["evidence_id"],
                        temporal_match=True,
                        jurisdiction_match=True,
                        explanation="Exact date",
                    )
                ],
                explanation="Test decision",
            )
        if schema == SupportChecks:
            return SupportChecks(
                checks=[
                    SupportCheck(
                        claim_id=c["claim_id"],
                        entailed=True,
                        missing_conditions=[],
                        explanation="All conditions",
                    )
                    for c in payload["claims"]
                ]
            )
        if schema == MetricV2:
            return MetricV2(
                primary_metric="M7",
                suitable=True,
                explanation="Date recall",
                tested_operation="recall",
                required_relationships=[],
            )
        from canadianness_eval.verification.models import Proposal

        if schema == Proposal:
            return Proposal(
                corrected_answer="",
                missing_information=["Date evidence"],
                disposition="revise",
                explanation="Missing proof is not false",
            )
        raise AssertionError(schema)


@pytest.mark.parametrize("insufficient", [False, True])
def test_v2_real_module_flow_resume_audit_and_unverified_status(tmp_path, insufficient):
    db = Database(tmp_path / "db")
    db.ingest([question()])
    cfg = Config(cache=tmp_path / "cache", workers=1)

    def handler(req):
        return (
            httpx.Response(404)
            if req.url.path == "/robots.txt"
            else httpx.Response(
                200, headers={"content-type": "text/html"}, text="<p>" + ANSWER + "</p>"
            )
        )

    r = SourceRetriever(
        db, cfg, transport=httpx.MockTransport(handler), resolve=False, sleep=lambda _: None
    )
    calls = []
    p = PipelineV2(
        db,
        cfg,
        Settings(key="test"),
        "Definitions",
        r,
        gateway_factory=lambda: Judge(calls, insufficient),
        baseline_events={question().question_id: "OLD-EVENT"},
    )
    try:
        assert p.run(10)["researched"] == 1
        result = db.results()[0][1]
        assert isinstance(result, ResearchV2)
        assert result.reference_status == (
            "needs_more_evidence" if insufficient else "fully_supported"
        )
        assert result.proposal.disposition == ("needs_more_evidence" if insufficient else "accept")
        assert not result.corrected_answer_verified
        before = list(calls)
        assert p.run(10)["attempted"] == 0 and before == calls
        assert len(db.audits()) == 1 and db.audits()[0]["baseline_event_id"] == "OLD-EVENT"
        db.check_integrity()
        export_package(db, tmp_path / "package")
        assert db.results()[0][0] == result.event_id
    finally:
        p.close()
        r.close()


def test_technical_finalization_is_idempotent_and_preserves_source_audits(tmp_path):
    import importlib.util

    db = Database(tmp_path / "pilot.sqlite3")
    questions = [question().model_copy(update={"question_id": f"Q{i}"}) for i in range(10)]
    db.ingest(questions)
    cfg = Config(cache=tmp_path / "cache", workers=2)

    def handler(req):
        return (
            httpx.Response(404)
            if req.url.path == "/robots.txt"
            else httpx.Response(
                200, headers={"content-type": "text/html"}, text="<p>" + ANSWER + "</p>"
            )
        )

    retriever = SourceRetriever(
        db, cfg, transport=httpx.MockTransport(handler), resolve=False, sleep=lambda _: None
    )
    calls = []
    pipeline = PipelineV2(
        db,
        cfg,
        Settings(key="test"),
        "Definitions",
        retriever,
        gateway_factory=lambda: Judge(calls),
    )
    try:
        assert pipeline.run(10)["researched"] == 10
    finally:
        pipeline.close()
        retriever.close()
    original_events = [r[0] for r in db.results()]
    count = len(calls)
    path = Path(__file__).resolve().parents[1] / "scripts/finalize_verification_spans.py"
    spec = importlib.util.spec_from_file_location("span_finalizer_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.finalize(tmp_path)
    module.finalize(tmp_path)
    final = Database(tmp_path / "pilot-validated.sqlite3")
    assert len(final.audits()) == 10
    assert [r[0] for r in db.results()] == original_events
    assert len(calls) == count
