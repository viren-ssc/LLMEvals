"""Compare preserved pilot evidence and linked research revisions, without approving either."""

# ruff: noqa: E402
import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from canadianness_eval.verification.db import Database
from canadianness_eval.verification.evidence import materialize, rank_units
from canadianness_eval.verification.export import verify_package
from canadianness_eval.verification.gates import citation_errors, extraction_errors
from canadianness_eval.verification.models import Question
from canadianness_eval.verification.sources import soft_failure
from canadianness_eval.verification.v2_models import EvidenceJudgment, research_from_json


def read_database(path):
    with sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True) as c:
        results = {
            qid: research_from_json(payload)
            for qid, payload in c.execute(
                "SELECT id,result FROM tasks WHERE state='researched' ORDER BY ordinal"
            )
        }
        inputs = {
            qid: Question.model_validate_json(payload)
            for qid, payload in c.execute("SELECT id,input FROM tasks")
        }
        audits = c.execute(
            "SELECT count(*),count(DISTINCT question_id),count(DISTINCT event_id) FROM audit"
        ).fetchone()
        events = dict(c.execute("SELECT task_id,id FROM events"))
    return results, inputs, audits, events


def compare(args):
    old, inputs, old_audits, old_events = read_database(args.baseline / "pilot-recovered.sqlite3")
    new, _, new_audits, new_events = read_database(args.current / args.database_name)
    if len(old) != 10 or set(old) != set(new):
        raise ValueError("Exactly the same ten completed IDs are required for comparison")
    verify_package(args.baseline / "results")
    verify_package(args.current / args.package_name)
    Database(args.current / args.database_name).check_integrity()
    if new_audits != (10, 10, 10) or any(new[q].baseline_event_id != old_events[q] for q in old):
        raise ValueError("Audit uniqueness or baseline revision links failed")
    protection = json.loads(args.protection.read_text(encoding="utf-8"))
    unchanged = all(
        hashlib.sha256(Path(r["path"]).read_bytes()).hexdigest() == r["sha256"] for r in protection
    )
    if not unchanged:
        raise ValueError("An original input or first-pilot artifact changed")
    old_sources = [
        json.loads(s)
        for s in (args.baseline / "results/sources.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    new_sources = [
        json.loads(s)
        for s in (args.current / args.package_name / "sources.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    old_notices = [
        s for s in old_sources if s["status"] == "ok" and soft_failure(s["title"], s["text"])
    ]
    accepted_notices = [
        s for s in new_sources if s["status"] == "ok" and soft_failure(s["title"], s["text"])
    ]
    old_counts = Counter(s["status"] for s in old_sources)
    new_counts = Counter(s["status"] for s in new_sources)
    attempts = {}
    for r in new.values():
        for row in r.discovery_log:
            if "url" in row and "status" in row:
                attempts[row["url"]] = row["status"]
    attempt_counts = Counter(attempts.values())
    rows = []
    mapping = []
    for qid, before in old.items():
        after = new[qid]
        rows.append(
            {
                "question_id": qid,
                "before_fully_supported": before.fully_supported,
                "after_fully_supported": after.fully_supported,
                "before_disposition": before.proposal.disposition,
                "after_disposition": after.proposal.disposition,
                "reference_status": after.reference_status,
                "before_claims": len(before.claims),
                "after_claims": len(after.claims),
                "before_insufficient": sum(
                    c.judgment.verdict != "supported" for c in before.claims
                ),
                "after_insufficient": sum(c.judgment.verdict != "supported" for c in after.claims),
                "before_alignment_errors": extraction_errors(
                    inputs[qid].answer, before.extraction, before.coverage
                ),
                "after_alignment_errors": after.alignment_errors,
                "original_metric": inputs[qid].metric,
                "old_recommended_metric": before.metric.primary_metric,
                "new_recommended_metric": after.metric.primary_metric,
                "metric_review_flags": after.metric.review_flags,
                "baseline_event_id": old_events[qid],
                "revision_event_id": new_events[qid],
            }
        )
        for claim in before.claims:
            relevant = [
                c
                for c in after.claims
                if max(c.claim.answer_start, claim.claim.answer_start)
                < min(c.claim.answer_end, claim.claim.answer_end)
            ]
            status = (
                "extraction_error"
                if after.alignment_errors or not relevant
                else "supported"
                if all(c.judgment.verdict == "supported" for c in relevant)
                else "needs_more_evidence"
            )
            mapping.append(
                {
                    "question_id": qid,
                    "baseline_claim_id": claim.claim_id,
                    "baseline_text": claim.claim.text,
                    "before_verdict": claim.judgment.verdict,
                    "mapped_after_status": status,
                    "new_claim_ids": [c.claim_id for c in relevant],
                    "method": "conservative shared-anchor mapping: all overlapping new assertions must be supported",
                }
            )
    selection_errors = [e for r in new.values() for e in r.citation_selection_errors]
    rejected_selections = []
    with sqlite3.connect(
        f"file:{(args.current / 'pilot.sqlite3').resolve().as_posix()}?mode=ro", uri=True
    ) as c:
        for qid, result in new.items():
            for claim in result.claims:
                row = c.execute(
                    "SELECT value FROM steps WHERE task_id=? AND name=?",
                    (qid, "select_v3:" + claim.claim_id),
                ).fetchone()
                if not row:
                    continue
                decision = EvidenceJudgment.model_validate_json(row[0])
                selected = rank_units(
                    result.evidence_catalog, claim.claim.assertion + " " + inputs[qid].question
                )
                for use in decision.evidence:
                    _, problems = materialize(
                        claim.claim,
                        EvidenceJudgment(
                            verdict="insufficient",
                            evidence=[use],
                            explanation="Comparison validation",
                        ),
                        selected,
                        result.sources,
                    )
                    if problems:
                        rejected_selections.append(
                            {
                                "question_id": qid,
                                "claim_id": claim.claim_id,
                                "evidence_id": use.evidence_id,
                                "errors": problems,
                            }
                        )
    structural_errors = [
        e
        for r in new.values()
        for c in r.claims
        for e in citation_errors(c.claim, c.judgment, r.sources)
    ]
    prior_insufficient = [r for r in mapping if r["before_verdict"] != "supported"]
    baseline_inspection = json.loads(
        (args.baseline / "inspection_report.json").read_text(encoding="utf-8")
    )
    summary = {
        "questions": 10,
        "originals_and_baseline_unchanged": unchanged,
        "protected_files_checked": len(protection),
        "baseline_audits": old_audits,
        "final_audits": new_audits,
        "baseline_links_verified": True,
        "fully_supported": {
            "before": sum(r.fully_supported for r in old.values()),
            "after": sum(r.fully_supported for r in new.values()),
        },
        "native_claim_counts": {
            "before": sum(len(r.claims) for r in old.values()),
            "after": sum(len(r.claims) for r in new.values()),
        },
        "native_unsupported_counts": {
            "before": sum(
                c.judgment.verdict != "supported" for r in old.values() for c in r.claims
            ),
            "after": sum(c.judgment.verdict != "supported" for r in new.values() for c in r.claims),
        },
        "original_26_objects_conservatively_mapped": dict(
            Counter(r["mapped_after_status"] for r in prior_insufficient)
        ),
        "claim_mapping_caveat": "Atomic decomposition changed. Shared-anchor mapping is conservative and is not a new independent adjudication of the old extraction objects.",
        "alignment_or_coverage_failed_questions": {
            "before_recomputed": sum(bool(r["before_alignment_errors"]) for r in rows),
            "after": sum(bool(r["after_alignment_errors"]) for r in rows),
        },
        "rejected_citation_records_before": baseline_inspection["rejected_citation_records"],
        "selection_errors_after": len(selection_errors),
        "rejected_evidence_selections_after": len(rejected_selections),
        "exported_citation_errors_after": len(structural_errors),
        "validated_citations_after": sum(
            len(c.judgment.citations) for r in new.values() for c in r.claims
        ),
        "sources_before": dict(old_counts),
        "sources_after_exported_inventory": dict(new_counts),
        "logical_candidate_outcomes_after": dict(attempt_counts),
        "unnoticed_soft_failures_before": len(old_notices),
        "soft_failures_accepted_after": len(accepted_notices),
        "soft_failures_detected_after": new_counts.get("soft_failed", 0),
        "source_denominator_caveat": "Counts are distinct URL-candidate records, not network requests. Final verification reuses the improved live retrieval pass snapshots. The improved pass searches observed links and a recorded official-search index rather than retrying all 83 historical guesses.",
        "reference_statuses_after": dict(Counter(r.reference_status for r in new.values())),
        "proposal_statuses_after": dict(Counter(r.proposal.disposition for r in new.values())),
        "independent_approvals": 0,
    }
    args.current.mkdir(parents=True, exist_ok=True)
    reviews = [
        {
            "question_id": "GC-ADD-0037",
            "finding": "The model reports a contradiction concerning postsecondary responsibility. Its cited CMEC passage also directly describes the collective education-ministry responsibilities in the reference. Whether the plural original means one universal ministry or collective ministries needs adjudication; do not treat this as an independently confirmed false answer.",
        },
        {
            "question_id": "GC-ADD-0039",
            "finding": "The stronger semantic reviewer does not consider evidence of a transfer for the stated policy areas sufficient to establish the word main. This is needs_more_evidence, not a proven false program identification.",
        },
        {
            "question_id": "ALL",
            "finding": "Metric recommendations, including M2/M7 institutional-function boundaries, remain advisory. All corrected drafts are unverified; no human or independent AI approval is present.",
        },
    ]
    (args.current / "inspection_findings.json").write_text(
        json.dumps(reviews, indent=2), encoding="utf-8"
    )
    (args.current / "comparison.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    for name, records in [("question_comparison", rows), ("baseline_claim_mapping", mapping)]:
        (args.current / (name + ".jsonl")).write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8"
        )
    table = [
        "| Measure | First pilot | Improved rerun |",
        "|---|---:|---:|",
        f"| Fully supported original answers | {summary['fully_supported']['before']} | {summary['fully_supported']['after']} |",
        f"| Questions with alignment/coverage failures | {summary['alignment_or_coverage_failed_questions']['before_recomputed']} | {summary['alignment_or_coverage_failed_questions']['after']} |",
        f"| Rejected citation records / evidence selections | {summary['rejected_citation_records_before']} | {len(rejected_selections)} |",
        f"| Invalid exported citations | 0 (rejected before export) | {len(structural_errors)} |",
        f"| HTTP 200 notice pages accepted as sources | {len(old_notices)} | {len(accepted_notices)} |",
        f"| Native unsupported/insufficient extraction objects | {summary['native_unsupported_counts']['before']} | {summary['native_unsupported_counts']['after']} |",
    ]
    detail = [
        "| Question | Before supported | After supported | Reference status | Proposed metric |",
        "|---|---|---|---|---|",
    ]
    detail += [
        f"| {r['question_id']} | {r['before_fully_supported']} | {r['after_fully_supported']} | {r['reference_status']} | {r['new_recommended_metric']} |"
        for r in rows
    ]
    text = (
        "# Verification comparison — same ten questions\n\n"
        + "\n".join(table)
        + "\n\n"
        + "Native claim counts changed from "
        + str(summary["native_claim_counts"]["before"])
        + " to "
        + str(summary["native_claim_counts"]["after"])
        + " because complete assertions and list items were re-extracted. Do not treat the raw unsupported-count change as a paired count of identical claims. "
        + "The original 26 insufficient objects map conservatively as follows: "
        + json.dumps(summary["original_26_objects_conservatively_mapped"])
        + ". See baseline_claim_mapping.jsonl for every stable original claim ID.\n\n"
        + "## Retrieval\n\nFirst-pilot candidate records: "
        + json.dumps(dict(old_counts))
        + ". Improved logical URL-candidate outcomes: "
        + json.dumps(dict(attempt_counts))
        + ". Improved exported inventory after alias deduplication: "
        + json.dumps(dict(new_counts))
        + ". "
        + summary["source_denominator_caveat"]
        + "\n\n"
        + "The public Canada.ca search page disallows automated fetching. This pilot used actual recorded official-source search results and observed official links; no live general-search API key was configured. BRAVE_SEARCH_API_KEY enables the optional live search adapter for unseen topics. Search snippets and migration notices are never claim evidence.\n\n"
        + "## Per-question outcomes\n\n"
        + "\n".join(detail)
        + "\n\n"
        + "## Interpretation and safeguards\n\nQuotes, hashes, line/page locations now come from actual retrieved passages. The model selects evidence IDs and an internal entailment check reviews semantic support, including claimed contradictions. This prevents fabricated locations but does not establish infallible semantic verification.\n\n"
        + "Claim alignment maps case and typography to exact original offsets; changed words, negation, facts or quantities are not fuzzily matched. Alignment failures are reported separately from insufficient evidence and explicit contradictions. Unverified correction drafts always have needs_more_evidence status. Metric proposals are blind to old labels, guarded for recall versus roles, and remain advisory.\n\n"
        + f"All {len(protection)} protected input/first-pilot file hashes match. Each database has ten unique question/audit event records; new events explicitly link to the original event IDs. Original results and the interim diagnostic pass are preserved. No independent AI audit or human approval has been added.\n\n"
        + "The final evidence-ID pass reused recent source snapshots from the separate improved live retrieval pass, rather than making another set of website requests. Runtime reports are in runs.jsonl.\n\n"
        + "## Remaining quality limitations\n\n"
        + "\n\n".join(row["question_id"] + ": " + row["finding"] for row in reviews)
        + "\n\nThe model pass is preserved in pilot.sqlite3 and results/. The exact-context-span validated view is in "
        "pilot-validated.sqlite3 and results-span-validated/. span_validation_provenance.json identifies every technical "
        "revision; assertions, claim IDs, source selections and factual verdicts were not changed. Only exact original "
        "anchors were expanded, and gates were recomputed. This removes string-accounting false negatives rather "
        "than weakening evidence requirements.\n\n"
        "Retrieval and structural citation validity improved, but semantic disagreements remain. Do not automatically "
        "accept a larger batch on this evidence alone. No larger batch was run.\n\n"
        "Results: results-span-validated/results.xlsx and matching JSONL files. Comparison: comparison.xlsx, comparison.json, question_comparison.jsonl and baseline_claim_mapping.jsonl.\n\n"
        + "Resume the same ten only:\n\n```powershell\n.\\.venv\\Scripts\\python.exe scripts/rerun_verification_pilot.py --seed-db outputs/verification/pilot-v2-20261103/pilot.sqlite3\n.\\.venv\\Scripts\\python.exe scripts/finalize_verification_spans.py\n```\n\nCompleted questions are skipped and exports are read back; no new audit records are created for already-completed IDs. No larger batch was launched.\n"
    )
    (args.current / "comparison_report.md").write_text(text, encoding="utf-8")
    book = Workbook()
    book.remove(book.active)
    for name, records in [
        ("Question comparison", rows),
        ("Original claim mapping", mapping),
        ("Measures", [{"measure": k, "value": v} for k, v in summary.items()]),
    ]:
        sheet = book.create_sheet(name)
        headers = list(dict.fromkeys(k for row in records for k in row))
        sheet.append(headers)
        for row in records:
            sheet.append(
                [
                    json.dumps(row.get(h, ""), ensure_ascii=False)
                    if isinstance(row.get(h), (dict, list, tuple))
                    else row.get(h, "")
                    for h in headers
                ]
            )
        for cells in sheet:
            for cell in cells:
                if isinstance(cell.value, str):
                    cell.data_type = "s"
        sheet.freeze_panes = "A2"
    book.save(args.current / "comparison.xlsx")
    book.close()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--baseline", type=Path, default=Path("outputs/verification/real-pilot-20261103")
    )
    p.add_argument(
        "--current", type=Path, default=Path("outputs/verification/pilot-final-20261104")
    )
    p.add_argument(
        "--protection",
        type=Path,
        default=Path("outputs/verification/pilot-v2-20261103/preservation_manifest.json"),
    )
    p.add_argument("--database-name", default="pilot-validated.sqlite3")
    p.add_argument("--package-name", default="results-span-validated")
    compare(p.parse_args())
