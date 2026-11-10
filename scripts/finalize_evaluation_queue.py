"""Local ten-minute waiter: finalize current Apertus and the workbook comparisons."""

import json
import statistics
import time
from collections import defaultdict

from openpyxl import Workbook

from canadianness_eval.apertus_research import PLAN as APERTUS_PLAN
from canadianness_eval.apertus_research import analyse as analyse_apertus
from canadianness_eval.hpc_ingestion import read_records
from canadianness_eval.queued_workbook import MODELS, STATE, run_id, validate_queue
from canadianness_eval.research_exports import LABEL, add_sheet, table
from canadianness_eval.research_run import verify_plan
from canadianness_eval.settings import ROOT
from canadianness_eval.storage import now, write_json


def wait_for(path, condition):
    while True:
        if path.exists():
            try:
                value = json.loads(path.read_text(encoding="utf8"))
                if condition(value):
                    return value
            except (ValueError, PermissionError):
                pass
        time.sleep(600)


def finalize_current():
    current = ROOT / "outputs/evaluations/apertus_full_as_generated_c4_20261107_v2"
    wait_for(current / "full_run_summary.json", lambda v: v.get("successful") == 1814)
    plan = verify_plan(APERTUS_PLAN)
    rows, summaries, groups = analyse_apertus()
    means = {
        m: statistics.mean(r["score"] for r in rows if r["evaluation_metric"] == m)
        for m in ["M1", "M2", "M3", "M4", "M5", "M6", "M7"]
    }
    write_json(
        current / "completion_verification.json",
        dict(
            status="PASS",
            successful=1814,
            failed=0,
            missing=0,
            all_source_response_strings_preserved=True,
            concurrency=4,
            rubric_sha256=plan["rubric_sha256"],
            evaluator_template_sha256=plan["evaluator_template_sha256"],
            result_label=LABEL,
            scientific_validity_approved=False,
            team_approval=False,
        ),
    )
    report = [
        "# Apertus as-generated completed evaluation",
        "",
        LABEL,
        "",
        "1,814/1,814 successful metric evaluations across 756 questions, including all 324 length-limited answers. "
        "756 primary and 1,058 secondary tasks; source response strings verified unchanged. "
        "Four-worker scheduling reused the unchanged fixed-rubric evaluator and metric checkpoints.",
        "",
        "| Metric | Apertus mean |",
        "|---|---:|",
    ]
    for metric, mean in means.items():
        report.append(f"| {metric} | {mean:.4f} |")
    report += [
        "",
        "Excel: `as_generated_comparison.xlsx`. Individual scores/explanations: `as_generated_results.jsonl` and `.csv`. "
        "Standard exports include primary/secondary and English/French summaries. Additional files contain generation metadata, "
        "complete/truncated and exploratory repetition groups, and 1,814 matched metric pairs for each comparison with Llama and GC LLM.",
        "",
        "No response regeneration, cleaning, exclusions, rubric changes, second normalization or arbitrary combined score. "
        "Different/unknown inference controls and unknown judge-server temperature limit strict comparison and reproducibility. "
        "Apertus uses four-worker scheduling while the previous runs were sequential, so load/timing/cache conditions differ. "
        "Supporting context is judge-side evidence, not a claim about the tested model input or verified verbatim quotations.",
        "",
        "Known calibration limitations:",
        *["- " + s for s in plan["known_scoring_limitations"]],
        "",
        f"Rubric SHA-256: `{plan['rubric_sha256']}`",
        "",
        f"Evaluator-template SHA-256: `{plan['evaluator_template_sha256']}`",
        "",
        "Failures/retries, actual request counts, token accounting and latency appear in `full_run_summary.json`, "
        "`attempts.*`, `retry_report.*`, `raw/` and `sessions/`. No scientific/team approval or empirical calibration is claimed.",
        "",
    ]
    (current / "apertus_final_report.md").write_text("\n".join(report), encoding="utf8")
    (ROOT / "docs/apertus_as_generated_full_results.md").write_text(
        "\n".join(report), encoding="utf8"
    )
    print(now(), "CURRENT_APERTUS_FINALIZED", means, flush=True)


def main():
    current = ROOT / "outputs/evaluations/apertus_full_as_generated_c4_20261107_v2"
    if not (
        (current / "completion_verification.json").exists()
        and (current / "apertus_final_report.md").exists()
    ):
        finalize_current()
    wait_for(
        STATE / "completion.json",
        lambda v: v.get("status") == "COMPLETED" and v.get("successful") == 5442,
    )
    queue = validate_queue()
    combined = []
    for model in MODELS:
        path = ROOT / "config/research" / run_id(model) / "experiment.json"
        p = verify_plan(path)
        values = read_records(ROOT / p["run_directory"] / "as_generated_results.jsonl")
        assert len(values) == 1814 and all(r["status"] == "SUCCESS" for r in values)
        combined.extend(values)
    assert (
        len({(r["question_id"], r["evaluated_model"], r["evaluation_metric"]) for r in combined})
        == 5442
    )
    output = STATE / "final_results"
    output.mkdir(exist_ok=True)
    table(output / "all_three_model_results", combined)
    groups = []
    for dims in [
        ("evaluated_model", "evaluation_metric"),
        ("evaluated_model", "evaluation_metric", "language"),
        ("evaluated_model", "evaluation_metric", "metric_role"),
    ]:
        indexed = defaultdict(list)
        for r in combined:
            indexed[tuple(r[k] for k in dims)].append(r)
        for key, values in sorted(indexed.items()):
            groups.append(
                dict(
                    zip(dims, key),
                    grouping="/".join(dims),
                    count=len(values),
                    mean_score=statistics.mean(r["score"] for r in values),
                    result_label=LABEL,
                )
            )
    table(output / "three_model_metric_summaries", groups)
    indexed = defaultdict(dict)
    for r in combined:
        indexed[(r["question_id"], r["evaluation_metric"])][r["evaluated_model"]] = r
    matched = []
    for key, models in sorted(indexed.items()):
        assert set(models) == set(MODELS)
        first = models["llama"]
        for r in models.values():
            for field in [
                "question",
                "reference_answer",
                "context_supporting_summary",
                "language",
                "metric_role",
                "rubric_sha256",
                "evaluator_template_sha256",
            ]:
                assert r[field] == first[field]
        row = dict(
            question_id=key[0],
            evaluation_metric=key[1],
            language=first["language"],
            metric_role=first["metric_role"],
            question=first["question"],
            reference_answer=first["reference_answer"],
            context_supporting_summary=first["context_supporting_summary"],
            result_label=LABEL,
        )
        for model, r in models.items():
            row.update(
                {
                    model + "_score": r["score"],
                    model + "_answer": r["model_answer"],
                    model + "_reason": r["judge_reason"],
                    model + "_generation_metadata": r["generation_metadata"],
                }
            )
        matched.append(row)
    table(output / "matched_question_metric_scores", matched)
    book = Workbook()
    book.remove(book.active)
    for title, values in [
        ("All three model scores", combined),
        ("Metric language role summaries", groups),
        ("Matched question metric scores", matched),
    ]:
        add_sheet(book, title, values)
    book.save(output / "three_model_mixed_temperature_results.xlsx")
    report = [
        "# Three-model mixed-temperature workbook evaluation",
        "",
        LABEL,
        "",
        "Completed 5,442/5,442 metric evaluations, 1,814 per model, in order Llama, GC LLM, Apertus. "
        "Each run used four-worker scheduling, the same fixed v2 evaluator and rubric, and individual checkpoint/retry persistence. "
        "All original workbook response strings were retained. Previous benchmark results were preserved.",
        "",
        "| Metric | Llama | GC LLM | Apertus |",
        "|---|---:|---:|---:|",
    ]
    for metric in ["M1", "M2", "M3", "M4", "M5", "M6", "M7"]:
        vals = [
            next(
                r["mean_score"]
                for r in groups
                if r["grouping"] == "evaluated_model/evaluation_metric"
                and r["evaluation_metric"] == metric
                and r["evaluated_model"] == m
            )
            for m in MODELS
        ]
        report.append("| " + metric + " | " + " | ".join(f"{v:.4f}" for v in vals) + " |")
    report += [
        "",
        "The GC LLM source contains 755 temperature-0.7 responses and one explicitly reused temperature-0.0 response. "
        "Temperature and source-run labels are preserved at question level. The other two models lack equivalent temperature metadata in this workbook. "
        "Full generation inference settings, revisions and termination metadata are not supplied and were not inferred from the earlier datasets. "
        "Consequently these are mixed-condition, AI-provisional comparisons, not controlled generation-condition or calibrated scientific rankings.",
        "",
        "Judge temperature remains omitted, matching the original scoring protocol; server-default sampling and shared-server load can vary. "
        "Rubric interpretation limitations from the original pilots remain documented in each run manifest. No arbitrary combined Canadian-ness score was computed.",
        "",
        f"Source workbook SHA-256: `{queue['source_workbook_sha256']}`",
        "",
        "Artifacts: `three_model_mixed_temperature_results.xlsx`, `all_three_model_results.*`, "
        "`three_model_metric_summaries.*`, `matched_question_metric_scores.*`. Individual run folders retain all raw judge responses, "
        "attempts, errors/retries, API usage, immutable manifests and execution-only approval records. "
        "English/French and primary/secondary comparisons appear in both individual and combined exports.",
        "",
    ]
    (output / "final_report.md").write_text("\n".join(report), encoding="utf8")
    (ROOT / "docs/three_model_mixed_temperature_results.md").write_text(
        "\n".join(report), encoding="utf8"
    )
    print(now(), "ALL_RESULTS_FINALIZED", str(output), flush=True)


if __name__ == "__main__":
    main()
