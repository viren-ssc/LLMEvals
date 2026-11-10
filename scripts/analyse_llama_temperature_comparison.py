"""Post-hoc paired Llama comparison; generation labels are user-reported."""

import json
import statistics
from collections import defaultdict

from openpyxl import Workbook

from canadianness_eval.final_metrics import file_hash
from canadianness_eval.hpc_ingestion import read_records
from canadianness_eval.research_exports import LABEL, add_sheet, table
from canadianness_eval.research_run import verify_plan
from canadianness_eval.settings import ROOT
from canadianness_eval.storage import now, write_json

OLD = "llama_full_20261106_v2"
NEW = "llama_mixed_temperature_workbook_c4_20261107_v2"
OUTPUT = ROOT / "outputs/comparisons/llama_temperature_0_vs_07_20261107"


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    plans = {
        rid: verify_plan(ROOT / "config/research" / rid / "experiment.json") for rid in [OLD, NEW]
    }
    rows = {
        rid: read_records(ROOT / plans[rid]["run_directory"] / "all_results.jsonl")
        for rid in [OLD, NEW]
    }
    indexed = {(r["question_id"], r["evaluation_metric"]): r for r in rows[OLD]}
    assert len(indexed) == 1814 and len(rows[NEW]) == 1814
    pairs = []
    for current in rows[NEW]:
        earlier = indexed[current["question_id"], current["evaluation_metric"]]
        assert earlier["status"] == current["status"] == "SUCCESS"
        for field in [
            "question",
            "reference_answer",
            "context_supporting_summary",
            "language",
            "primary_metric",
            "metric_role",
            "rubric_sha256",
            "evaluator_template_sha256",
            "judge_model",
        ]:
            assert earlier[field] == current[field], field
        pairs.append(
            dict(
                question_id=current["question_id"],
                evaluation_metric=current["evaluation_metric"],
                language=current["language"],
                metric_role=current["metric_role"],
                primary_metric=current["primary_metric"],
                temperature_0_score=earlier["score"],
                temperature_07_score=current["score"],
                score_difference_07_minus_0=current["score"] - earlier["score"],
                answer_changed=earlier["model_answer"] != current["model_answer"],
                temperature_0_answer=earlier["model_answer"],
                temperature_07_answer=current["model_answer"],
                temperature_0_reason=earlier["judge_reason"],
                temperature_07_reason=current["judge_reason"],
                question=current["question"],
                reference_answer=current["reference_answer"],
                context_supporting_summary=current["context_supporting_summary"],
                temperature_0_run_id=OLD,
                temperature_07_run_id=NEW,
                generation_temperature_label_provenance="User identification in conversation; absent from supplied Llama generation metadata",
                top_p_source_recorded=None,
                top_p_user_reported=0.95,
                top_p_report_scope="User reports 0.95; original temperature-zero value is not independently recoverable from supplied files",
                result_label=LABEL,
            )
        )
    summaries = []
    for axes in [(), ("language",), ("metric_role",), ("answer_changed",)]:
        groups = defaultdict(list)
        for r in pairs:
            groups[(r["evaluation_metric"], *(r[k] for k in axes))].append(r)
        for key, values in sorted(groups.items()):
            summaries.append(
                dict(
                    evaluation_metric=key[0],
                    grouping="/".join(axes) or "metric",
                    **dict(zip(axes, key[1:])),
                    pairs=len(values),
                    temperature_0_mean=statistics.mean(r["temperature_0_score"] for r in values),
                    temperature_07_mean=statistics.mean(r["temperature_07_score"] for r in values),
                    mean_paired_difference=statistics.mean(
                        r["score_difference_07_minus_0"] for r in values
                    ),
                    median_paired_difference=statistics.median(
                        r["score_difference_07_minus_0"] for r in values
                    ),
                    temperature_07_higher=sum(r["score_difference_07_minus_0"] > 0 for r in values),
                    ties=sum(r["score_difference_07_minus_0"] == 0 for r in values),
                    temperature_07_lower=sum(r["score_difference_07_minus_0"] < 0 for r in values),
                    result_label=LABEL,
                )
            )
    table(OUTPUT / "question_metric_comparisons", pairs)
    table(OUTPUT / "metric_language_role_comparisons", summaries)
    unchanged = [r for r in pairs if not r["answer_changed"]]
    annotation = dict(
        recorded_at=now(),
        source="User statement in conversation",
        verbatim_message="llama model is done.. Can you do the analysis and then compare the llama temp 0 results vs llama temp 0.7 results. Also waht was the top_p at temp 0 as I know now it was 0.95",
        earlier_run_id=OLD,
        newer_run_id=NEW,
        user_identified_temperatures={OLD: 0.0, NEW: 0.7},
        top_p_user_reported=0.95,
        top_p_independently_verified=False,
        earlier_top_p_in_original_source=None,
        newer_top_p_in_original_source=None,
        top_p_report_scope="0.95 reported retrospectively; source files do not establish its per-run application",
        existing_manifests_modified=False,
        scientific_validity_approved=False,
        result_label=LABEL,
    )
    write_json(OUTPUT / "generation_settings_annotation.json", annotation)
    write_json(
        OUTPUT / "comparison_manifest.json",
        dict(
            comparison_id=OUTPUT.name,
            run_ids=[OLD, NEW],
            pairs=1814,
            unique_questions=756,
            unchanged_answers=len({r["question_id"] for r in unchanged}),
            unchanged_answer_metric_pairs=len(unchanged),
            unchanged_answer_pairs_with_score_changes=sum(
                r["score_difference_07_minus_0"] != 0 for r in unchanged
            ),
            source_results_sha256={
                rid: file_hash(ROOT / plans[rid]["run_directory"] / "all_results.jsonl")
                for rid in [OLD, NEW]
            },
            rubric_sha256=plans[NEW]["rubric_sha256"],
            evaluator_template_sha256=plans[NEW]["evaluator_template_sha256"],
            no_new_judge_requests=True,
            result_label=LABEL,
        ),
    )
    book = Workbook()
    book.remove(book.active)
    add_sheet(book, "Metric and subgroup comparisons", summaries)
    add_sheet(book, "All question metric pairs", pairs)
    add_sheet(book, "Unchanged answer controls", unchanged)
    add_sheet(book, "Generation settings provenance", [annotation])
    book.save(OUTPUT / "llama_temperature_0_vs_07.xlsx")
    report = [
        "# Llama temperature-labelled run comparison",
        "",
        LABEL,
        "",
        "Both runs completed 1,814/1,814 metric judgments over the same 756 questions. The new run has zero final failed or missing tasks. "
        "No additional scoring requests were made for this comparison. Temperature 0 and 0.7 labels follow the user identification; "
        "the supplied Llama generation sources do not independently document those temperatures.",
        "",
        "| Metric | Tasks | Temp 0 mean | Temp 0.7 mean | Difference |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in summaries:
        if r["grouping"] == "metric":
            report.append(
                f"| {r['evaluation_metric']} | {r['pairs']} | {r['temperature_0_mean']:.4f} | {r['temperature_07_mean']:.4f} | {r['mean_paired_difference']:+.4f} |"
            )
    report += [
        "",
        "## Interpretation",
        "",
        "Differences are small and mixed: the new run is higher on M1 and M4 and lower on the other five metrics. "
        "The largest descriptive decline is M5 (about 0.0184 on the 0–1 scale). This is not evidence of a consistent improvement or decline, "
        "statistical equivalence, or a causal temperature effect. All individual pairs and reasons are retained; English/French and "
        "primary/secondary comparisons are exported separately.",
        "",
        f"The answer strings are identical for {len({r['question_id'] for r in unchanged})} questions, covering {len(unchanged)} metric pairs. "
        f"{sum(r['score_difference_07_minus_0'] != 0 for r in unchanged)} of those identical-answer metric pairs have different scores on repeat judging. "
        "This demonstrates observed repeat-judgment variation; the small control subset cannot establish an uncertainty bound for all changed answers.",
        "",
        "## top_p and inference provenance",
        "",
        "Neither supplied Llama source records top_p. The value 0.95 is retained as a retrospective user report, "
        "not independently verified per-run generation metadata. The earlier temperature-zero value cannot be recovered from these files, "
        "and the current workbook does not establish the temperature-0.7 top_p either. No library/provider default was assumed. "
        "The original generation command, configuration or generation manifest is needed to establish whether both runs used 0.95.",
        "",
        "These are answer-generation settings. The gpt-oss-120b judge still used omitted temperature/server-default sampling in both scoring runs. "
        "Its effective temperature/top_p were not recorded and should not be confused with the tested Llama generation parameters.",
        "",
        "## Comparability limits",
        "",
        "The rubric, fixed 42 steps, 35 bands, v2 template, judge deployment and question/reference/context/assignment alignment match. "
        "The earlier run used one worker and the new run four; execution load, timing and caching differed. Seeds, exact generation prompts, "
        "model checkpoint revisions and other generation controls were not supplied for both runs. Therefore isolate neither temperature nor top_p as the sole explanation. "
        "No arbitrary overall Canadian-ness score, scientific calibration or team approval is claimed.",
        "",
        f"Rubric SHA-256: `{plans[NEW]['rubric_sha256']}`",
        "",
        f"Evaluator-template SHA-256: `{plans[NEW]['evaluator_template_sha256']}`",
        "",
        "## Files",
        "",
        "`llama_temperature_0_vs_07.xlsx`, `question_metric_comparisons.csv`/`.jsonl`, "
        "`metric_language_role_comparisons.csv`/`.jsonl`, `generation_settings_annotation.json`, `comparison_manifest.json`. "
        "Existing frozen run artifacts were not modified.",
        "",
    ]
    text = "\n".join(report)
    (OUTPUT / "report.md").write_text(text, encoding="utf8")
    (ROOT / "docs/llama_temperature_0_vs_07_comparison.md").write_text(text, encoding="utf8")
    print(
        json.dumps(
            dict(
                metric_comparisons=[r for r in summaries if r["grouping"] == "metric"],
                unchanged_answer_pairs=len(unchanged),
                unchanged_pairs_with_score_change=sum(
                    r["score_difference_07_minus_0"] != 0 for r in unchanged
                ),
                output=str(OUTPUT),
            )
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
