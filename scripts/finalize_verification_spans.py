"""Idempotent technical span validation; no new model/source calls or independent approvals."""

# ruff: noqa: E402
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from canadianness_eval.verification.alignment import contextualize
from canadianness_eval.verification.db import Database, process_lock
from canadianness_eval.verification.export import export_package, verify_package
from canadianness_eval.verification.gates import extraction_errors, quality_errors
from canadianness_eval.verification.models import Proposal, Question, digest, now
from canadianness_eval.verification.v2_models import research_from_json


def finalize(directory=ROOT / "outputs/verification/pilot-final-20261104"):
    original = directory / "pilot.sqlite3"
    target = directory / "pilot-validated.sqlite3"
    package = directory / "results-span-validated"
    if target.exists() and package.exists():
        db = Database(target)
        db.check_integrity()
        verify_package(package)
        print(
            json.dumps(
                {"already_finalized": True, "local": db.report(), "new_audit_records": 0}, indent=2
            )
        )
        return
    with sqlite3.connect(f"file:{original.resolve().as_posix()}?mode=ro", uri=True) as c:
        rows = c.execute(
            "SELECT input,result FROM tasks WHERE state='researched' ORDER BY ordinal"
        ).fetchall()
    if len(rows) != 10:
        raise ValueError("Complete/resume the same-ten model pass before technical finalization")
    questions = [Question.model_validate_json(r[0]) for r in rows]
    with process_lock(target.with_suffix(".lock")):
        db = Database(target)
        db.bind(
            digest(
                {"kind": "exact context-span validation", "source_results": [r[1] for r in rows]}
            )
        )
        db.ingest(questions)
        db.recover()
        changes = []
        for question, (_, payload) in zip(questions, rows):
            if question.question_id not in db.pending(10, retry_failed=True):
                continue
            before = research_from_json(payload)
            after = before.model_copy(deep=True)
            for i, claim in enumerate(after.extraction.claims):
                updated = contextualize(claim, question.answer)
                after.extraction.claims[i] = updated
                after.claims[i].claim = updated
            after.alignment_errors = (
                extraction_errors(question.answer, after.extraction, after.coverage)
                + after.coverage.assertion_alignment_errors
            )
            after.gate_errors = after.alignment_errors + after.citation_selection_errors
            after.fully_supported = (
                not after.gate_errors
                and bool(after.claims)
                and all(c.judgment.verdict == "supported" for c in after.claims)
            )
            after.reference_status = (
                "extraction_error"
                if after.alignment_errors
                else "fully_supported"
                if after.fully_supported
                else "contradicted"
                if any(c.judgment.verdict == "contradicted" for c in after.claims)
                else "needs_more_evidence"
            )
            if after.fully_supported and not before.fully_supported:
                after.proposal = Proposal(
                    corrected_answer="",
                    missing_information=[],
                    disposition="accept"
                    if after.metric.primary_metric == question.metric and after.metric.suitable
                    else "revise",
                    explanation="Reference evidence verified after exact original-context span repair. "
                    "No assertions, source selections, or factual verdicts changed. Metric recommendations remain advisory.",
                )
            changed = after.model_dump() != before.model_dump()
            if changed:
                after.created_at = now()
                after.discovery_log.append(
                    {
                        "method": "technical_context_span_validation",
                        "at": after.created_at,
                        "previous_event_id": before.event_id,
                        "assertions_changed": False,
                        "evidence_verdicts_changed": False,
                    }
                )
                changes.append(
                    {
                        "question_id": question.question_id,
                        "previous_event_id": before.event_id,
                        "new_event_id": after.event_id,
                        "before_reference_status": before.reference_status,
                        "after_reference_status": after.reference_status,
                        "assertions_changed": False,
                        "evidence_verdicts_changed": False,
                        "claim_ids_preserved": True,
                    }
                )
            if issues := quality_errors(after):
                raise ValueError("; ".join(issues))
            db.start(question.question_id)
            db.finish(after)
        db.check_integrity()
        export_package(db, package)
        (directory / "span_validation_provenance.json").write_text(
            json.dumps(changes, indent=2), encoding="utf-8"
        )
        print(
            json.dumps(
                {"changes": changes, "local": db.report(), "package": str(package)}, indent=2
            )
        )


if __name__ == "__main__":
    finalize()
