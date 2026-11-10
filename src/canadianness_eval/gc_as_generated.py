"""As-generated GC LLM intake and post-run analysis; scoring uses the unchanged research workflow."""

import argparse
import hashlib
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import load_workbook

from .calibration.schema import CalibrationCase, load_cases
from .final_metrics import file_hash
from .hpc_ingestion import load_benchmark, read_records
from .hpc_workflow import save_jsonl
from .research_exports import add_sheet, table
from .research_run import LABEL, confirmation, exclusive, verify_plan
from .research_run import prepare as prepare_research
from .settings import ROOT
from .storage import write_json

RUN_ID = "gc_llm_full_as_generated_20261106_v2"
INCOMING = ROOT / "data/incoming/gc_llm_as_generated"
PROCESSED = ROOT / "data/processed/gc_llm_as_generated_v2"
PLAN = ROOT / "config/research" / RUN_ID / "experiment.json"
APPROVAL = PLAN.parent / "execution_approval.json"
LLAMA = ROOT / "outputs/evaluations/llama_full_20261106_v2"
SOURCE_NAMES = [
    "gc_llm_756_evaluation_1024_tokens.jsonl",
    "gc_llm_756_evaluation_1024_tokens.xlsx",
    "GC_LLM_756_As_Is_DeepEval_Generations.jsonl",
    "GC_LLM_756_As_Is_Generation_Provenance.jsonl",
    "GC_LLM_756_As_Is_Evaluation_Manifest.json",
]


def repetition_indicator(answer):
    """Analysis only: no response mutation, filtering, judge instruction or inferred source-audit label."""
    tokens = re.findall(r"\w+", answer.casefold(), flags=re.UNICODE)
    grams = [tuple(tokens[i : i + 4]) for i in range(max(0, len(tokens) - 3))]
    fraction = 1 - len(set(grams)) / len(grams) if grams else 0
    return dict(
        analysis_token_count=len(tokens),
        repeated_4gram_fraction=fraction,
        analysis_repetition_flag=len(tokens) >= 40 and fraction >= 0.30,
        repetition_flag_source="derived exploratory 4-gram heuristic; not supplied audit",
    )


def copy_sources():
    INCOMING.mkdir(parents=True, exist_ok=True)
    for name in SOURCE_NAMES:
        source = ROOT / name
        if not source.exists():
            source = Path("C:/Users/BhanderV/Downloads") / name
        if not source.exists():
            raise ValueError(f"Missing original source: {name}")
        dest = INCOMING / name
        if dest.exists() and file_hash(dest) != file_hash(source):
            raise ValueError("Existing intake differs; source files must not be overwritten")
        if not dest.exists():
            dest.write_bytes(source.read_bytes())
        if file_hash(dest) != file_hash(source):
            raise ValueError("Source copy was not byte-identical")


def unique_index(rows, label):
    result = {r["question_id"]: r for r in rows}
    if len(result) != len(rows) or len(result) != 756:
        raise ValueError(f"{label}: expected 756 unique question IDs")
    return result


def prepare():
    copy_sources()
    original_path = INCOMING / SOURCE_NAMES[0]
    original_hash = file_hash(original_path)
    workbook = INCOMING / SOURCE_NAMES[1]
    normalized = INCOMING / SOURCE_NAMES[2]
    sidecar = INCOMING / SOURCE_NAMES[3]
    contract = json.loads((INCOMING / SOURCE_NAMES[4]).read_text(encoding="utf-8-sig"))
    for key, path in [
        ("original_jsonl", original_path),
        ("normalized_generations", normalized),
        ("provenance_sidecar", sidecar),
    ]:
        if file_hash(path) != contract["files"][key]["sha256"]:
            raise ValueError(f"Source checksum differs from provided contract: {key}")
    original = unique_index(read_records(original_path), "original JSONL")
    generated = unique_index(read_records(normalized), "normalized JSONL")
    metadata = unique_index(read_records(sidecar), "generation provenance")
    excel = {r.question_id: r for r in load_benchmark(workbook, 756)}
    llama_cases = {
        c.question_id: c for c in load_cases(ROOT / "data/processed/llama_756_v1/all_cases.jsonl")
    }
    if not set(original) == set(generated) == set(metadata) == set(excel) == set(llama_cases):
        raise ValueError("Question IDs do not match GC source files and final Llama benchmark")
    cases = []
    provenance = []
    for qid, raw in original.items():
        answer = raw["gc_llm_answer"]
        if (
            not isinstance(answer, str)
            or not answer.strip()
            or generated[qid]["answer"] != answer
            or excel[qid].model_extra["gc_llm_answer"] != answer
        ):
            raise ValueError(f"Missing, altered or mismatched response: {qid}")
        if generated[qid]["evaluated_model"] != "gc_llm" or generated[qid]["status"] != "success":
            raise ValueError("Wrong normalized generation model/status")
        base = llama_cases[qid]
        for key in ["question", "reference_answer", "language", "primary_metric"]:
            if raw[key] != getattr(base, key) or getattr(excel[qid], key) != getattr(base, key):
                raise ValueError(f"Benchmark text/label mismatch: {qid}/{key}")
        if (
            raw["context_text"] != base.reference_context[0]
            or excel[qid].context_text != raw["context_text"]
        ):
            raise ValueError(f"Context mismatch: {qid}")
        labels = {m.strip() for m in raw["applicable_metrics"].replace(";", ",").split(",")}
        if labels != set(base.applicable_metrics) or labels != set(excel[qid].applicable_metrics):
            raise ValueError(f"Applicable metric mismatch: {qid}")
        for key in [
            "truncated",
            "response_complete",
            "finish_reason",
            "output_tokens",
            "max_new_tokens",
            "model_revision",
            "run_id",
            "model_id",
        ]:
            if raw[key] != metadata[qid][key] or raw[key] != excel[qid].model_extra[key]:
                raise ValueError(f"Generation metadata mismatch: {qid}/{key}")
        values = base.model_dump()
        values.update(
            model_variant="gc_llm",
            model_answer=answer,
            dataset_version="gc-as-generated-" + original_hash[:12],
            provenance="Original GC LLM export; answer string unchanged; generation metadata in frozen sidecar",
        )
        case = CalibrationCase.model_validate(values)
        assert case.model_answer == answer
        cases.append(case)
        record = dict(
            metadata[qid],
            answer_sha256=hashlib.sha256(answer.encode("utf8")).hexdigest(),
            answer_characters=len(answer),
            **repetition_indicator(answer),
        )
        provenance.append(record)
    if Counter(m["finish_reason"] for m in provenance) != {"length": 305, "stop": 451}:
        raise ValueError("Unexpected completion distribution; no filtering permitted")
    PROCESSED.mkdir(parents=True, exist_ok=True)
    case_path = PROCESSED / "all_cases.jsonl"
    meta_path = PROCESSED / "generation_analysis_metadata.jsonl"
    save_jsonl(case_path, [c.model_dump() for c in cases])
    save_jsonl(meta_path, provenance)
    stage = PROCESSED / "preparation_draft/experiment.json"
    if PLAN.exists():
        return verify_plan(PLAN)
    draft = prepare_research(
        stage,
        run_id=RUN_ID,
        model="gc_llm",
        cases_path=case_path,
        generations_path=normalized,
        workbook_path=workbook,
    )
    draft["policy_basis"] = (
        "User explicitly requested and authorized the full GC LLM as-generated research evaluation in this chat; separate execution permission is recorded next, not scientific/team approval."
    )
    draft["software_sha256"]["src/canadianness_eval/gc_as_generated.py"] = file_hash(Path(__file__))
    for path in [original_path, sidecar, INCOMING / SOURCE_NAMES[4], meta_path]:
        draft["input_sha256"][str(path.relative_to(ROOT)).replace("\\", "/")] = file_hash(path)
    draft["protected_pilot_sha256"].update(
        {
            str(p.relative_to(ROOT)).replace("\\", "/"): file_hash(p)
            for p in LLAMA.rglob("*")
            if p.is_file() and not p.name.startswith("~$") and p.suffix != ".tmp"
        }
    )
    draft["as_generated_contract"] = dict(
        all_responses_retained=True,
        responses_cleaned=False,
        responses_regenerated=False,
        special_scoring_instructions=False,
        source_jsonl_sha256=file_hash(original_path),
        source_metadata_sidecar=str(meta_path.relative_to(ROOT)).replace("\\", "/"),
        original_provenance_sidecar=str(sidecar.relative_to(ROOT)).replace("\\", "/"),
        truncated_questions=305,
        complete_questions=451,
        truncated_metric_tasks=742,
        complete_metric_tasks=1072,
        source_generation_run_ids=sorted({m["run_id"] for m in provenance}),
        model_revisions=sorted({m["model_revision"] for m in provenance}),
        max_new_tokens=1024,
        repetition_audit_flags_supplied=False,
        derived_repetition_rule="At least 40 Unicode word tokens and >=0.30 repeated 4-gram fraction; analysis only, no exclusions or judge changes",
    )
    draft["missing_generation_metadata"] = (
        "GC revision/run ID, token cap, output tokens and termination flags supplied. Temperature, sampling/decoding settings and prompt template not supplied. Llama generation settings/revision were not supplied; strict generation-condition parity cannot be established."
    )
    old = json.loads(
        (ROOT / "config/research/llama_full_20261106_v2/experiment.json").read_text(encoding="utf8")
    )
    if any(file_hash(ROOT / p) != sha for p, sha in old["software_sha256"].items()):
        raise ValueError("Existing Llama evaluator software changed")
    if (
        draft["judge"] != old["judge"]
        or draft["evaluator_template_sha256"] != old["evaluator_template_sha256"]
        or draft["rubric_sha256"] != old["rubric_sha256"]
    ):
        raise ValueError("GC must use the exact Llama judge/evaluator/rubric configuration")
    exclusive(PLAN, draft)
    exclusive(
        PLAN.parent / "approval_request.json",
        dict(
            status="PENDING_EXECUTION_AUTHORIZATION",
            run_id=RUN_ID,
            experiment_sha256=file_hash(PLAN),
            required_confirmation=confirmation(draft),
            execution_authorized=False,
            scientific_validity_approved=False,
            team_approval=False,
            rubric_empirically_calibrated=False,
        ),
    )
    write_json(
        PROCESSED / "validation_manifest.json",
        dict(
            status="VALID",
            questions=756,
            metric_tasks=1814,
            primary=756,
            secondary=1058,
            language_questions=dict(Counter(c.language for c in cases)),
            source_strings_preserved=756,
            excel_jsonl_normalized_answers_identical=True,
            original_benchmark_evidence_and_applicability_match_llama=True,
            truncated=305,
            complete=451,
            derived_repetition_flags=sum(m["analysis_repetition_flag"] for m in provenance),
            files={
                str(p.relative_to(ROOT)): file_hash(p) for p in INCOMING.iterdir() if p.is_file()
            },
            plan_sha256=file_hash(PLAN),
            repetition_flags_are_exploratory=True,
        ),
    )
    return verify_plan(PLAN)


def analyse():
    plan = verify_plan(PLAN)
    directory = ROOT / plan["run_directory"]
    rows = read_records(directory / "all_results.jsonl")
    metadata = {
        r["question_id"]: r for r in read_records(PROCESSED / "generation_analysis_metadata.jsonl")
    }
    enriched = [
        dict(
            r,
            generation_metadata=metadata[r["question_id"]],
            truncated=metadata[r["question_id"]]["truncated"],
            response_complete=metadata[r["question_id"]]["response_complete"],
            finish_reason=metadata[r["question_id"]]["finish_reason"],
            generation_run_id=metadata[r["question_id"]]["run_id"],
            model_revision=metadata[r["question_id"]]["model_revision"],
            analysis_repetition_flag=metadata[r["question_id"]]["analysis_repetition_flag"],
            repeated_4gram_fraction=metadata[r["question_id"]]["repeated_4gram_fraction"],
        )
        for r in rows
    ]
    table(directory / "as_generated_results", enriched)
    subgroups = []
    for axes in [
        ("truncated",),
        ("response_complete",),
        ("finish_reason",),
        ("analysis_repetition_flag",),
        ("truncated", "analysis_repetition_flag"),
        ("truncated", "language"),
        ("analysis_repetition_flag", "language"),
        ("truncated", "metric_role"),
        ("analysis_repetition_flag", "metric_role"),
    ]:
        groups = defaultdict(list)
        for row in enriched:
            groups[(row["evaluation_metric"], *(row[k] for k in axes))].append(row)
        for key, group in sorted(groups.items()):
            good = [r for r in group if r["status"] == "SUCCESS"]
            subgroups.append(
                dict(
                    evaluation_metric=key[0],
                    grouping="/".join(axes),
                    **dict(zip(axes, key[1:])),
                    task_count=len(group),
                    question_count=len({r["question_id"] for r in group}),
                    successful=len(good),
                    mean=statistics.mean(r["score"] for r in good) if good else None,
                    result_label=LABEL,
                )
            )
    table(directory / "completion_repetition_subgroups", subgroups)
    llama = read_records(LLAMA / "all_results.jsonl")
    indexed = {(r["question_id"], r["evaluation_metric"]): r for r in llama}
    if len(indexed) != 1814 or len(enriched) != 1814:
        raise ValueError("Full matched analysis requires 1814 tasks per model")
    pairs = []
    for r in enriched:
        prior = indexed[r["question_id"], r["evaluation_metric"]]
        for key in [
            "question",
            "reference_answer",
            "context_supporting_summary",
            "primary_metric",
            "metric_role",
            "language",
            "rubric_sha256",
            "evaluator_template_sha256",
        ]:
            if r[key] != prior[key]:
                raise ValueError(f"Cross-model comparison mismatch: {key}")
        pairs.append(
            dict(
                question_id=r["question_id"],
                evaluation_metric=r["evaluation_metric"],
                metric_role=r["metric_role"],
                language=r["language"],
                gc_llm_score=r["score"],
                llama_score=prior["score"],
                gc_minus_llama=r["score"] - prior["score"]
                if r["status"] == prior["status"] == "SUCCESS"
                else None,
                gc_llm_status=r["status"],
                llama_status=prior["status"],
                gc_llm_reason=r["judge_reason"],
                llama_reason=prior["judge_reason"],
                gc_llm_answer=r["model_answer"],
                llama_answer=prior["model_answer"],
                question=r["question"],
                reference_answer=r["reference_answer"],
                context_supporting_summary=r["context_supporting_summary"],
                truncated=r["truncated"],
                response_complete=r["response_complete"],
                analysis_repetition_flag=r["analysis_repetition_flag"],
                generation_metadata=r["generation_metadata"],
                result_label=LABEL,
            )
        )
    table(directory / "gc_llm_vs_llama_question_metric_pairs", pairs)
    paired_summaries = []
    for dims in [
        (),
        ("language",),
        ("metric_role",),
        ("truncated",),
        ("analysis_repetition_flag",),
    ]:
        groups = defaultdict(list)
        for pair in pairs:
            groups[(pair["evaluation_metric"], *(pair[k] for k in dims))].append(pair)
        for key, group in sorted(groups.items()):
            valid = [r for r in group if r["gc_minus_llama"] is not None]
            paired_summaries.append(
                dict(
                    evaluation_metric=key[0],
                    grouping="/".join(dims) or "metric",
                    **dict(zip(dims, key[1:])),
                    pairs=len(valid),
                    gc_llm_mean=statistics.mean(r["gc_llm_score"] for r in valid)
                    if valid
                    else None,
                    llama_mean=statistics.mean(r["llama_score"] for r in valid) if valid else None,
                    mean_paired_difference=statistics.mean(r["gc_minus_llama"] for r in valid)
                    if valid
                    else None,
                    gc_higher=sum(r["gc_minus_llama"] > 0 for r in valid),
                    ties=sum(r["gc_minus_llama"] == 0 for r in valid),
                    gc_lower=sum(r["gc_minus_llama"] < 0 for r in valid),
                    result_label=LABEL,
                )
            )
    table(directory / "gc_llm_vs_llama_metric_comparisons", paired_summaries)
    book = load_workbook(directory / "full_results.xlsx")
    add_sheet(book, "Generation metadata", list(metadata.values()))
    add_sheet(book, "GC original outputs and scores", enriched)
    add_sheet(book, "Completion repetition groups", subgroups)
    add_sheet(book, "GC vs Llama metric pairs", pairs)
    add_sheet(book, "Paired metric comparisons", paired_summaries)
    book.save(directory / "as_generated_comparison.xlsx")
    return enriched, subgroups, paired_summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "analyse"])
    args = parser.parse_args()
    if args.command == "prepare":
        plan = prepare()
        print("Validated as-generated GC run:", plan["run_id"], "tasks:", plan["task_count"])
        print("Manifest SHA256:", file_hash(PLAN))
    else:
        rows, _, _ = analyse()
        print("Analysed", len(rows), "unchanged-output metric results")


if __name__ == "__main__":
    main()
