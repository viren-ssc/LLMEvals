from pathlib import Path

import numpy as np
import pandas as pd


def export_results(rows, output_dir):
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(directory / "results.csv", index=False, encoding="utf-8-sig")
    frame.groupby(["metric_id", "model_variant", "status"]).size().rename("count").to_csv(
        directory / "status_counts.csv"
    )
    valid = frame[frame.status == "success"]
    if valid.empty:
        return
    valid.groupby(["metric_id", "model_variant"]).score.agg(
        valid_count="count", mean="mean", standard_deviation="std", median="median"
    ).to_csv(directory / "summary.csv")
    pair_rows = []
    for mid, group in frame[frame.status != "not_applicable"].groupby("metric_id"):
        group = group.copy()
        group.loc[group.status != "success", "score"] = np.nan
        pivot = group.pivot(index="question_id", columns="model_variant", values="score")
        if not {"base", "fine_tuned"}.issubset(pivot.columns):
            continue
        paired = pivot[["base", "fine_tuned"]].dropna()
        diff = (paired.fine_tuned - paired.base).to_numpy(dtype=float)
        low = high = None
        if len(diff) >= 10:
            rng = np.random.default_rng(2026)
            means = rng.choice(diff, size=(5000, len(diff)), replace=True).mean(axis=1)
            low, high = np.quantile(means, [0.025, 0.975])
        pair_rows.append(
            dict(
                metric_id=mid,
                valid_pairs=len(diff),
                base_mean=paired.base.mean(),
                fine_tuned_mean=paired.fine_tuned.mean(),
                paired_difference=diff.mean() if len(diff) else None,
                ci_low=low,
                ci_high=high,
                unmatched_or_failed=len(pivot) - len(paired),
                ci_method="Paired question bootstrap, 5000 resamples, seed 2026; only n>=10",
            )
        )
    pd.DataFrame(pair_rows).to_csv(directory / "paired_comparison.csv", index=False)
