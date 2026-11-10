"""Post-hoc three-condition Llama analysis; no scoring or source/run changes."""

import json
import statistics
from collections import defaultdict
from itertools import combinations

from openpyxl import Workbook

from canadianness_eval.final_metrics import file_hash
from canadianness_eval.hpc_ingestion import read_records
from canadianness_eval.research_exports import LABEL, add_sheet, table
from canadianness_eval.research_run import verify_plan
from canadianness_eval.settings import ROOT
from canadianness_eval.storage import now, write_json

RUNS = {
    "temp_0": "llama_full_20261106_v2",
    "temp_07": "llama_mixed_temperature_workbook_c4_20261107_v2",
    "cleaned": "llama_cleaned_responses_c4_20261107_v2",
}
OUTPUT = ROOT / "outputs/comparisons/llama_temp0_temp07_cleaned_20261107"


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    plans = {
        name: verify_plan(ROOT / "config/research" / rid / "experiment.json")
        for name, rid in RUNS.items()
    }
    paths = {
        name: ROOT / plan["run_directory"] / "all_results.jsonl" for name, plan in plans.items()
    }
    data = {
        name: {(r["question_id"], r["evaluation_metric"]): r for r in read_records(path)}
        for name, path in paths.items()
    }
    assert all(len(rows) == 1814 and set(rows) == set(data["temp_0"]) for rows in data.values())
    clean_meta = {
        r["question_id"]: r
        for r in read_records(
            ROOT / plans["cleaned"]["as_generated_contract"]["source_metadata_sidecar"]
        )
    }
    records = []
    long = []
    for key in data["temp_0"]:
        original = data["temp_0"][key]
        raw = data["temp_07"][key]
        clean = data["cleaned"][key]
        for r in [original, raw, clean]:
            assert r["status"] == "SUCCESS" and 0 <= r["score"] <= 1 and r["judge_reason"].strip()
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
                assert r[field] == original[field], field
        changed = raw["model_answer"] != clean["model_answer"]
        assert changed == clean_meta[key[0]]["answer_changed_versus_parent_workbook"]
        row = dict(
            question_id=key[0],
            evaluation_metric=key[1],
            language=original["language"],
            metric_role=original["metric_role"],
            primary_metric=original["primary_metric"],
            cleaning_changed_answer=changed,
            question=original["question"],
            reference_answer=original["reference_answer"],
            context_supporting_summary=original["context_supporting_summary"],
            cleaned_minus_temp07=clean["score"] - raw["score"],
            temp07_minus_temp0=raw["score"] - original["score"],
            cleaned_minus_temp0=clean["score"] - original["score"],
            cleaning_metadata=clean_meta[key[0]],
            temperature_label_provenance="User-identified temperatures; not independently recorded in supplied Llama sources",
            result_label=LABEL,
        )
        for name, rows in data.items():
            r = rows[key]
            row.update(
                {
                    name + "_score": r["score"],
                    name + "_answer": r["model_answer"],
                    name + "_reason": r["judge_reason"],
                    name + "_run_id": RUNS[name],
                }
            )
            long.append(dict(r, comparison_condition=name, cleaning_changed_answer=changed))
        records.append(row)
    table(OUTPUT / "all_question_metric_conditions", records)
    table(OUTPUT / "all_5442_individual_judgments", long)
    summaries = []
    for axes in [(), ("language",), ("metric_role",), ("cleaning_changed_answer",)]:
        groups = defaultdict(list)
        for r in records:
            groups[(r["evaluation_metric"], *(r[k] for k in axes))].append(r)
        for key, rows in sorted(groups.items()):
            summary = dict(
                evaluation_metric=key[0],
                grouping="/".join(axes) or "metric",
                **dict(zip(axes, key[1:])),
                tasks=len(rows),
                questions=len({r["question_id"] for r in rows}),
                result_label=LABEL,
            )
            for name in RUNS:
                summary[name + "_mean"] = statistics.mean(r[name + "_score"] for r in rows)
            for name in ["temp07_minus_temp0", "cleaned_minus_temp07", "cleaned_minus_temp0"]:
                summary[name + "_mean"] = statistics.mean(r[name] for r in rows)
            summaries.append(summary)
    table(OUTPUT / "metric_language_role_summaries", summaries)
    contrasts = []
    for first, second in combinations(RUNS, 2):
        for metric in sorted({r["evaluation_metric"] for r in records}):
            rows = [r for r in records if r["evaluation_metric"] == metric]
            contrasts.append(
                dict(
                    first_condition=first,
                    second_condition=second,
                    evaluation_metric=metric,
                    tasks=len(rows),
                    first_mean=statistics.mean(r[first + "_score"] for r in rows),
                    second_mean=statistics.mean(r[second + "_score"] for r in rows),
                    mean_second_minus_first=statistics.mean(
                        r[second + "_score"] - r[first + "_score"] for r in rows
                    ),
                    second_higher=sum(r[second + "_score"] > r[first + "_score"] for r in rows),
                    ties=sum(r[second + "_score"] == r[first + "_score"] for r in rows),
                    second_lower=sum(r[second + "_score"] < r[first + "_score"] for r in rows),
                    identical_answer_pairs=sum(
                        r[second + "_answer"] == r[first + "_answer"] for r in rows
                    ),
                    result_label=LABEL,
                )
            )
    table(OUTPUT / "all_three_pairwise_metric_comparisons", contrasts)
    decomposition = []
    for metric in sorted({r["evaluation_metric"] for r in records}):
        rows = [r for r in records if r["evaluation_metric"] == metric]
        value = dict(
            evaluation_metric=metric,
            total_tasks=len(rows),
            full_mean_cleaned_minus_temp07=statistics.mean(r["cleaned_minus_temp07"] for r in rows),
            result_label=LABEL,
        )
        for changed, label in [(True, "changed"), (False, "unchanged")]:
            subset = [r for r in rows if r["cleaning_changed_answer"] == changed]
            value[label + "_tasks"] = len(subset)
            value[label + "_pairs_with_score_changes"] = sum(
                r["cleaned_minus_temp07"] != 0 for r in subset
            )
            value[label + "_mean_paired_change"] = (
                statistics.mean(r["cleaned_minus_temp07"] for r in subset) if subset else None
            )
            value[label + "_contribution_to_full_metric_mean_change"] = sum(
                r["cleaned_minus_temp07"] for r in subset
            ) / len(rows)
        decomposition.append(value)
    table(OUTPUT / "cleaning_changed_vs_unchanged_decomposition", decomposition)
    changed = [r for r in records if r["cleaning_changed_answer"]]
    unchanged = [r for r in records if not r["cleaning_changed_answer"]]
    table(OUTPUT / "cleaning_affected_question_metrics", changed)
    question_groups = defaultdict(list)
    for r in records:
        question_groups[r["question_id"]].append(r)
    questions = []
    for qid, rows in sorted(question_groups.items()):
        first = rows[0]
        questions.append(
            dict(
                question_id=qid,
                language=first["language"],
                primary_metric=first["primary_metric"],
                applicable_metrics=[r["evaluation_metric"] for r in rows],
                cleaning_changed_answer=first["cleaning_changed_answer"],
                question=first["question"],
                reference_answer=first["reference_answer"],
                context_supporting_summary=first["context_supporting_summary"],
                scores_by_metric={
                    r["evaluation_metric"]: {name: r[name + "_score"] for name in RUNS}
                    for r in rows
                },
                **{name + "_answer": first[name + "_answer"] for name in RUNS},
                result_label=LABEL,
            )
        )
    table(OUTPUT / "question_level_three_conditions", questions)
    manifest = dict(
        created_at=now(),
        run_ids=RUNS,
        successful_each=1814,
        successful_total=5442,
        question_metric_triples=1814,
        unique_questions=756,
        cleaning_changed_questions=len({r["question_id"] for r in changed}),
        cleaning_changed_metric_tasks=len(changed),
        cleaning_unchanged_questions=len({r["question_id"] for r in unchanged}),
        cleaning_unchanged_metric_tasks=len(unchanged),
        unchanged_pairs_with_score_changes=sum(r["cleaned_minus_temp07"] != 0 for r in unchanged),
        unchanged_pair_score_change_rate=sum(r["cleaned_minus_temp07"] != 0 for r in unchanged)
        / len(unchanged),
        source_results_sha256={name: file_hash(path) for name, path in paths.items()},
        rubric_sha256=plans["cleaned"]["rubric_sha256"],
        evaluator_template_sha256=plans["cleaned"]["evaluator_template_sha256"],
        generation_temperature_labels="temp_0 and temp_07 are user-identified; source generation metadata incomplete",
        cleaned_condition="User-provided cleaned version of the temp_07-labelled workbook answers; not newly generated answers",
        top_p="0.95 retrospectively user-reported, not independently verified per run; see earlier Llama annotation",
        no_new_judge_requests=True,
        existing_runs_unchanged=True,
        result_label=LABEL,
    )
    write_json(OUTPUT / "comparison_manifest.json", manifest)
    book = Workbook()
    book.remove(book.active)
    for title, values in [
        ("Three condition summaries", summaries),
        ("All three pairwise comparisons", contrasts),
        ("All question metric triples", records),
        ("Changed unchanged decomposition", decomposition),
        ("Cleaning affected judgments", changed),
        ("Question level scores", questions),
        ("Provenance", [manifest]),
    ]:
        add_sheet(book, title, values)
    book.save(OUTPUT / "llama_temp0_temp07_cleaned_comparison.xlsx")
    report = [
        "# Llama: temperature 0, temperature 0.7 and cleaned answers",
        "",
        LABEL,
        "",
        "All three runs completed 1,814/1,814 evaluations: 756 questions, 756 primary and 1,058 secondary metric assignments per condition. "
        "This analysis aligns 1,814 question-metric triples and retains all 5,442 individual judgments without creating an overall Canadian-ness score. "
        "No new judge calls were made and no existing score or run manifest was changed.",
        "",
        "| Metric | Tasks | Temp 0 | Temp 0.7 | Cleaned | Cleaned minus temp 0.7 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in summaries:
        if r["grouping"] == "metric":
            report.append(
                f"| {r['evaluation_metric']} | {r['tasks']} | {r['temp_0_mean']:.4f} | {r['temp_07_mean']:.4f} | {r['cleaned_mean']:.4f} | {r['cleaned_minus_temp07_mean']:+.4f} |"
            )
    report += [
        "",
        "## Main interpretation",
        "",
        "Relative to the temp-0.7-labelled run, cleaned means are higher on M2 and M5 and lower on the other five metrics. "
        "These are mixed descriptive changes, not evidence that cleaning improved or reduced model quality or removed judge bias. "
        "Temperature labels follow the user identification; the original Llama sources do not independently establish them. "
        "The cleaned condition uses edited workbook answers, not a new model generation at a third temperature.",
        "",
        f"Only {manifest['cleaning_changed_questions']} answers changed, affecting {len(changed)} metric evaluations. "
        f"The remaining {len(unchanged)} evaluations use identical answer text to the temp-0.7-labelled condition. "
        f"Of those, {manifest['unchanged_pairs_with_score_changes']} ({manifest['unchanged_pair_score_change_rate']:.1%}) received different scores on repeat judging. "
        "Thus all-condition mean shifts include substantial repeat-judgment variation on unedited answers. "
        "Changed/unchanged subsets and their contribution to each metric mean change are explicitly separated. "
        "Even the eight edited-answer cases remain subject to judgment variation and possible changes in meaning or information content.",
        "",
        "A difference in score for an identical answer demonstrates observed repeatability limits in this deployment. "
        "It does not establish that cleaning caused those differences, nor quantify a causal correction to scores of edited answers. "
        "No significance test, deterministic-scoring claim or scientific calibration is implied.",
        "",
        "Changed question IDs: " + ", ".join(sorted({r["question_id"] for r in changed})) + ".",
    ]
    for axis in ["language", "metric_role", "cleaning_changed_answer"]:
        report += [
            "",
            f"## {axis} breakdown",
            "",
            f"| Metric | {axis} | Tasks | Temp 0 | Temp 0.7 | Cleaned |",
            "|---|---|---:|---:|---:|---:|",
        ]
        for r in summaries:
            if r["grouping"] == axis:
                report.append(
                    f"| {r['evaluation_metric']} | {r[axis]} | {r['tasks']} | {r['temp_0_mean']:.4f} | {r['temp_07_mean']:.4f} | {r['cleaned_mean']:.4f} |"
                )
    report += [
        "",
        "## Configuration and evidence limits",
        "",
        "All three use the same question/reference/context, fixed 42 steps, 35 scoring bands, v2 template and gpt-oss-120b judge. "
        "The temp-0-labelled run used one worker; the other two used four. Judge temperature was omitted in all scoring requests; "
        "the numeric server default and deterministic behavior are not established. Load, caching, timing and infrastructure interruptions differ. "
        "Full generation settings, seeds and checkpoint identity were not supplied for both original conditions. "
        "top_p=0.95 is retained only as a retrospective user report; no per-run value is independently inferred. "
        "The cleaning algorithm and full cleaning provenance were not supplied. No further cleaning or score normalization was performed.",
        "",
        "Supporting context is rubric-permitted judge-side evaluation evidence, not tested-model input or a guaranteed verbatim quotation. "
        "Other model answers and previous judgments were excluded from independent scoring; this post-hoc comparison reads already-completed results only.",
        "",
        f"Rubric SHA-256: `{manifest['rubric_sha256']}`",
        "",
        f"Evaluator-template SHA-256: `{manifest['evaluator_template_sha256']}`",
        "",
        "## Files",
        "",
        "`llama_temp0_temp07_cleaned_comparison.xlsx`: all three side-by-side conditions, all three paired contrasts, "
        "full responses and explanations, changed/unchanged decomposition, language and metric-role summaries, question-level score mappings. "
        "Every table is additionally exported as CSV/JSONL. `comparison_manifest.json` records all source hashes and limitations.",
        "",
    ]
    text = "\n".join(report)
    (OUTPUT / "report.md").write_text(text, encoding="utf8")
    (ROOT / "docs/llama_temp0_temp07_cleaned_comparison.md").write_text(text, encoding="utf8")
    print(
        json.dumps(
            dict(
                metric_summaries=[r for r in summaries if r["grouping"] == "metric"],
                manifest=manifest,
                output=str(OUTPUT),
            )
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
