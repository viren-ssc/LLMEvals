"""Reference research tests: retrieval is HTTP-mocked, judges are schema-validated fakes."""

import gzip
import hashlib
import io
import json
from pathlib import Path

import httpx
import pytest
from openpyxl import Workbook, load_workbook
from pydantic import ValidationError

from canadianness_eval.settings import Settings
from canadianness_eval.verification.cli import main
from canadianness_eval.verification.config import Config
from canadianness_eval.verification.db import Conflict, Database, process_lock
from canadianness_eval.verification.export import export_package, verify_package
from canadianness_eval.verification.gates import citation_errors, extraction_errors
from canadianness_eval.verification.local_io import load_inputs
from canadianness_eval.verification.models import (
    Citation,
    Claim,
    Coverage,
    Extraction,
    Judgment,
    MetricAssessment,
    Proposal,
    Question,
    Source,
)
from canadianness_eval.verification.pipeline import Pipeline, SourceCandidates
from canadianness_eval.verification.sources import SourceRetriever

URL = "https://www.canada.ca/official-test"
ANSWER = "Ottawa is the capital of Canada."


def question(qid="GC-ADD-0012"):
    return Question(
        question_id=qid,
        question="What is Canada's capital?",
        answer=ANSWER,
        metric="M7",
        source_urls=[URL],
        original_row={"reference_answer": ANSWER},
        queue_row={"status": "pending"},
    )


def claim():
    return Claim(
        text=ANSWER,
        answer_start=0,
        answer_end=len(ANSWER),
        material=True,
        temporal_scope="current",
        relevant_date="",
        jurisdiction="Canada",
    )


class FakeGateway:
    def __init__(self, calls, bad_citation=False, fail_question=None):
        self.model_id = "gpt-oss-120b-test"
        self.calls = calls
        self.bad_citation = bad_citation
        self.fail_question = fail_question

    def discover(self):
        return [self.model_id]

    def close(self):
        pass

    def generate(self, prompt, schema):
        self.calls.append(schema.__name__)
        payload = json.loads(prompt.split("\nDATA:\n", 1)[1])
        if schema == Extraction:
            if payload["question"] == self.fail_question:
                raise RuntimeError("fake partial failure")
            return Extraction(
                claims=[claim()], nonfactual_spans=[], coverage_explanation="All factual text"
            )
        if schema == Coverage:
            return Coverage(
                complete=True, omitted_claims=[], explanation="All assertions extracted"
            )
        if schema == SourceCandidates:
            return SourceCandidates(urls=[], explanation="Use supplied primary source")
        if schema == Judgment:
            source = payload["sources"][0]
            return Judgment(
                verdict="supported",
                citations=[
                    Citation(
                        source_url=source["url"],
                        source_sha256=source["sha256"],
                        locator="L00002",
                        exact_excerpt="Invented evidence" if self.bad_citation else ANSWER,
                        attributed_summary="Government identifies Ottawa",
                        temporal_match=True,
                        jurisdiction_match=True,
                        explanation="Explicit capital statement",
                    )
                ],
                explanation="Direct support",
            )
        if schema == MetricAssessment:
            return MetricAssessment(
                primary_metric="M7", suitable=True, explanation="Factual recall"
            )
        if schema == Proposal:
            return Proposal(
                corrected_answer=ANSWER,
                missing_information=[],
                disposition="accept",
                explanation="All original factual assertions supported",
            )
        raise AssertionError(schema)


@pytest.fixture
def setup_pipeline(tmp_path):
    db = Database(tmp_path / "research.sqlite3")
    config = Config(database=db.path, cache=tmp_path / "cache", workers=2)
    requests = []

    def handler(request):
        requests.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<title>Official</title><p>" + ANSWER + "</p>",
        )

    retriever = SourceRetriever(
        db, config, transport=httpx.MockTransport(handler), sleep=lambda _: None, resolve=False
    )
    calls = []

    def factory(**kwargs):
        return Pipeline(
            db,
            config,
            Settings(key="test"),
            "Seven metric definitions",
            retriever,
            gateway_factory=lambda: FakeGateway(calls, **kwargs),
        )

    yield db, retriever, calls, requests, factory
    retriever.close()


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def test_end_to_end_delta_package_and_resume(setup_pipeline, tmp_path):
    db, _, calls, requests, factory = setup_pipeline
    db.ingest([question()])
    pipeline = factory()
    assert pipeline.run(10)["researched"] == 1
    pipeline.close()
    result = db.results()[0][1]
    assert result.fully_supported
    assert result.proposal.disposition == "accept"
    assert not result.corrected_answer_verified
    assert len(db.audits()) == 1
    assert len(requests) == 2
    before = list(calls)
    db.recover()
    assert pipeline.run(10)["attempted"] == 0
    assert calls == before
    target = tmp_path / "package"
    manifest = export_package(db, target)
    assert manifest["counts"]["proposed_updates"] == 1
    assert manifest["counts"]["claims"] == 1
    assert verify_package(target)["files"]
    assert export_package(db, target)["content_signature"] == manifest["content_signature"]
    updates = json.loads((target / "proposed_updates.jsonl").read_text())
    assert updates["question_id"] == "GC-ADD-0012"
    assert "original_row" not in updates
    assert updates["human_approval"] == updates["independent_ai_audit"] == ""
    (target / "claims.jsonl").write_text("tampered")
    with pytest.raises(Conflict, match="hash mismatch"):
        verify_package(target)


def test_interrupted_task_reuses_all_saved_steps(setup_pipeline):
    db, _, calls, _, factory = setup_pipeline
    db.ingest([question()])
    pipeline = factory()
    original = db.finish
    db.finish = lambda _: (_ for _ in ()).throw(KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        pipeline.process(question().question_id)
    assert db.report()["states"] == {"running": 1}
    saved_calls = list(calls)
    db.finish = original
    db.recover()
    pipeline.process(question().question_id)
    assert calls == saved_calls
    with db.connect() as c:
        outcomes = [r[0] for r in c.execute("SELECT outcome FROM attempts ORDER BY attempt")]
    assert outcomes == ["interrupted", "researched"]
    assert len(db.results()) == len(db.audits()) == 1
    pipeline.close()


def test_partial_failure_does_not_repeat_success(setup_pipeline):
    db, _, calls, _, factory = setup_pipeline
    bad = question("Q2").model_copy(update={"question": "Fail this question"})
    db.ingest([question(), bad])
    pipeline = factory(fail_question="Fail this question")
    report = pipeline.run(10)
    pipeline.close()
    assert report["researched"] == report["failed"] == 1
    assert db.pending(100) == []
    assert db.pending(100, retry_failed=True) == ["Q2"]
    before = calls.count("Extraction")
    retry = factory()
    assert retry.run(100, retry_failed=True)["researched"] == 1
    assert calls.count("Extraction") == before + 1
    assert len(db.results()) == 2
    retry.close()


def test_incorrect_citation_blocks_support_and_accept(setup_pipeline):
    db, _, _, _, factory = setup_pipeline
    db.ingest([question()])
    pipeline = factory(bad_citation=True)
    pipeline.run(1)
    result = db.results()[0][1]
    assert not result.fully_supported
    assert result.proposal.disposition == "unresolved"
    assert result.claims[0].judgment.verdict == "insufficient"
    assert any("excerpt" in e for e in result.gate_errors)
    pipeline.close()


def test_duplicate_and_conflicting_imports_are_rejected(tmp_path):
    db = Database(tmp_path / "db")
    with pytest.raises(Conflict, match="Duplicate"):
        db.ingest([question(), question()])
    db.ingest([question()])
    db.ingest([question()])
    assert db.report()["total"] == 1
    with pytest.raises(Conflict, match="input changed"):
        db.ingest([question().model_copy(update={"answer": "Changed by a human"})])
    db.bind("original inputs")
    with pytest.raises(Conflict, match="configuration changed"):
        db.bind("changed inputs")
    db.bind_model("model-a")
    with pytest.raises(Conflict, match="judge model changed"):
        db.bind_model("model-b")


def test_import_existing_queue_skip_completed_and_preserve_original(tmp_path):
    benchmark = write_jsonl(
        tmp_path / "questions.jsonl",
        [
            {
                "question_id": "Q1",
                "question": "Q?",
                "reference_answer": "A.",
                "metric": "M7",
                "source_urls": [URL],
                "human_approval": "Approved",
                "original_evidence": "WARC excerpt",
            },
            {
                "question_id": "GC-ADD-0012",
                "question": "Q?",
                "reference_answer": ANSWER,
                "metric": "M2",
            },
        ],
    )
    queue = write_jsonl(
        tmp_path / "queue.jsonl",
        [
            {"question_id": "Q1", "status": "Research saved"},
            {"question_id": "GC-ADD-0012", "status": "Pending"},
        ],
    )
    before = benchmark.read_bytes(), queue.read_bytes()
    questions, progress = load_inputs(benchmark, queue, expected_queue=2)
    assert [q.question_id for q in questions] == ["GC-ADD-0012"]
    assert progress["queue_completed_on_import"] == 1
    assert before == (benchmark.read_bytes(), queue.read_bytes())
    with pytest.raises(Conflict, match="Expected 100"):
        load_inputs(benchmark, queue)
    write_jsonl(queue, [{"question_id": "Q1", "status": "typo"}])
    with pytest.raises(Conflict, match="Unknown queue status"):
        load_inputs(benchmark, queue, expected_queue=1)


def test_excel_import_and_network_free_dry_run(tmp_path, monkeypatch):
    book = Workbook()
    questions = book.active
    questions.title = "Questions"
    questions.append(["Question ID", "Question", "Original proposed answer", "Original metric"])
    questions.append(["GC-ADD-0012", "Q?", ANSWER, "M2"])
    queue = book.create_sheet("Cycle 100 Queue")
    queue.append(["Question ID", "Cycle status"])
    queue.append(["GC-ADD-0012", "Pending"])
    path = tmp_path / "input.xlsx"
    book.save(path)
    before = path.read_bytes()
    monkeypatch.setattr(httpx.Client, "request", lambda *a, **k: pytest.fail("Unexpected network"))
    dbpath = tmp_path / "no-database.sqlite3"
    code = main(
        [
            "--db",
            str(dbpath),
            "run",
            "--benchmark",
            str(path),
            "--queue",
            str(path),
            "--expected-queue",
            "1",
            "--instructions",
            str(Path(__file__)),
            "--dry-run",
        ]
    )
    assert code == 0
    assert not dbpath.exists()
    assert path.read_bytes() == before


def test_invalid_metric_and_coverage_rejected(tmp_path):
    with pytest.raises(ValidationError):
        question().model_copy().model_validate({**question().model_dump(), "metric": "M8"})
    partial = Extraction(claims=[claim()], nonfactual_spans=[], coverage_explanation="test")
    assert extraction_errors(
        ANSWER + " There are 99 provinces.",
        partial,
        Coverage(complete=True, omitted_claims=[], explanation="bad reviewer"),
    )
    assert extraction_errors(
        ANSWER,
        partial,
        Coverage(complete=False, omitted_claims=["Missing fact"], explanation="missing"),
    )


@pytest.mark.parametrize(
    "change", ["url", "hash", "excerpt", "locator", "temporal", "jurisdiction", "historical"]
)
def test_provenance_mismatches_cannot_pass(change):
    source = Source(
        url=URL,
        final_url=URL,
        status="ok",
        authoritative=True,
        sha256="hash",
        text="[L00001] Other section.\n[L00002] " + ANSWER,
    )
    citation = Citation(
        source_url=URL,
        source_sha256="hash",
        locator="L00002",
        exact_excerpt=ANSWER,
        attributed_summary="Capital",
        temporal_match=True,
        jurisdiction_match=True,
        explanation="Direct",
    )
    if change == "url":
        citation.source_url = "https://www.canada.ca/not-inspected"
    elif change == "hash":
        citation.source_sha256 = "wrong"
    elif change == "excerpt":
        citation.exact_excerpt = "Made up"
    elif change == "locator":
        citation.locator = "L00001"
    elif change == "temporal":
        citation.temporal_match = False
    elif change == "jurisdiction":
        citation.jurisdiction_match = False
    else:
        source.historical = True
    assert citation_errors(
        claim(), Judgment(verdict="supported", citations=[citation], explanation="test"), [source]
    )


def test_fetch_cache_and_broken_url_are_not_contradictions(setup_pipeline):
    db, retriever, _, requests, _ = setup_pipeline
    first = retriever.fetch(URL)
    second = retriever.fetch(URL)
    assert first.sha256 == second.sha256
    assert len(requests) == 2
    Path(first.raw_path).write_bytes(b"corrupted")
    assert retriever.fetch(URL).status == "ok"
    assert len(requests) == 3
    assert db.source_get("not found") is None


@pytest.mark.parametrize("status", [403, 404, 500])
def test_source_http_failure_never_becomes_false_claim(tmp_path, status):
    db = Database(tmp_path / "db")
    requests = []

    def handler(r):
        requests.append(r.url.path)
        return httpx.Response(404 if r.url.path == "/robots.txt" else status)

    retriever = SourceRetriever(
        db,
        Config(cache=tmp_path / "cache"),
        resolve=False,
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )
    result = retriever.fetch(URL)
    assert result.status in {"failed", "blocked"}
    assert not result.text
    assert len(requests) == (4 if status == 500 else 2)
    retriever.close()


def test_robots_and_unsafe_redirect_are_respected(tmp_path):
    db = Database(tmp_path / "db")
    calls = []

    def blocked(r):
        calls.append(r.url.path)
        return httpx.Response(200, text="User-agent: *\nDisallow: /\n")

    retriever = SourceRetriever(
        db,
        Config(cache=tmp_path / "cache"),
        resolve=False,
        transport=httpx.MockTransport(blocked),
        sleep=lambda _: None,
    )
    assert retriever.fetch(URL).status == "blocked"
    assert calls == ["/robots.txt"]
    retriever.close()

    def redirect(r):
        if r.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    retriever = SourceRetriever(
        db,
        Config(cache=tmp_path / "cache"),
        resolve=False,
        transport=httpx.MockTransport(redirect),
        sleep=lambda _: None,
    )
    assert retriever.fetch(URL + "-redirect").status == "failed"
    retriever.close()


def test_warc_retains_historical_snapshot_separate_from_current(tmp_path):
    from warcio.statusandheaders import StatusAndHeaders
    from warcio.warcwriter import WARCWriter

    buffer = io.BytesIO()
    writer = WARCWriter(buffer, gzip=True)
    record = writer.create_warc_record(
        URL,
        "response",
        payload=io.BytesIO(ANSWER.encode()),
        http_headers=StatusAndHeaders(
            "200 OK", [("Content-Type", "text/plain")], protocol="HTTP/1.1"
        ),
        warc_headers_dict={"WARC-Date": "2012-01-01T00:00:00Z"},
    )
    writer.write_record(record)
    path = tmp_path / "historical.warc.gz"
    path.write_bytes(buffer.getvalue())
    db = Database(tmp_path / "db")
    retriever = SourceRetriever(db, Config(cache=tmp_path / "cache"), resolve=False)
    assert retriever.import_warc(path) == 1
    assert retriever.import_warc(path) == 1
    archives = db.archives(URL)
    assert len(archives) == 1
    assert archives[0].historical and archives[0].archive_date.startswith("2012")
    assert Path(archives[0].raw_path).read_text() == ANSWER
    assert db.source_get("web:" + hashlib.sha256(URL.encode()).hexdigest()) is None
    assert any(p.suffix == ".warc" for p in retriever.config.cache.iterdir())
    retriever.close()


def test_export_formula_text_is_literal_and_original_input_protected(setup_pipeline, tmp_path):
    db, _, _, _, factory = setup_pipeline
    db.ingest([question()])
    p = factory()
    p.run(1)
    p.close()
    with db.transaction() as c:
        row = c.execute("SELECT event_id,payload FROM audit").fetchone()
        audit = json.loads(row[1])
        audit["reason"] = '=HYPERLINK("https://malicious.invalid")'
        c.execute("UPDATE audit SET payload=? WHERE event_id=?", (json.dumps(audit), row[0]))
    target = tmp_path / "export"
    with pytest.raises(Conflict, match="original input"):
        export_package(db, target, [target / "benchmark.xlsx"])
    export_package(db, target)
    book = load_workbook(target / "results.xlsx")
    sheet = book["audit"]
    column = [c.value for c in sheet[1]].index("reason") + 1
    assert sheet.cell(2, column).data_type == "s"
    book.close()


def test_process_lock_blocks_duplicate_writer(tmp_path):
    path = tmp_path / "pipeline.lock"
    with process_lock(path):
        with pytest.raises(Conflict, match="Another process"):
            with process_lock(path):
                pytest.fail("Duplicate writer acquired the lock")
    with process_lock(path):
        pass


def test_hundred_question_batch_reuses_source_and_exports_stable_ids(setup_pipeline, tmp_path):
    db, _, calls, requests, factory = setup_pipeline
    db.ingest([question(f"EXISTING-{i:04d}") for i in range(100)])
    pipeline = factory()
    report = pipeline.run(100)
    pipeline.close()
    assert report["attempted"] == report["researched"] == 100
    assert report["failed"] == 0
    assert report["questions_per_minute"] > 0
    assert len(requests) == 2
    manifest = export_package(db, tmp_path / "hundred")
    assert manifest["counts"]["proposed_updates"] == 100
    assert manifest["counts"]["claims"] == 100
    assert manifest["counts"]["audit"] == 100
    assert db.report()["fully_supported"] == 100
    assert len({r[1].claims[0].claim_id for r in db.results()}) == 100


def test_inconsistent_progress_counts_block_export(setup_pipeline, tmp_path):
    db, _, _, _, factory = setup_pipeline
    db.ingest([question()])
    pipeline = factory()
    pipeline.run(1)
    pipeline.close()
    with db.transaction() as c:
        c.execute("DELETE FROM audit")
    with pytest.raises(Conflict, match="Progress count inconsistent"):
        export_package(db, tmp_path / "invalid-package")


def test_queue_reordering_changes_resume_signature(tmp_path):
    benchmark = write_jsonl(
        tmp_path / "benchmark.jsonl",
        [
            {"question_id": qid, "question": "Q?", "reference_answer": ANSWER, "metric": "M7"}
            for qid in ("Q1", "Q2")
        ],
    )
    queue = tmp_path / "queue.jsonl"
    rows = [{"question_id": qid, "status": "Pending"} for qid in ("Q1", "Q2")]
    write_jsonl(queue, rows)
    _, first = load_inputs(benchmark, queue, expected_queue=2)
    write_jsonl(queue, list(reversed(rows)))
    _, second = load_inputs(benchmark, queue, expected_queue=2)
    assert first["input_signature"] != second["input_signature"]


def test_excel_with_txt_filename_is_read_by_content(tmp_path):
    book = Workbook()
    sheet = book.active
    sheet.title = "Questions"
    sheet.append(["Question ID", "Question", "Original proposed answer", "Original metric"])
    sheet.append(["GC-ADD-0012", "Q?", ANSWER, "M2"])
    queue = book.create_sheet("Cycle 100 Queue")
    queue.append(["Question ID", "Cycle status"])
    queue.append(["GC-ADD-0012", "Pending"])
    path = tmp_path / "misnamed.txt"
    book.save(path)
    before = path.read_bytes()
    questions, _ = load_inputs(path, path, expected_queue=1)
    assert questions[0].question_id == "GC-ADD-0012"
    assert path.read_bytes() == before


def test_gzipped_source_is_decoded_exactly_once(tmp_path):
    db = Database(tmp_path / "db")

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(
            200,
            headers={"content-type": "text/html", "content-encoding": "gzip"},
            content=gzip.compress(("<p>" + ANSWER + "</p>").encode()),
        )

    retriever = SourceRetriever(
        db,
        Config(cache=tmp_path / "cache"),
        resolve=False,
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )
    try:
        source = retriever.fetch(URL)
        assert source.status == "ok"
        assert ANSWER in source.text
    finally:
        retriever.close()


def test_whitespace_only_nonfactual_spans_do_not_invalidate_full_coverage():
    extraction = Extraction(
        claims=[claim()],
        nonfactual_spans=["", " ", "\n"],
        coverage_explanation="Full answer is a claim",
    )
    coverage = Coverage(complete=True, omitted_claims=[], explanation="No omissions")
    assert extraction_errors(ANSWER, extraction, coverage) == []
