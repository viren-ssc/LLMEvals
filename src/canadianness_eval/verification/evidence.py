"""Construct excerpts and locations from actual source text; judges only select IDs."""

import math
import re
import unicodedata
from collections import Counter

from .gates import citation_errors
from .models import Citation, Judgment, digest
from .v2_models import EvidenceUnit

STOP = set(
    "the and for that this with from are has have its des les dans pour une est qui que aux "
    "sur par du de le la et un en au il to of is a an as be it or".split()
)


def tokens(text):
    folded = "".join(
        c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c)
    )
    return {w.rstrip("s") for w in re.findall(r"[a-z0-9]+", folded) if len(w) > 2 and w not in STOP}


def catalog(sources):
    units = {}
    for source in sources:
        if source.status != "ok" or not source.authoritative:
            continue
        lines = []
        if source.text.startswith("[Page "):
            for part in re.split(r"(?=\[Page \d+\])", source.text):
                match = re.match(r"\[Page (\d+)\]\s*(.*)", part, flags=re.S)
                if match:
                    lines.append((f"Page {match[1]}", match[2]))
        else:
            for line in source.text.splitlines():
                match = re.match(r"\[(L\d{5})\]\s*(.*)", line)
                if match:
                    lines.append((match[1], match[2]))
        for locator, text in lines:
            # Contiguous substrings only; splitting changes neither quotes nor page/line identity.
            for start in range(0, len(text), 1000):
                excerpt = text[start : start + 1500].strip()
                if len(excerpt) < 25:
                    continue
                eid = "E-" + digest([source.url, source.sha256, locator, excerpt])[:20]
                units[eid] = EvidenceUnit(
                    evidence_id=eid,
                    source_url=source.url,
                    source_sha256=source.sha256,
                    locator=locator,
                    exact_excerpt=excerpt,
                    source_title=source.title,
                    historical=source.historical,
                    archive_date=source.archive_date,
                )
    return list(units.values())


def rank_units(units, query, limit=32):
    wanted = tokens(query)
    bilingual = {
        "ministere": "ministry",
        "education": "education",
        "organisation": "organization",
        "prestation": "delivery",
        "evaluation": "assessment",
        "enseignement": "education",
        "primaire": "elementary",
        "secondaire": "secondary",
        "postsecondaire": "postsecondary",
        "responsable": "responsible",
    }
    wanted |= {english for french, english in bilingual.items() if french in wanted}
    frequencies = Counter(t for unit in units for t in tokens(unit.exact_excerpt))

    def score(unit):
        found = wanted & tokens(unit.exact_excerpt)
        return sum(math.log(2 + len(units) / (1 + frequencies[t])) for t in found)

    ranked = sorted(units, key=lambda u: (-score(u), u.evidence_id))
    # Give each relevant source room while retaining deeply located paragraphs from long documents.
    selected, per_source = [], Counter()
    for unit in ranked:
        if per_source[unit.source_url] < 12:
            selected.append(unit)
            per_source[unit.source_url] += 1
        if len(selected) == limit:
            break
    return selected


def materialize(claim, decision, selected, sources):
    lookup = {unit.evidence_id: unit for unit in selected}
    citations, errors, seen = [], [], set()
    for use in decision.evidence:
        if use.evidence_id not in lookup:
            errors.append("Judge selected an evidence ID not supplied for this claim")
            continue
        if use.evidence_id in seen:
            continue
        seen.add(use.evidence_id)
        unit = lookup[use.evidence_id]
        citations.append(
            Citation(
                source_url=unit.source_url,
                source_sha256=unit.source_sha256,
                locator=unit.locator,
                exact_excerpt=unit.exact_excerpt,
                attributed_summary=use.explanation,
                temporal_match=use.temporal_match,
                jurisdiction_match=use.jurisdiction_match,
                explanation=use.explanation,
            )
        )
    judgment = Judgment(
        verdict=decision.verdict, citations=citations, explanation=decision.explanation
    )
    errors.extend(citation_errors(claim, judgment, sources))
    if errors:
        judgment = Judgment(
            verdict="insufficient",
            citations=[],
            explanation="Evidence selection validation failed: " + "; ".join(errors),
        )
    return judgment, errors
