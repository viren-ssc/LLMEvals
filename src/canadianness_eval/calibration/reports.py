"""Diagnostics are synthetic expectations, not a declaration of scientific validity."""

import json
from pathlib import Path

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from ..final_metrics import FINAL_JSON, load_final
from ..storage import digest, write_json
from .evaluate import read_results
from .schema import load_cases


def format_book(writer):
    for sheet in writer.book:
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="24465B")
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = 28
            for cell in column[1:]:
                if isinstance(cell.value, str) and cell.value.startswith(("=", "+", "-", "@")):
                    cell.data_type = "s"
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        for index in range(2, sheet.max_row + 1):
            sheet.row_dimensions[index].height = 65


def variability(rows):
    frame = pd.DataFrame(rows)
    valid = frame[frame.status == "SUCCESS"].copy()
    if valid.empty:
        return pd.DataFrame(
            columns=[
                "question_id",
                "model_variant",
                "metric_id",
                "n",
                "mean",
                "minimum",
                "maximum",
                "std",
                "spread",
            ]
        )
    summary = valid.groupby(
        ["question_id", "model_variant", "metric_id"], as_index=False
    ).score.agg(n="count", mean="mean", minimum="min", maximum="max", std="std")
    summary["spread"] = summary.maximum - summary.minimum
    return summary


def generate_reports(directory, input_path, config_path=FINAL_JSON, output_dir=None):
    directory = Path(directory)
    rows, cases = read_results(directory), load_cases(input_path)
    if not rows:
        raise ValueError("No saved calibration records")
    definitions = {m.metric_id: m for m in load_final(config_path).metrics}
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    from ..final_metrics import file_hash
    from .schema import dataset_hash

    if manifest["metric_json_sha256"] != file_hash(config_path) or manifest[
        "dataset_hash"
    ] != dataset_hash(cases):
        raise ValueError("Report dataset/configuration differs from run manifest")
    run_id = directory.name
    directory = Path(output_dir) if output_dir else directory
    directory.mkdir(parents=True, exist_ok=True)
    lookup = {c.question_id: c for c in cases}
    summary = variability(rows)
    frame = pd.DataFrame(rows)
    findings = []
    for row in rows:
        interval = row.get("intended_score_range")
        if (
            row["status"] == "SUCCESS"
            and interval
            and not interval[0] <= row["score"] <= interval[1]
        ):
            findings.append(
                dict(
                    question_id=row["question_id"],
                    metric_id=row["metric_id"],
                    repeat=row["repeat"],
                    kind="outside_synthetic_diagnostic_range",
                    score=row["score"],
                    expected_range=interval,
                    explanation=row["reason"],
                    expected_behavior=row["expected_behavior"],
                )
            )
    # Within-question repeated score variability, including honest one-run/failed counts.
    for row in summary.to_dict("records"):
        if row["spread"] >= 0.2 - 1e-9:
            findings.append(
                dict(
                    question_id=row["question_id"],
                    metric_id=row["metric_id"],
                    kind="repeat_spread_at_least_0.2",
                    spread=row["spread"],
                )
            )
    comparisons = []
    by_key = {(r["question_id"], r["metric_id"]): r for r in summary.to_dict("records")}
    # Matched controls: paired repetitions, not independent unpaired averages.
    pairs = [
        (
            "CAL-M4-FRENCH-PENDANT",
            "CAL-M4-FRENCH-DURANT",
            "M4",
            "unambiguous_french_paraphrase",
            "similar",
        ),
        ("CAL-M1-CONCISE", "CAL-M1-VERBOSE", "M1", "length_equivalence", "similar"),
        (
            "CAL-M1-CONCISE",
            "CAL-M1-UNNECESSARY-CLARIFICATION",
            "M1",
            "unnecessary_clarification_penalty",
            "higher",
        ),
        (
            "CAL-M1-CONCISE",
            "CAL-M1-FACTUAL-BOUNDARY",
            "M1",
            "context_vs_irrelevant_fact",
            "similar",
        ),
        ("CAL-M2-RELATIONSHIPS", "CAL-M2-WRONG-JURISDICTION", "M2", "jurisdiction", "higher"),
        ("CAL-M3-EXPLANATION", "CAL-M3-FACT-RECITATION", "M3", "application_vs_recall", "higher"),
        ("CAL-M4-FRENCH-VARIANT", "CAL-M4-FRENCH-ALTERNATIVE", "M4", "french_variants", "similar"),
        (
            "CAL-M5-DISTINCTIONS",
            "CAL-M5-GENERIC-DIVERSITY",
            "M5",
            "culture_vs_generic_wording",
            "higher",
        ),
        ("CAL-M6-SUPPORTED", "CAL-M6-EVASION", "M6", "calibration_vs_refusal", "higher"),
        ("CAL-M6-SUPPORTED", "CAL-M6-CORRECT-EXTRA", "M6", "valid_extra_facts", "similar"),
        ("CAL-M7-CONCISE", "CAL-M7-PARAPHRASE", "M7", "paraphrase_equivalence", "similar"),
        ("CAL-M7-CONCISE", "CAL-M7-VERBOSE-CORRECT", "M7", "length_equivalence", "similar"),
        ("CAL-M7-CONCISE", "CAL-M7-PARTIAL", "M7", "required_fact_coverage", "higher"),
        ("CAL-M7-CONCISE", "CAL-M7-LONG-HALLUCINATION", "M7", "material_added_errors", "higher"),
    ]
    for first, second, mid, label, direction in pairs:
        first_rows = {
            r["repeat"]: r["score"]
            for r in rows
            if r["question_id"] == first and r["metric_id"] == mid and r["status"] == "SUCCESS"
        }
        second_rows = {
            r["repeat"]: r["score"]
            for r in rows
            if r["question_id"] == second and r["metric_id"] == mid and r["status"] == "SUCCESS"
        }
        reps = sorted(set(first_rows) & set(second_rows))
        differences = [first_rows[n] - second_rows[n] for n in reps]
        passed = [abs(d) <= 0.1 + 1e-9 if direction == "similar" else d > 0 for d in differences]
        comparisons.append(
            dict(
                first=first,
                second=second,
                metric_id=mid,
                comparison=label,
                expected=direction,
                paired_repeats=len(reps),
                differences=differences,
                passes=sum(passed),
                fails=len(passed) - sum(passed),
                stable=len(set(passed)) <= 1 if passed else None,
            )
        )
    # Cross-metric comparisons are observations of the same response, not forced independence.
    overlap = []
    for case in cases:
        if len(case.applicable_metrics) > 1:
            means = {
                mid: by_key[(case.question_id, mid)]["mean"]
                for mid in case.applicable_metrics
                if (case.question_id, mid) in by_key
            }
            overlap.append(
                dict(
                    question_id=case.question_id,
                    metric_means=means,
                    interpretation="Overlapping relevant defects can affect both constructs; no numerical independence imposed.",
                )
            )
    status_counts = frame.groupby(["metric_id", "status"]).size().rename("count").reset_index()
    metrics_summary = (
        summary.groupby("metric_id", as_index=False).agg(
            scored_cases=("question_id", "count"),
            mean_within_case_std=("std", "mean"),
            maximum_spread=("spread", "max"),
        )
        if len(summary)
        else pd.DataFrame()
    )
    summary_path = directory / "calibration_summary.xlsx"
    human_path = directory / "human_calibration_review.xlsx"
    # Re-running analysis must not replace a workbook into which people could have entered data.
    for path in (summary_path, human_path):
        if path.exists():
            raise ValueError(
                "Report workbook already exists; use --report-dir to preserve existing files"
            )
    summary["case_family"] = summary.question_id.map(lambda q: lookup[q].case_family)
    summary["expected_behavior"] = summary.question_id.map(lambda q: lookup[q].expected_behavior)
    summary["intended_ranges_not_human_labels"] = [
        str(lookup[r.question_id].intended_score_ranges.get(r.metric_id, "directional only"))
        for r in summary.itertuples()
    ]
    with pd.ExcelWriter(summary_path, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Case variability", index=False)
        frame.drop(
            columns=[
                "applicable_rubric",
                "evidence_review",
                "judge_configuration",
                "package_versions",
            ]
        ).to_excel(writer, sheet_name="Individual results", index=False)
        status_counts.to_excel(writer, sheet_name="Status counts", index=False)
        pd.DataFrame(findings).to_excel(writer, sheet_name="Diagnostic flags", index=False)
        pd.DataFrame(comparisons).to_excel(writer, sheet_name="Matched comparisons", index=False)
        pd.DataFrame(overlap).to_excel(writer, sheet_name="Metric overlap", index=False)
        metrics_summary.to_excel(writer, sheet_name="Metric stability", index=False)
        format_book(writer)
    human_rows = []
    for case in cases:
        for mid in case.applicable_metrics:
            group = [
                r for r in rows if r["question_id"] == case.question_id and r["metric_id"] == mid
            ]
            valid = [r for r in group if r["status"] == "SUCCESS"]
            stats = by_key.get((case.question_id, mid), {})
            human_rows.append(
                dict(
                    review_id=digest([case.question_id, case.model_variant, mid])[:16],
                    question_id=case.question_id,
                    metric_id=mid,
                    response_id=digest([case.question_id, case.model_variant])[:16],
                    question=case.question,
                    model_answer=case.model_answer,
                    reference_answer=case.reference_answer,
                    evidence="\n".join(case.reference_context),
                    rubric=json.dumps(
                        [b.model_dump() for b in definitions[mid].rubric_0_to_10],
                        ensure_ascii=False,
                    ),
                    human_reviewer="",
                    human_score="",
                    human_comments="",
                    geval_score=stats.get("mean"),
                    geval_explanation="\n".join(
                        f"Repeat {r['repeat']}: {r['reason']}" for r in valid
                    ),
                    difference="",
                    evidence_status=group[0]["evidence_status"] if group else "NOT_READY",
                    repeated_std=stats.get("std"),
                    evaluation_run_id=run_id,
                )
            )
    with pd.ExcelWriter(human_path, engine="openpyxl") as writer:
        pd.DataFrame(human_rows).to_excel(writer, sheet_name="Human review", index=False)
        pd.DataFrame(
            [
                {
                    "instruction": "Score independently from 0 to 1. Fill reviewer identity and score; duplicate a row for a second reviewer. Blank means unreviewed."
                },
                {
                    "instruction": "Judge score, explanation, differences and identifying question labels are hidden initially to reduce anchoring. Unhide only after independent scoring."
                },
                {
                    "instruction": "Evidence NOT_READY rows are for readiness review, not factual scoring. No human scores have been generated."
                },
            ]
        ).to_excel(writer, sheet_name="Instructions", index=False)
        format_book(writer)
        sheet = writer.book["Human review"]
        for index in range(2, sheet.max_row + 1):
            sheet.cell(
                index, 15, f'=IF(AND(ISNUMBER(K{index}),ISNUMBER(M{index})),K{index}-M{index},"")'
            )
        for column in ("B", "M", "N", "O"):
            sheet.column_dimensions[column].hidden = True
        validation = DataValidation(
            type="decimal", operator="between", formula1="0", formula2="1", allow_blank=True
        )
        validation.errorTitle = "Use a normalized score"
        validation.error = "Enter a score between 0 and 1"
        validation.showErrorMessage = True
        sheet.add_data_validation(validation)
        validation.add("K2:K1048576")
    counts = frame.status.value_counts().to_dict()
    analysis = dict(
        status_counts=counts,
        diagnostic_flags=findings,
        matched_comparisons=comparisons,
        cross_metric_overlap=overlap,
        human_calibration_status="PENDING_REAL_HUMAN_LABELS",
        explanations_status="Saved verbatim; semantic rubric consistency requires human review, not an automatic lexical verdict.",
    )
    write_json(directory / "analysis.json", analysis)
    lines = [
        "# Final-metric calibration report",
        "",
        f"Run: `{run_id}`; JSON SHA-256 `{manifest['metric_json_sha256']}`.",
        "",
        "Research state: calibration of proposed final definitions, not frozen or scientifically validated.",
        "",
        f"Saved latest records: {len(rows)}. Status counts: {json.dumps(counts)}.",
        "",
        "## Repeated-score variability",
        "",
        "| Metric | Scored cases | Mean within-case SD | Maximum spread |",
        "|---|---:|---:|---:|",
    ]
    for r in metrics_summary.to_dict("records"):
        lines.append(
            f"| {r['metric_id']} | {r['scored_cases']} | {r['mean_within_case_std']:.3f} | {r['maximum_spread']:.3f} |"
        )
    lines += [
        "",
        "## Matched controls",
        "",
        "| Comparison | Metric | Paired repeats | Passes | Fails | Differences (first minus second) |",
        "|---|---|---:|---:|---:|---|",
    ]
    for r in comparisons:
        lines.append(
            f"| {r['comparison']} | {r['metric_id']} | {r['paired_repeats']} | {r['passes']} | {r['fails']} | {r['differences']} |"
        )
    lines += [
        "",
        "## Exact diagnostic findings",
        "",
        "Ranges are synthetic author expectations, not independent human labels. A flag is a review prompt, not proof of unfairness.",
        "",
    ]
    for finding in findings:
        lines.append(
            f"- **{finding['question_id']} / {finding['metric_id']}**: "
            + json.dumps(finding, ensure_ascii=False)
        )
    if not findings:
        lines.append("No programmed range/spread flags observed; this does not establish validity.")
    lines += [
        "",
        "## Interpretation and next steps",
        "",
        "The exact selected steps and rubric wording were never regenerated or revised. M6's rubric wording about unsupported claims may conflict with its finer distinction between unsupported and contradicted claims; examine the limited-evidence controls and explanations before proposing a documented revision.",
        "",
        "M3 rubric anchors emphasize practical guidance even though the selected steps also accept explanatory tasks. Inspect CAL-M3-EXPLANATION for checklist-related penalties; any adjustment requires explicit team review.",
        "",
        "M1 and M4 boundary controls isolate framing/language from an unrelated factual mistake. M2/M3 paired same-response scores record legitimate construct overlap without forcing independence. See the Metric overlap sheet.",
        "",
        "Correct concise/paraphrased answers and equivalent longer controls test superficial wording and verbosity. Mean/SD/range and all repeats are retained. Missing evidence skips and N/A records are excluded from score averages, never converted to zero.",
        "",
        "Gateway-default sampling is held constant, but temperature/seed and immutable model revision are not established, so determinism is not claimed. Repeats are repeated measurements, not independent questions.",
        "",
        "Human fields are blank. Semantic explanation consistency, cultural/language nuance and potential scoring unfairness require independent human review. The workbook hides judge scores initially to reduce anchoring; retain each reviewer's individual scores.",
        "",
        "Software supports the eventual comparison, but production use requires verified benchmark evidence, independent human calibration, final team approval and a frozen metric version. No full benchmark, training or fine-tuning was run.",
    ]
    (directory / "metric_calibration_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return analysis


def compare_humans(workbook, output_dir, tolerance=0.1):
    if not 0 <= tolerance <= 1:
        raise ValueError("Tolerance must be between zero and one")
    frame = pd.read_excel(workbook, sheet_name="Human review", keep_default_na=False)
    labels = frame[frame.human_score != ""].copy()
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise ValueError("Human comparison output directory exists; choose a new path")
    output_dir.mkdir(parents=True)
    if labels.empty:
        result = {"status": "PENDING_REAL_HUMAN_LABELS", "human_labels": 0}
        write_json(output_dir / "human_agreement.json", result)
        return result
    labels["human_score"] = pd.to_numeric(labels.human_score, errors="raise")
    if not labels.human_score.between(0, 1).all() or any(
        not str(x).strip() for x in labels.human_reviewer
    ):
        raise ValueError("Valid human scores and reviewer identifiers are required")
    if labels.duplicated(["review_id", "human_reviewer"]).any():
        raise ValueError(
            "Duplicate score for one item/reviewer; retain independent reviewers explicitly"
        )
    labels["geval_score"] = pd.to_numeric(labels.geval_score, errors="coerce")
    usable = labels[labels.geval_score.notna()].copy()
    usable["absolute_difference"] = (usable.human_score - usable.geval_score).abs()
    output = []
    for (mid, reviewer), group in usable.groupby(["metric_id", "human_reviewer"]):
        correlation = None
        if len(group) >= 3 and group.human_score.nunique() > 1 and group.geval_score.nunique() > 1:
            correlation = float(group.human_score.rank().corr(group.geval_score.rank()))
        output.append(
            dict(
                metric_id=mid,
                reviewer=reviewer,
                count=len(group),
                mean_absolute_error=float(group.absolute_difference.mean()),
                rank_correlation=correlation,
                agreement_within_tolerance=float((group.absolute_difference <= tolerance).mean()),
            )
        )
    labels.to_csv(output_dir / "individual_human_labels.csv", index=False)
    usable[usable.absolute_difference > tolerance].to_csv(
        output_dir / "large_disagreements.csv", index=False
    )
    labels.groupby(["review_id", "metric_id"]).human_score.agg(
        ["count", "mean", "std", "min", "max"]
    ).to_csv(output_dir / "human_reviewer_disagreement.csv")
    result = dict(
        status="HUMAN_LABELS_ANALYZED_NOT_AUTOMATIC_APPROVAL",
        tolerance=tolerance,
        human_labels=len(labels),
        paired_labels=len(usable),
        by_metric_and_reviewer=output,
    )
    write_json(output_dir / "human_agreement.json", result)
    return result
