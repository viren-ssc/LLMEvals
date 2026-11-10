"""Offline intake for user-defined correctness/completeness. No scoring command."""

import argparse
import hashlib
import json
from collections import Counter

from .calibration.schema import load_cases
from .final_metrics import file_hash
from .hpc_ingestion import read_records
from .hpc_workflow import save_jsonl
from .queued_cleaned import validate_queue
from .research_run import LABEL, exclusive
from .settings import ROOT
from .storage import write_json

CONFIG = ROOT / "config/general_answer_quality/v1"
PROCESSED = ROOT / "data/processed/general_answer_quality_cleaned_v1"
METRICS = ["correctness", "completeness"]
MODELS = ["llama", "gc_llm", "apertus"]


def prepare():
    source_queue = validate_queue()
    source = ROOT / source_queue["source_jsonl"]
    rows = read_records(source)
    if len(rows) != 756 or len({r["question_id"] for r in rows}) != 756:
        raise ValueError("Expected exactly 756 unique questions")
    benchmark = {
        c.question_id: c for c in load_cases(ROOT / "data/processed/llama_756_v1/all_cases.jsonl")
    }
    if {r["question_id"] for r in rows} != set(benchmark):
        raise ValueError("Benchmark IDs differ")
    questions = []
    by_model = {m: [] for m in MODELS}
    tasks = []
    for row in rows:
        case = benchmark[row["question_id"]]
        for field in ["question", "reference_answer", "language", "primary_metric"]:
            if row[field] != getattr(case, field):
                raise ValueError("Benchmark differs: " + field)
        if [row["context_text"]] != case.reference_context:
            raise ValueError("Evidence differs")
        if {m.strip() for m in row["applicable_metrics"].split(",")} != set(
            case.applicable_metrics
        ):
            raise ValueError("Original metric assignments differ")
        shared = dict(
            question_id=row["question_id"],
            language=row["language"],
            question=row["question"],
            reference_answer=row["reference_answer"],
            reference_context=[row["context_text"]],
            original_primary_metric=case.primary_metric,
            original_secondary_metrics=case.secondary_metrics,
            source_dataset_sha256=file_hash(source),
            evidence_provenance="Imported benchmark evidence; no new independent verification",
            response_variant="user_provided_cleaned",
        )
        questions.append(shared)
        for model in MODELS:
            answer = row[model + "_answer"]
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("Missing answer")
            answer_sha = hashlib.sha256(answer.encode("utf8")).hexdigest()
            selected = dict(
                shared, evaluated_model=model, model_answer=answer, model_answer_sha256=answer_sha
            )
            # Deliberately excludes all other models' answers, all earlier scores/reasons,
            # and cleaning flags from each independent scoring-case payload.
            if any(name + "_answer" in selected for name in MODELS):
                raise ValueError("Cross-model answer field")
            by_model[model].append(selected)
            for metric in METRICS:
                tasks.append(
                    dict(
                        question_id=row["question_id"],
                        evaluated_model=model,
                        evaluation_metric=metric,
                        language=row["language"],
                        response_variant="user_provided_cleaned",
                        source_answer_sha256=answer_sha,
                        original_primary_metric=case.primary_metric,
                        original_secondary_metrics=case.secondary_metrics,
                        status="NOT_STARTED",
                        result_label=LABEL,
                    )
                )
    assert (
        len(tasks)
        == len({(r["question_id"], r["evaluated_model"], r["evaluation_metric"]) for r in tasks})
        == 4536
    )
    save_jsonl(PROCESSED / "shared_question_evidence.jsonl", questions)
    for model, values in by_model.items():
        save_jsonl(PROCESSED / model / "cases.jsonl", values)
    save_jsonl(PROCESSED / "planned_tasks.jsonl", tasks)
    template = dict(
        protocol_id="general-answer-quality-user-defined-v1",
        status="WAITING_FOR_USER_STEPS_AND_RUBRIC",
        definitions_supplied_by=None,
        shared_among_all_models=True,
        metrics=[dict(metric_id=m, evaluation_steps=None, rubric=None) for m in METRICS],
        dynamic_step_generation_allowed=False,
    )
    definition_path = CONFIG / "metrics_user_supplied.json"
    if not definition_path.exists():
        exclusive(definition_path, template)
    manifest = dict(
        setup_id="general-answer-quality-cleaned-v1",
        status="WAITING_FOR_USER_STEPS_AND_RUBRIC",
        source_jsonl=source.relative_to(ROOT).as_posix(),
        source_jsonl_sha256=file_hash(source),
        cleaned_dataset_unmodified=True,
        questions=756,
        models=MODELS,
        metrics=METRICS,
        tasks_per_model=1512,
        total_metric_tasks=4536,
        language_questions=dict(Counter(r["language"] for r in rows)),
        tasks_per_model_and_metric={m: {metric: 756 for metric in METRICS} for m in MODELS},
        definitions_file=definition_path.relative_to(ROOT).as_posix(),
        shared_definitions_required=True,
        scoring_implementation="Existing DeepEval GEval/fixed-rubric factory and authenticated judge gateway; no new scorer",
        deepeval_version="4.3.2",
        preferred_concurrency=4,
        judge_model="gpt-oss-120b",
        judge_inference_settings_status="Not newly frozen; must be identical across all three models before execution",
        no_answers_regenerated=True,
        no_other_model_answers_or_prior_scores_in_prepared_cases=True,
        original_canadianness_assignments_preserved_as_metadata=True,
        new_metrics_have_no_primary_secondary_role="Both planned for all 756 questions per model; original roles retained only as provenance",
        evaluation_steps_provided=False,
        rubric_provided=False,
        execution_authorized=False,
        execution_guard="No scoring or queue-entry command exists in this setup module; user definitions and explicit execution instruction required before scoring",
        scientific_validity_approved=False,
        team_approval=False,
        rubric_empirically_calibrated=False,
        result_label=LABEL,
        software_sha256={__file__: file_hash(__file__)},
        prepared_input_sha256={
            p.relative_to(ROOT).as_posix(): file_hash(p) for p in PROCESSED.rglob("*.jsonl")
        },
    )
    path = CONFIG / "setup_manifest.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf8")) != manifest:
            raise ValueError("Setup differs; use a new version")
    else:
        exclusive(path, manifest)
    write_json(
        PROCESSED / "validation_manifest.json",
        dict(
            status="INPUT_VALIDATION_PASS",
            questions=756,
            models=3,
            selected_answer_strings_checked=2268,
            unique_metric_tasks=4536,
            source_answers_unchanged=True,
            shared_evidence_matches_benchmark=True,
            cross_model_fields_excluded=True,
            language_questions=dict(Counter(r["language"] for r in rows)),
            scoring_status="BLOCKED_WAITING_FOR_USER_STEPS_AND_RUBRIC",
            judge_requests=0,
        ),
    )
    return manifest


def check():
    manifest = json.loads((CONFIG / "setup_manifest.json").read_text(encoding="utf8"))
    if file_hash(ROOT / manifest["source_jsonl"]) != manifest["source_jsonl_sha256"]:
        raise ValueError("Source changed")
    for p, sha in manifest["prepared_input_sha256"].items():
        if file_hash(ROOT / p) != sha:
            raise ValueError("Prepared input changed: " + p)
    definitions = json.loads((CONFIG / "metrics_user_supplied.json").read_text(encoding="utf8"))
    missing = [
        m["metric_id"]
        for m in definitions["metrics"]
        if not m.get("evaluation_steps") or not m.get("rubric")
    ]
    if missing:
        print(
            "NO-GO: waiting for user-provided evaluation steps and rubric for " + ", ".join(missing)
        )
        return 1
    print(
        "Definitions present. No execution permission granted by this setup; scoring remains disabled."
    )
    return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "check"])
    args = parser.parse_args()
    if args.command == "prepare":
        manifest = prepare()
        print(manifest["status"], manifest["total_metric_tasks"], "planned; zero judge calls")
        return 0
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
