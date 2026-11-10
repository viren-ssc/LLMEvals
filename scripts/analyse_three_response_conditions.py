"""Paired previous/workbook/cleaned comparison; reads completed scores only."""

import argparse
import json
import statistics
from collections import Counter, defaultdict
from itertools import combinations

from openpyxl import Workbook

from canadianness_eval.final_metrics import file_hash
from canadianness_eval.hpc_ingestion import read_records
from canadianness_eval.research_exports import LABEL, add_sheet, table
from canadianness_eval.research_run import verify_plan
from canadianness_eval.settings import ROOT
from canadianness_eval.storage import now, write_json


def analyse(model):
    baseline = (
        "apertus_full_as_generated_c4_20261107_v2"
        if model == "apertus"
        else f"{model}_full_as_generated_20261106_v2"
    )
    if model == "llama":
        baseline = "llama_full_20261106_v2"
    runs = dict(
        previous=baseline,
        workbook=f"{model}_mixed_temperature_workbook_c4_20261107_v2",
        cleaned=f"{model}_cleaned_responses_c4_20261107_v2",
    )
    output = ROOT / "outputs/comparisons" / f"{model}_previous_workbook_cleaned_20261107"
    output.mkdir(parents=True, exist_ok=True)
    plans = {
        name: verify_plan(ROOT / "config/research" / rid / "experiment.json")
        for name, rid in runs.items()
    }
    paths = {name: ROOT / p["run_directory"] / "all_results.jsonl" for name, p in plans.items()}
    data = {
        name: {(r["question_id"], r["evaluation_metric"]): r for r in read_records(path)}
        for name, path in paths.items()
    }
    assert all(len(r) == 1814 and set(r) == set(data["previous"]) for r in data.values())
    clean_metadata = {
        r["question_id"]: r
        for r in read_records(
            ROOT / plans["cleaned"]["as_generated_contract"]["source_metadata_sidecar"]
        )
    }
    workbook_metadata = {
        r["question_id"]: r
        for r in read_records(
            ROOT / plans["workbook"]["as_generated_contract"]["source_metadata_sidecar"]
        )
    }
    records = []
    all_judgments = []
    for key in data["previous"]:
        old = data["previous"][key]
        raw = data["workbook"][key]
        clean = data["cleaned"][key]
        for r in [old, raw, clean]:
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
                assert r[field] == old[field], field
        changed = raw["model_answer"] != clean["model_answer"]
        assert changed == clean_metadata[key[0]]["answer_changed_versus_parent_workbook"]
        row = dict(
            question_id=key[0],
            evaluated_model=model,
            evaluation_metric=key[1],
            language=old["language"],
            metric_role=old["metric_role"],
            primary_metric=old["primary_metric"],
            cleaning_changed_answer=changed,
            question=old["question"],
            reference_answer=old["reference_answer"],
            context_supporting_summary=old["context_supporting_summary"],
            workbook_generation_metadata=workbook_metadata[key[0]],
            cleaning_metadata=clean_metadata[key[0]],
            workbook_minus_previous=raw["score"] - old["score"],
            cleaned_minus_workbook=clean["score"] - raw["score"],
            cleaned_minus_previous=clean["score"] - old["score"],
            result_label=LABEL,
        )
        for name, values in data.items():
            r = values[key]
            row.update(
                {
                    name + "_score": r["score"],
                    name + "_answer": r["model_answer"],
                    name + "_reason": r["judge_reason"],
                    name + "_run_id": runs[name],
                }
            )
            all_judgments.append(
                dict(r, comparison_condition=name, cleaning_changed_answer=changed)
            )
        records.append(row)
    table(output / "all_question_metric_conditions", records)
    table(output / "all_5442_individual_judgments", all_judgments)
    summaries = []
    for axes in [(), ("language",), ("metric_role",), ("cleaning_changed_answer",)]:
        groups = defaultdict(list)
        for r in records:
            groups[(r["evaluation_metric"], *(r[k] for k in axes))].append(r)
        for key, values in sorted(groups.items()):
            row = dict(
                evaluation_metric=key[0],
                grouping="/".join(axes) or "metric",
                **dict(zip(axes, key[1:])),
                tasks=len(values),
                questions=len({r["question_id"] for r in values}),
                result_label=LABEL,
            )
            for name in runs:
                row[name + "_mean"] = statistics.mean(r[name + "_score"] for r in values)
            for delta in [
                "workbook_minus_previous",
                "cleaned_minus_workbook",
                "cleaned_minus_previous",
            ]:
                row[delta + "_mean"] = statistics.mean(r[delta] for r in values)
            summaries.append(row)
    table(output / "metric_language_role_summaries", summaries)
    contrasts = []
    for first, second in combinations(runs, 2):
        for metric in sorted({r["evaluation_metric"] for r in records}):
            values = [r for r in records if r["evaluation_metric"] == metric]
            contrasts.append(
                dict(
                    first_condition=first,
                    second_condition=second,
                    evaluation_metric=metric,
                    tasks=len(values),
                    first_mean=statistics.mean(r[first + "_score"] for r in values),
                    second_mean=statistics.mean(r[second + "_score"] for r in values),
                    mean_second_minus_first=statistics.mean(
                        r[second + "_score"] - r[first + "_score"] for r in values
                    ),
                    second_higher=sum(r[second + "_score"] > r[first + "_score"] for r in values),
                    ties=sum(r[second + "_score"] == r[first + "_score"] for r in values),
                    second_lower=sum(r[second + "_score"] < r[first + "_score"] for r in values),
                    identical_answer_pairs=sum(
                        r[first + "_answer"] == r[second + "_answer"] for r in values
                    ),
                    result_label=LABEL,
                )
            )
    table(output / "all_three_pairwise_metric_comparisons", contrasts)
    decomposition = []
    for metric in sorted({r["evaluation_metric"] for r in records}):
        values = [r for r in records if r["evaluation_metric"] == metric]
        row = dict(
            evaluation_metric=metric,
            total_tasks=len(values),
            full_mean_cleaned_minus_workbook=statistics.mean(
                r["cleaned_minus_workbook"] for r in values
            ),
            result_label=LABEL,
        )
        for changed, label in [(True, "changed"), (False, "unchanged")]:
            subset = [r for r in values if r["cleaning_changed_answer"] == changed]
            row.update(
                {
                    label + "_tasks": len(subset),
                    label + "_score_changed": sum(r["cleaned_minus_workbook"] != 0 for r in subset),
                    label + "_mean_paired_change": statistics.mean(
                        r["cleaned_minus_workbook"] for r in subset
                    )
                    if subset
                    else None,
                    label + "_contribution_to_full_metric_mean_change": sum(
                        r["cleaned_minus_workbook"] for r in subset
                    )
                    / len(values),
                }
            )
        decomposition.append(row)
    table(output / "cleaning_changed_vs_unchanged_decomposition", decomposition)
    changed = [r for r in records if r["cleaning_changed_answer"]]
    unchanged = [r for r in records if not r["cleaning_changed_answer"]]
    table(output / "cleaning_affected_question_metrics", changed)
    grouped = defaultdict(list)
    for r in records:
        grouped[r["question_id"]].append(r)
    question_rows = []
    for qid, values in sorted(grouped.items()):
        r = values[0]
        question_rows.append(
            dict(
                question_id=qid,
                language=r["language"],
                primary_metric=r["primary_metric"],
                question=r["question"],
                reference_answer=r["reference_answer"],
                context_supporting_summary=r["context_supporting_summary"],
                cleaning_changed_answer=r["cleaning_changed_answer"],
                scores_by_metric={
                    v["evaluation_metric"]: {n: v[n + "_score"] for n in runs} for v in values
                },
                **{n + "_answer": r[n + "_answer"] for n in runs},
                result_label=LABEL,
            )
        )
    table(output / "question_level_three_conditions", question_rows)
    manifest = dict(
        created_at=now(),
        evaluated_model=model,
        run_ids=runs,
        successful_each=1814,
        successful_total=5442,
        question_metric_triples=1814,
        unique_questions=756,
        cleaning_changed_questions=len({r["question_id"] for r in changed}),
        cleaning_changed_metric_tasks=len(changed),
        cleaning_unchanged_questions=len({r["question_id"] for r in unchanged}),
        cleaning_unchanged_metric_tasks=len(unchanged),
        unchanged_pairs_with_score_changes=sum(r["cleaned_minus_workbook"] != 0 for r in unchanged),
        unchanged_pair_score_change_rate=sum(r["cleaned_minus_workbook"] != 0 for r in unchanged)
        / len(unchanged),
        source_results_sha256={name: file_hash(p) for name, p in paths.items()},
        rubric_sha256=plans["cleaned"]["rubric_sha256"],
        evaluator_template_sha256=plans["cleaned"]["evaluator_template_sha256"],
        no_new_judge_requests=True,
        existing_runs_unchanged=True,
        result_label=LABEL,
    )
    if model == "gc_llm":
        manifest["workbook_temperature_question_counts"] = dict(
            Counter(str(r["generation_temperature"]) for r in workbook_metadata.values())
        )
        manifest["workbook_reused_questions"] = sum(
            bool(r["answer_reused"]) for r in workbook_metadata.values()
        )
    write_json(output / "comparison_manifest.json", manifest)
    book = Workbook()
    book.remove(book.active)
    for title, values in [
        ("Three condition summaries", summaries),
        ("All three pairwise comparisons", contrasts),
        ("All question metric triples", records),
        ("Changed unchanged decomposition", decomposition),
        ("Cleaning affected judgments", changed),
        ("Question level scores", question_rows),
        ("Provenance", [manifest]),
    ]:
        assert len(title) <= 31
        add_sheet(book, title, values)
    book.save(output / f"{model}_three_run_comparison.xlsx")
    report = [
        f"# {model}: previous, workbook and cleaned responses",
        "",
        LABEL,
        "",
        "All three runs completed 1,814/1,814 evaluations over the same 756 questions: 756 primary and 1,058 secondary tasks per run. "
        "This analysis aligns all 1,814 question-metric triples and retains every one of the 5,442 scores and explanations. "
        "No new judge calls were made and no source answer, previous judgment or frozen run manifest was modified.",
        "",
        "| Metric | Tasks | Previous | Workbook | Cleaned | Cleaned minus workbook |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in summaries:
        if r["grouping"] == "metric":
            report.append(
                f"| {r['evaluation_metric']} | {r['tasks']} | {r['previous_mean']:.4f} | {r['workbook_mean']:.4f} | {r['cleaned_mean']:.4f} | {r['cleaned_minus_workbook_mean']:+.4f} |"
            )
    report += [
        "",
        "## Cleaning and repeat-judgment variation",
        "",
        f"Cleaning changes {manifest['cleaning_changed_questions']} answers, covering {len(changed)} metric judgments. "
        f"Of the {len(unchanged)} judgments with identical answer text, {manifest['unchanged_pairs_with_score_changes']} "
        f"({manifest['unchanged_pair_score_change_rate']:.1%}) have different scores on repeat judging. "
        "Thus full-set differences include changes on unedited responses and cannot be attributed solely to cleaning or interpreted as proof of judge repetition bias. "
        "The changed/unchanged decomposition exports each subset contribution to every metric mean shift. "
        "Edited answers may also differ in factual coverage or meaning; no cleaning algorithm or full edit provenance was supplied. "
        "The unchanged subset is descriptive evidence of repeatability limits, not a calibrated causal correction for edited-response scores.",
    ]
    if model == "gc_llm":
        report += [
            "",
            "For GC LLM, cleaned means rise on M1, M2, M6 and M7 relative to the workbook and fall on M3-M5. "
            "Against the previous run, cleaned means are higher only on M1. Effects are mixed; no uniform improvement is established. "
            "The original workbook explicitly has 755 temperature-0.7 answers and one reused temperature-0 answer. "
            "The earlier source did not directly capture temperature; later replacement provenance retrospectively attributes its source run to temperature 0. "
            "This is not a pure controlled temperature comparison. top_p is not supplied for GC LLM and is not inferred from the Llama discussion. "
            "Cleaned responses are user-edited workbook strings, not new generations at a third temperature.",
        ]
    for axis in ["language", "metric_role", "cleaning_changed_answer"]:
        report += [
            "",
            f"## {axis} breakdown",
            "",
            f"| Metric | {axis} | Tasks | Previous | Workbook | Cleaned |",
            "|---|---|---:|---:|---:|---:|",
        ]
        for r in summaries:
            if r["grouping"] == axis:
                report.append(
                    f"| {r['evaluation_metric']} | {r[axis]} | {r['tasks']} | {r['previous_mean']:.4f} | {r['workbook_mean']:.4f} | {r['cleaned_mean']:.4f} |"
                )
    accounting = json.loads(
        (ROOT / plans["cleaned"]["run_directory"] / "full_run_summary.json").read_text(
            encoding="utf8"
        )
    )
    report += [
        "",
        "## Configuration and execution limits",
        "",
        "All pairs match question, reference, supporting context, language, assignment role, judge deployment and fixed rubric/template checksums. "
        "The judge used omitted-temperature/server-default sampling across all conditions. Determinism is not established, and timing/load/cache conditions vary. "
        "Earlier GC LLM/Llama runs were sequential while workbook and cleaned runs used four workers. "
        "Generation prompts, seeds, exact revisions and all inference controls were not supplied for both original conditions. "
        "Missing source metadata is not borrowed from other models or changed responses. No extra normalization or arbitrary overall score is computed. "
        "Known rubric interpretation limitations and pending human calibration remain in force.",
        "",
        f"Cleaned-run scoring HTTP attempts: {accounting['scoring_http_attempts']}; discovery calls: {accounting['discovery_http_attempts']}; "
        f"HTTP outcomes: {accounting['http_status_counts']}; API-reported tokens: {accounting['api_reported_tokens']}.",
        "",
        f"Rubric SHA-256: `{manifest['rubric_sha256']}`",
        "",
        f"Evaluator-template SHA-256: `{manifest['evaluator_template_sha256']}`",
        "",
        "## Files",
        "",
        f"`{model}_three_run_comparison.xlsx`: side-by-side scores, all three paired contrasts, full answers/reasons, language/role groups, "
        "cleaning-affected cases, changed/unchanged decomposition and question-level score mappings. "
        "Each table is also exported as CSV/JSONL. `all_5442_individual_judgments.*` retains the full original evaluation metadata. "
        "`comparison_manifest.json` records source hashes and counts. All outputs remain AI-provisional, pending calibration.",
        "",
    ]
    text = "\n".join(report)
    (output / "report.md").write_text(text, encoding="utf8")
    (ROOT / "docs" / f"{model}_previous_workbook_cleaned_comparison.md").write_text(
        text, encoding="utf8"
    )
    print(
        json.dumps(
            dict(
                metric_summaries=[r for r in summaries if r["grouping"] == "metric"],
                manifest=manifest,
                output=str(output),
            )
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["llama", "gc_llm", "apertus"], required=True)
    analyse(parser.parse_args().model)
