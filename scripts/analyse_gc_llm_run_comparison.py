"""Post-hoc paired comparison of completed GC LLM runs; no scoring requests."""

import json
import statistics
from collections import Counter, defaultdict

from openpyxl import Workbook

from canadianness_eval.final_metrics import file_hash
from canadianness_eval.hpc_ingestion import read_records
from canadianness_eval.research_exports import LABEL, add_sheet, table
from canadianness_eval.research_run import verify_plan
from canadianness_eval.settings import ROOT
from canadianness_eval.storage import now, write_json

OLD = "gc_llm_full_as_generated_20261106_v2"
NEW = "gc_llm_mixed_temperature_workbook_c4_20261107_v2"
OUTPUT = ROOT / "outputs/comparisons/gc_llm_previous_vs_mixed_temperature_20261107"


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    plans = {
        rid: verify_plan(ROOT / "config/research" / rid / "experiment.json") for rid in [OLD, NEW]
    }
    paths = {
        rid: ROOT / plans[rid]["run_directory"] / "as_generated_results.jsonl" for rid in [OLD, NEW]
    }
    results = {rid: read_records(path) for rid, path in paths.items()}
    old = {(r["question_id"], r["evaluation_metric"]): r for r in results[OLD]}
    assert len(old) == len(results[NEW]) == 1814
    pairs = []
    for r in results[NEW]:
        prior = old[r["question_id"], r["evaluation_metric"]]
        assert prior["status"] == r["status"] == "SUCCESS"
        for k in [
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
            assert r[k] == prior[k], k
        meta = r["generation_metadata"]
        previous_meta = prior["generation_metadata"]
        pairs.append(
            dict(
                question_id=r["question_id"],
                evaluation_metric=r["evaluation_metric"],
                language=r["language"],
                metric_role=r["metric_role"],
                primary_metric=r["primary_metric"],
                previous_score=prior["score"],
                new_score=r["score"],
                new_minus_previous=r["score"] - prior["score"],
                answer_changed=r["model_answer"] != prior["model_answer"],
                new_generation_temperature=meta["generation_temperature"],
                new_answer_reused=meta["answer_reused"],
                previous_repetition_flag=previous_meta["analysis_repetition_flag"],
                new_repetition_flag=meta["analysis_repetition_flag"],
                previous_truncated=previous_meta["truncated"],
                new_truncated=None,
                previous_answer=prior["model_answer"],
                new_answer=r["model_answer"],
                previous_reason=prior["judge_reason"],
                new_reason=r["judge_reason"],
                question=r["question"],
                reference_answer=r["reference_answer"],
                context_supporting_summary=r["context_supporting_summary"],
                previous_generation_metadata=previous_meta,
                new_generation_metadata=meta,
                previous_run_id=OLD,
                new_run_id=NEW,
                result_label=LABEL,
            )
        )
    summaries = []
    for axes in [
        (),
        ("language",),
        ("metric_role",),
        ("answer_changed",),
        ("new_generation_temperature",),
        ("new_answer_reused",),
        ("previous_repetition_flag",),
        ("new_repetition_flag",),
    ]:
        groups = defaultdict(list)
        for r in pairs:
            groups[(r["evaluation_metric"], *(r[k] for k in axes))].append(r)
        for key, rows in sorted(groups.items()):
            summaries.append(
                dict(
                    evaluation_metric=key[0],
                    grouping="/".join(axes) or "metric",
                    **dict(zip(axes, key[1:])),
                    pairs=len(rows),
                    previous_mean=statistics.mean(r["previous_score"] for r in rows),
                    new_mean=statistics.mean(r["new_score"] for r in rows),
                    mean_paired_difference=statistics.mean(r["new_minus_previous"] for r in rows),
                    median_paired_difference=statistics.median(
                        r["new_minus_previous"] for r in rows
                    ),
                    new_higher=sum(r["new_minus_previous"] > 0 for r in rows),
                    ties=sum(r["new_minus_previous"] == 0 for r in rows),
                    new_lower=sum(r["new_minus_previous"] < 0 for r in rows),
                    result_label=LABEL,
                )
            )
    table(OUTPUT / "question_metric_comparisons", pairs)
    table(OUTPUT / "metric_language_role_comparisons", summaries)
    unchanged = [r for r in pairs if not r["answer_changed"]]
    question_rows = {r["question_id"]: r for r in pairs}
    metadata = dict(
        created_at=now(),
        run_ids=[OLD, NEW],
        pairs=1814,
        unique_questions=756,
        primary_tasks=756,
        secondary_tasks=1058,
        new_temperature_question_counts=dict(
            Counter(str(r["new_generation_temperature"]) for r in question_rows.values())
        ),
        new_reused_questions=sum(r["new_answer_reused"] for r in question_rows.values()),
        unchanged_answer_questions=len({r["question_id"] for r in unchanged}),
        unchanged_answer_pairs=len(unchanged),
        unchanged_pairs_with_score_change=sum(r["new_minus_previous"] != 0 for r in unchanged),
        previous_repetition_flagged_questions=sum(
            r["previous_repetition_flag"] for r in question_rows.values()
        ),
        new_repetition_flagged_questions=sum(
            r["new_repetition_flag"] for r in question_rows.values()
        ),
        new_termination_metadata="Not supplied; earlier flags must not be copied to changed responses",
        source_results_sha256={rid: file_hash(path) for rid, path in paths.items()},
        rubric_sha256=plans[NEW]["rubric_sha256"],
        evaluator_template_sha256=plans[NEW]["evaluator_template_sha256"],
        no_new_judge_requests=True,
        existing_manifests_modified=False,
        result_label=LABEL,
    )
    write_json(OUTPUT / "comparison_manifest.json", metadata)
    book = Workbook()
    book.remove(book.active)
    add_sheet(book, "Metric and subgroup comparisons", summaries)
    add_sheet(book, "All matched question metrics", pairs)
    add_sheet(book, "Reused identical answer control", unchanged)
    add_sheet(book, "Comparison provenance", [metadata])
    book.save(OUTPUT / "gc_llm_previous_vs_mixed_temperature.xlsx")
    report = [
        "# GC LLM: previous versus new mixed-temperature run",
        "",
        LABEL,
        "",
        "Both runs completed 1,814/1,814 unique question-model-metric evaluations over the same 756 questions: "
        "756 primary and 1,058 secondary. The new run has no final failed/missing tasks; all 1,814 scoring HTTP calls returned 200, "
        "with one model-discovery call. Its API-reported usage was 4,176,342 tokens. No new judge calls were used for this comparison.",
        "",
        "| Metric | Tasks | Previous mean | New mean | New minus previous |",
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
        "## Findings and interpretation",
        "",
        "The new run is higher on M1 and lower on M2-M7. The largest descriptive decline is M4 (-0.0634 on the 0-1 scale); "
        "M7 declines about 0.0354. These are paired observed differences, not calibrated scientific rankings or proof of a temperature effect.",
        "",
        "The new workbook explicitly labels 755 GC LLM answers as temperature 0.7, and one reused response "
        "(CA-EXP2-152) as temperature 0.0. This is a mixed-condition run, not a pure temperature-0.7 benchmark. "
        "That reused answer covers two metric tasks: M5 changes from 0.4 to 0.1 despite identical response text, while M7 remains 0.2. "
        "This illustrates repeat-judgment variation; one question is insufficient to estimate the uncertainty of the full comparison.",
        "",
        "The earlier raw/provenance files did not directly record temperature or top_p. The later workbook replacement-provenance "
        "sheet identifies its reused source run as temperature 0.0; this is retrospective source attribution, not an original complete "
        "per-response inference manifest. top_p remains unavailable for GC LLM; no value is inferred from the Llama discussion.",
        "",
        f"Exploratory repetition flags: previous {metadata['previous_repetition_flagged_questions']}/756, new {metadata['new_repetition_flagged_questions']}/756. "
        "These use the same derived four-gram heuristic; flags are analysis only and were never judge instructions or exclusion rules. "
        "Subgroup means are exported but are confounded by question mix. Previous truncation flags are retained as previous-response metadata only; "
        "new termination flags/output-token counts/revision were not supplied by the workbook and are not inferred.",
        "",
        "## Scoring and comparability",
        "",
        "Question IDs, benchmark evidence, assignments, rubric checksum and v2 evaluator-template checksum match across all 1,814 pairs. "
        "The same gpt-oss-120b scoring protocol was used; judge temperature was omitted and the numeric server default is unknown. "
        "Earlier execution was sequential; the new execution used four workers. Server load, caching and timing differed. "
        "Generation seeds, full prompts, revisions and all decoding controls were not supplied for both conditions, so temperature "
        "cannot be isolated as the sole cause. No extra normalization, rubric changes, arbitrary combined Canadian-ness score, "
        "scientific calibration or team approval is claimed.",
        "",
        f"Rubric SHA-256: `{plans[NEW]['rubric_sha256']}`",
        "",
        f"Evaluator-template SHA-256: `{plans[NEW]['evaluator_template_sha256']}`",
        "",
        "## Files",
        "",
        "`gc_llm_previous_vs_mixed_temperature.xlsx`: all pairs, original/new answers and reasons, metric/language/role summaries, "
        "mixed-temperature and repetition groups, and reused-answer control. `question_metric_comparisons.*` and "
        "`metric_language_role_comparisons.*` provide CSV/JSONL exports. `comparison_manifest.json` records source hashes and settings limitations. "
        "The new run itself retains its full independent results at `outputs/evaluations/"
        + NEW
        + "/`.",
        "",
    ]
    text = "\n".join(report)
    (OUTPUT / "report.md").write_text(text, encoding="utf8")
    (ROOT / "docs/gc_llm_previous_vs_mixed_temperature_comparison.md").write_text(
        text, encoding="utf8"
    )
    print(
        json.dumps(
            dict(
                metric_comparisons=[r for r in summaries if r["grouping"] == "metric"],
                metadata=metadata,
                output=str(OUTPUT),
            )
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
