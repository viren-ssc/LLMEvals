import re
from collections import Counter
from difflib import SequenceMatcher

import pandas as pd

COLUMNS = [
    "metric_id",
    "metric_name",
    "generation_run",
    "candidate_id",
    "original_step",
    "similarity_group",
    "appearances_across_runs",
    "suggested_quality",
    "suggestion_reason",
    "manual_selection",
    "edited_final_wording",
    "final_order",
    "reviewer_notes",
]


def normalized(text):
    return " ".join(re.findall(r"\w+", text.lower()))


def consolidate(records, metrics):
    rows, representatives = [], {}
    for record in records:
        if record["status"] != "success":
            continue
        mid = record["metric_id"]
        groups = representatives.setdefault(mid, [])
        for index, step in enumerate(record["evaluation_steps"], 1):
            key = normalized(step)
            group = next(
                (
                    n
                    for n, value in enumerate(groups, 1)
                    if SequenceMatcher(None, key, value).ratio() >= 0.78
                ),
                None,
            )
            if group is None:
                groups.append(key)
                group = len(groups)
            vague = len(key.split()) < 7 or "canadian enough" in key
            rows.append(
                dict(
                    zip(
                        COLUMNS,
                        [
                            mid,
                            record["metric_name"],
                            record["run_number"],
                            f"{mid}-R{record['run_number']}-{index:02}",
                            step,
                            f"{mid}-G{group}",
                            0,
                            "Review vague wording"
                            if vague
                            else "Review relevance and observability",
                            "Short/vague heuristic"
                            if vague
                            else "Lexical grouping only; human checks overlap and metric boundaries",
                            "",
                            "",
                            "",
                            "",
                        ],
                    )
                )
            )
    for row in rows:
        row["appearances_across_runs"] = len(
            {r["generation_run"] for r in rows if r["similarity_group"] == row["similarity_group"]}
        )
    coverage = []
    for metric in metrics:
        subset = [r for r in rows if r["metric_id"] == metric["metric_id"]]
        joined = " ".join(r["original_step"].lower() for r in subset)
        hits = [c for c in metric["coverage_concepts"] if c.lower() in joined]
        counts = Counter(r["similarity_group"] for r in subset)
        coverage.append(
            dict(
                metric_id=metric["metric_id"],
                definition=metric["definition"],
                exclusions=metric["exclusions"],
                evaluation_params=", ".join(metric["evaluation_params"]),
                required_evidence=", ".join(metric["required_evidence"]),
                candidates=len(subset),
                distinct_lexical_groups=len(counts),
                lexical_hits="; ".join(hits),
                potentially_missing="; ".join(
                    c for c in metric["coverage_concepts"] if c not in hits
                ),
                redundant_groups="; ".join(k for k, v in counts.items() if v > 1),
                interpretation="Keyword proxy only; manually review conceptual coverage and cross-metric leakage.",
            )
        )
    return pd.DataFrame(rows, columns=COLUMNS), pd.DataFrame(coverage)
