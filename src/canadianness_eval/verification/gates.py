"""Deterministic provenance gates; semantic support still requires the evidence judge."""

import re


def normalized(text):
    return " ".join(re.sub(r"\[L\d{5}\]", "", text).split())


def extraction_errors(answer, extraction, coverage):
    errors, covered = [], set()
    seen = set()
    for claim in extraction.claims:
        identity = getattr(claim, "assertion", claim.text)
        if identity in seen:
            errors.append("Duplicate extracted claim")
        seen.add(identity)
        if answer[claim.answer_start : claim.answer_end] != claim.text:
            errors.append("Claim text/offset does not match original answer")
        else:
            covered.update(range(claim.answer_start, claim.answer_end))
        if claim.temporal_scope == "historical" and not claim.relevant_date.strip():
            errors.append("Historical claim has no relevant date")
    for span in extraction.nonfactual_spans:
        # Whitespace is not factual text and is already excluded from the coverage gate.
        if not span.strip():
            continue
        starts = [m.start() for m in re.finditer(re.escape(span), answer)]
        if not starts:
            errors.append("Nonfactual span absent from original answer")
        else:
            for start in starts:
                covered.update(range(start, start + len(span)))
    if any(c.isalnum() and i not in covered for i, c in enumerate(answer)):
        errors.append("Answer has uncovered factual-text candidates")
    if not coverage.complete or coverage.omitted_claims:
        errors.append("Coverage review found missing or incomplete claims")
    return errors


def citation_errors(claim, judgment, sources):
    errors = []
    if judgment.verdict in {"supported", "contradicted"} and not judgment.citations:
        errors.append("Factual verdict missing inspected citations")
    for citation in judgment.citations:
        matches = [
            s
            for s in sources
            if citation.source_url in {s.url, s.final_url} and citation.source_sha256 == s.sha256
        ]
        if len(matches) != 1:
            errors.append("Citation URL/hash does not identify exactly one retrieved source")
            continue
        source = matches[0]
        if source.status != "ok" or not source.authoritative:
            errors.append("Citation source was not retrieved from an approved authority")
        if normalized(citation.exact_excerpt) not in normalized(source.text):
            errors.append("Citation excerpt absent from retrieved source")
        locator = citation.locator
        lines = re.findall(r"L\d{5}", locator)
        pages = re.findall(r"Page (\d+)", locator)
        if not (
            (lines and all(f"[{line}]" in source.text for line in lines))
            or (pages and all(f"[Page {page}]" in source.text for page in pages))
        ):
            errors.append("Citation locator must identify retrieved L00001 lines or Page 1")
        # Require the excerpt to occur inside the indicated location, not elsewhere on the page.
        if lines:
            first = int(lines[0][1:])
            last = int(lines[-1][1:])
            localized = "\n".join(
                line
                for line in source.text.splitlines()
                if (m := re.match(r"\[L(\d{5})\]", line)) and first <= int(m[1]) <= last
            )
            if normalized(citation.exact_excerpt) not in normalized(localized):
                errors.append("Excerpt does not occur within the cited line range")
        if pages:
            localized = "\n".join(
                part
                for part in re.split(r"(?=\[Page \d+\])", source.text)
                if any(part.startswith(f"[Page {p}]") for p in pages)
            )
            if normalized(citation.exact_excerpt) not in normalized(localized):
                errors.append("Excerpt does not occur on the cited page")
        if not citation.temporal_match or not citation.jurisdiction_match:
            errors.append("Citation does not match claim date or jurisdiction")
        if source.historical and claim.temporal_scope == "current":
            errors.append("Archived evidence cannot establish a present-day claim")
    return errors


def quality_errors(result):
    errors = []
    ids = [c.claim_id for c in result.claims]
    if len(ids) != len(set(ids)):
        errors.append("Duplicate claim IDs")
    if len(result.claims) != len(result.extraction.claims):
        errors.append("Claim result count mismatch")
    for c in result.claims:
        errors.extend(citation_errors(c.claim, c.judgment, result.sources))
    if result.fully_supported and (
        result.gate_errors
        or not result.claims
        or any(c.judgment.verdict != "supported" for c in result.claims)
    ):
        errors.append("Fully supported status inconsistent with claim verdicts/gates")
    if result.proposal.disposition == "accept" and (
        not result.fully_supported
        or not result.metric.suitable
        or result.proposal.missing_information
    ):
        errors.append("Accept disposition inconsistent with evidence/metric/missing information")
    if getattr(result, "pipeline_version", 1) == 2:
        if (
            result.proposal.corrected_answer
            and not result.corrected_answer_verified
            and result.proposal.disposition != "needs_more_evidence"
        ):
            errors.append("Unverified correction must have needs_more_evidence disposition")
        if (result.reference_status == "fully_supported") != result.fully_supported:
            errors.append("Reference status inconsistent with support gates")
        if result.reference_status == "contradicted" and not any(
            c.judgment.verdict == "contradicted" for c in result.claims
        ):
            errors.append("Missing evidence must not become a contradicted reference status")
    return errors
