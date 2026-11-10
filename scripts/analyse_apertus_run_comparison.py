"""Independent post-hoc Apertus comparison; no judge requests or run mutations."""

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

OLD = "apertus_full_as_generated_c4_20261107_v2"
NEW = "apertus_mixed_temperature_workbook_c4_20261107_v2"
OUTPUT = ROOT / "outputs/comparisons/apertus_previous_vs_new_workbook_20261107"


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    plans = {
        rid: verify_plan(ROOT / "config/research" / rid / "experiment.json") for rid in [OLD, NEW]
    }
    paths = {rid: ROOT / plans[rid]["run_directory"] / "all_results.jsonl" for rid in [OLD, NEW]}
    results = {rid: read_records(path) for rid, path in paths.items()}
    metadata = {
        rid: {
            r["question_id"]: r
            for r in read_records(
                ROOT / plans[rid]["as_generated_contract"]["source_metadata_sidecar"]
            )
        }
        for rid in [OLD, NEW]
    }
    earlier = {(r["question_id"], r["evaluation_metric"]): r for r in results[OLD]}
    assert len(earlier) == len(results[NEW]) == 1814
    pairs = []
    for r in results[NEW]:
        previous = earlier[r["question_id"], r["evaluation_metric"]]
        assert r["status"] == previous["status"] == "SUCCESS"
        for field in [
            "question",
            "reference_answer",
            "context_supporting_summary",
            "language",
            "metric_role",
            "primary_metric",
            "rubric_sha256",
            "evaluator_template_sha256",
            "judge_model",
        ]:
            assert r[field] == previous[field], field
        old_meta = metadata[OLD][r["question_id"]]
        new_meta = metadata[NEW][r["question_id"]]
        pairs.append(
            dict(
                question_id=r["question_id"],
                evaluation_metric=r["evaluation_metric"],
                language=r["language"],
                primary_metric=r["primary_metric"],
                metric_role=r["metric_role"],
                previous_score=previous["score"],
                new_score=r["score"],
                new_minus_previous=r["score"] - previous["score"],
                answer_changed=r["model_answer"] != previous["model_answer"],
                previous_repetition_flag=old_meta["analysis_repetition_flag"],
                new_repetition_flag=new_meta["analysis_repetition_flag"],
                previous_truncated=old_meta["truncated"],
                new_truncated=None,
                previous_answer=previous["model_answer"],
                new_answer=r["model_answer"],
                previous_reason=previous["judge_reason"],
                new_reason=r["judge_reason"],
                question=r["question"],
                reference_answer=r["reference_answer"],
                context_supporting_summary=r["context_supporting_summary"],
                previous_generation_metadata=old_meta,
                new_generation_metadata=new_meta,
                previous_run_id=OLD,
                new_run_id=NEW,
                result_label=LABEL,
            )
        )
    assert len({(r["question_id"], r["evaluation_metric"]) for r in pairs}) == 1814
    summaries = []
    for axes in [
        (),
        ("language",),
        ("metric_role",),
        ("answer_changed",),
        ("previous_repetition_flag",),
        ("new_repetition_flag",),
        ("previous_truncated",),
    ]:
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
                    previous_mean=statistics.mean(r["previous_score"] for r in values),
                    new_mean=statistics.mean(r["new_score"] for r in values),
                    mean_paired_difference=statistics.mean(r["new_minus_previous"] for r in values),
                    median_paired_difference=statistics.median(
                        r["new_minus_previous"] for r in values
                    ),
                    new_higher=sum(r["new_minus_previous"] > 0 for r in values),
                    ties=sum(r["new_minus_previous"] == 0 for r in values),
                    new_lower=sum(r["new_minus_previous"] < 0 for r in values),
                    result_label=LABEL,
                )
            )
    table(OUTPUT / "question_metric_comparisons", pairs)
    table(OUTPUT / "metric_language_role_comparisons", summaries)
    unchanged = [r for r in pairs if not r["answer_changed"]]
    unique = {r["question_id"]: r for r in pairs}
    accounting = json.loads(
        (ROOT / plans[NEW]["run_directory"] / "full_run_summary.json").read_text(encoding="utf8")
    )
    manifest = dict(
        created_at=now(),
        run_ids=[OLD, NEW],
        pairs=1814,
        unique_questions=756,
        primary_tasks=756,
        secondary_tasks=1058,
        unchanged_answer_questions=len({r["question_id"] for r in unchanged}),
        unchanged_answer_pairs=len(unchanged),
        unchanged_pairs_with_score_changes=sum(r["new_minus_previous"] != 0 for r in unchanged),
        previous_repetition_flagged_questions=sum(
            r["previous_repetition_flag"] for r in unique.values()
        ),
        new_repetition_flagged_questions=sum(r["new_repetition_flag"] for r in unique.values()),
        previous_temperature=None,
        new_temperature=None,
        previous_top_p=None,
        new_top_p=None,
        inference_metadata_status="Apertus temperature/top_p not supplied for either condition; no values inferred from filename or other models",
        source_results_sha256={rid: file_hash(path) for rid, path in paths.items()},
        rubric_sha256=plans[NEW]["rubric_sha256"],
        evaluator_template_sha256=plans[NEW]["evaluator_template_sha256"],
        no_new_judge_requests=True,
        existing_manifests_modified=False,
        result_label=LABEL,
    )
    write_json(OUTPUT / "comparison_manifest.json", manifest)
    book = Workbook()
    book.remove(book.active)
    for title, values in [
        ("Metric and subgroup comparisons", summaries),
        ("All matched question metrics", pairs),
        ("Identical answer controls", unchanged),
        ("Comparison provenance", [manifest]),
    ]:
        add_sheet(book, title, values)
    book.save(OUTPUT / "apertus_previous_vs_new_workbook.xlsx")
    report = [
        "# Apertus: previous versus new workbook run",
        "",
        LABEL,
        "",
        "Both runs completed 1,814/1,814 unique metric evaluations over the same 756 questions, with 756 primary and 1,058 secondary tasks. "
        "Both used four-worker execution and the same fixed v2 scoring protocol. The new run has zero final failed/missing evaluations. "
        "No new judge calls were made for this comparison.",
        "",
        "| Metric | Tasks | Previous mean | New mean | Change |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in summaries:
        if r["grouping"] == "metric":
            report.append(
                f"| {r['evaluation_metric']} | {r['pairs']} | {r['previous_mean']:.4f} | {r['new_mean']:.4f} | {r['mean_paired_difference']:+.4f} |"
            )
    for axis in ["language", "metric_role"]:
        report += [
            "",
            f"## {axis} comparison",
            "",
            f"| Metric | {axis} | Tasks | Previous mean | New mean | Change |",
            "|---|---|---:|---:|---:|---:|",
        ]
        for r in summaries:
            if r["grouping"] == axis:
                report.append(
                    f"| {r['evaluation_metric']} | {r[axis]} | {r['pairs']} | {r['previous_mean']:.4f} | {r['new_mean']:.4f} | {r['mean_paired_difference']:+.4f} |"
                )
    report += [
        "",
        "## Findings",
        "",
        "New means are higher on M1, M2, M3, M5 and M7, unchanged on M4, and slightly lower on M6. "
        "The largest descriptive increase is M3 (+0.0440 on the 0-1 scale). This is not evidence of statistical significance, "
        "a calibrated scientific improvement or a causal temperature effect.",
        "",
        f"Identical answer strings occur for {manifest['unchanged_answer_questions']} question(s), covering {len(unchanged)} metric pair(s). "
        f"{manifest['unchanged_pairs_with_score_changes']} identical-answer pairs changed score on repeat judging. "
        "This is a limited repeat-judgment control, not a full-run uncertainty estimate.",
        "",
        f"Exploratory repetition flags: previous {manifest['previous_repetition_flagged_questions']}/756; new {manifest['new_repetition_flagged_questions']}/756. "
        "Both use the same derived four-gram heuristic. Repetition labels did not alter prompts or exclude answers. "
        "Repetition subgroup comparisons and previous-response truncation subgroup results are exported, but reflect different question mixes. "
        "New truncation/termination flags were not supplied and are not copied from earlier responses.",
        "",
        "## Generation and scoring limitations",
        "",
        "Neither supplied Apertus source establishes temperature or top_p for both runs. "
        "The workbook temperature columns apply to GC LLM only, and the user-reported 0.95 discussed for Llama must not be attributed to Apertus. "
        "The original Apertus export provides a 1024-token cap, model revision and source run ID; equivalent detailed metadata for the "
        "new answer column is unavailable. Thus this is a comparison of observed answer sets rather than a controlled temperature experiment.",
        "",
        "Question/reference/context, language, role, judge identity and rubric/template hashes match across every pair. "
        "Judge sampling remains server-default/unknown in both scoring runs. Although both used four workers, server load, timing "
        "and caching can differ. Known rubric-interpretation limitations remain; no steps/bands were modified, no second normalization "
        "was applied, and no arbitrary overall Canadian-ness score or team/scientific approval is claimed.",
        "",
        f"Actual new scoring HTTP attempts: {accounting['scoring_http_attempts']}; discovery calls: {accounting['discovery_http_attempts']}; "
        f"HTTP status counts: {accounting['http_status_counts']}; API-reported tokens: {accounting['api_reported_tokens']}.",
        "",
        f"Rubric SHA-256: `{plans[NEW]['rubric_sha256']}`",
        "",
        f"Evaluator-template SHA-256: `{plans[NEW]['evaluator_template_sha256']}`",
        "",
        "## Files",
        "",
        "`apertus_previous_vs_new_workbook.xlsx`, `question_metric_comparisons.csv`/`.jsonl`, "
        "`metric_language_role_comparisons.csv`/`.jsonl`, `comparison_manifest.json`. "
        "These retain both complete answers and explanations, question-level score changes, metric summaries, "
        "English/French and primary/secondary breakdowns. Existing run outputs were preserved.",
        "",
    ]
    text = "\n".join(report)
    (OUTPUT / "report.md").write_text(text, encoding="utf8")
    (ROOT / "docs/apertus_previous_vs_new_workbook_comparison.md").write_text(text, encoding="utf8")
    print(
        json.dumps(
            dict(
                metric_comparisons=[r for r in summaries if r["grouping"] == "metric"],
                manifest=manifest,
                output=str(OUTPUT),
            )
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
