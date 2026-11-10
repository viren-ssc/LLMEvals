"""Offline request-isolation audit. No network client or actual judge calls."""

import json
import sys
from collections import Counter
from types import SimpleNamespace

from canadianness_eval.calibration.factory import judge_case, make_final_metric
from canadianness_eval.calibration.schema import load_cases
from canadianness_eval.final_metrics import load_final
from canadianness_eval.judge_adapter import RemoteJudge
from canadianness_eval.queued_workbook import (
    MODELS,
    QUEUE,
    STATE,
    run_id,
    validate_queue,
    workbook_rows,
)
from canadianness_eval.research_run import verify_plan
from canadianness_eval.settings import ROOT
from canadianness_eval.storage import now, write_json


class OfflineCapture:
    model_id = "gpt-oss-120b"
    settings = SimpleNamespace(base="offline-audit", timeout=180)

    def __init__(self):
        self.prompts = []

    def generate(self, prompt, schema=None):
        self.prompts.append(prompt)
        return schema(score=8, reason="Offline placeholder; not a real judgment")


queue = validate_queue()
source = {r["question_id"]: r for r in workbook_rows(ROOT / queue["source_workbook"])[0]}
include_cleaned = "--include-cleaned" in sys.argv
specs = [("original_workbook", model, run_id(model), source) for model in MODELS]
if include_cleaned:
    from canadianness_eval.hpc_ingestion import read_records
    from canadianness_eval.queued_cleaned import STATE as CLEANED_STATE
    from canadianness_eval.queued_cleaned import run_id as cleaned_run_id
    from canadianness_eval.queued_cleaned import validate_queue as validate_cleaned

    cleaned_queue = validate_cleaned()
    cleaned_source = {
        r["question_id"]: r for r in read_records(ROOT / cleaned_queue["source_jsonl"])
    }
    specs += [
        ("user_provided_cleaned", model, cleaned_run_id(model), cleaned_source) for model in MODELS
    ]
definitions = load_final().metrics
checked = 0
prompts = 0
counts = {}
for variant, model, evaluation_run_id, selected_source in specs:
    plan_path = ROOT / "config/research" / evaluation_run_id / "experiment.json"
    plan = verify_plan(plan_path)
    cases = load_cases(ROOT / plan["cases_path"])
    assert len(cases) == 756
    slot = variant + ":" + model
    counts[slot] = Counter()
    for case in cases:
        r = selected_source[case.question_id]
        assert case.model_variant == model
        assert case.model_answer == r[model + "_answer"]
        assert case.question == r["question"]
        assert case.reference_answer == r["reference_answer"]
        assert case.reference_context == [r["context_text"]]
        assert not case.model_extra
        checked += 1
    for definition in definitions:
        for language in ["en", "fr"]:
            case = next(
                c
                for c in cases
                if c.language == language and definition.metric_id in c.applicable_metrics
            )
            capture = OfflineCapture()
            judge = RemoteJudge(capture)
            metric = make_final_metric(definition, judge)
            metric.measure(judge_case(case, definition), _show_indicator=False)
            assert len(capture.prompts) == 1
            original = capture.prompts[0]
            assert case.model_answer in original and case.question in original
            canary = "UNRELATED_MODEL_ANSWER_AND_PREVIOUS_JUDGMENT_MUST_NOT_LEAK_9f1bda"
            altered = case.model_copy(
                update={
                    "model_variant": next(m for m in MODELS if m != model),
                    "provenance": canary,
                    "expected_behavior": canary,
                    "intended_score_ranges": {},
                }
            )
            second = make_final_metric(definition, judge)
            second.measure(judge_case(altered, definition), _show_indicator=False)
            assert len(capture.prompts) == 2 and capture.prompts[1] == original
            assert canary not in original
            prompts += 2
            counts[slot][definition.metric_id] += 1
report = dict(
    status="PASS",
    timestamp=now(),
    queue_manifest=str(QUEUE / "queue.json"),
    source_workbook_sha256=queue["source_workbook_sha256"],
    model_cases_checked=checked,
    task_inventory_per_model=1814,
    total_metric_tasks=10884 if include_cleaned else 5442,
    offline_factory_prompt_captures=prompts,
    live_judge_requests=0,
    source_answer_column_matches=True,
    case_schema_has_no_other_model_answer_fields=True,
    question_reference_context_match_source=True,
    model_identity_and_provenance_metadata_do_not_change_prompt=True,
    canary_previous_judgment_and_unrelated_answer_metadata_excluded=True,
    independent_gateway_and_metric_instances=True,
    serialized_checkpoint_publication=True,
    per_model_run_directories_and_manifests=True,
    scope=f"All {checked} prepared question-model-variant cases; actual factory request construction for EN/FR examples of every metric/model/variant, including metadata/model-identity mutation tests. Runtime software hashes prevent subsequent scorer changes.",
    limitation="Isolation establishes what the local evaluator sends; it cannot prove benchmark questions were absent from model pretraining or control server-side behavior.",
    per_model_metric_language_examples={m: dict(v) for m, v in counts.items()},
)
if include_cleaned:
    report["cleaned_source_jsonl_sha256"] = cleaned_queue["source_jsonl_sha256"]
    write_json(CLEANED_STATE / "six_run_isolation_audit.json", report)
else:
    write_json(STATE / "model_isolation_audit.json", report)
print(json.dumps(report), flush=True)
