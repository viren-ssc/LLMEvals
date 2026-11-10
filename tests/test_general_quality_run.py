import json
import threading
import time

import pytest

from canadianness_eval import general_quality_run as engine
from canadianness_eval.calibration.evaluate import read_results
from canadianness_eval.final_metrics import file_hash
from canadianness_eval.hpc_workflow import save_jsonl


def test_source_extraction_is_exact_and_complete():
    parsed = engine.extract_definitions()
    text = engine.SOURCE.read_text(encoding="utf8")
    assert [m["metric_id"] for m in parsed["metrics"]] == ["correctness", "completeness"]
    for metric in parsed["metrics"]:
        assert len(metric["evaluation_steps"]) == 6
        assert len(metric["rubric_0_to_10"]) == 5
        for step in metric["evaluation_steps"]:
            assert step in text
        for band in metric["rubric_0_to_10"]:
            assert band["expected_outcome"] in text
    assert parsed["common_scoring_rules"] in text
    assert parsed["source_markdown_sha256"] == file_hash(engine.SOURCE)


def test_native_factory_checkpoint_resume_and_model_isolation(tmp_path, monkeypatch):
    definitions = engine.extract_definitions()
    cases = []
    for n in range(4):
        cases.append(
            dict(
                question_id=f"Q{n}",
                evaluated_model="llama",
                language="en" if n % 2 else "fr",
                question=f"Question {n}: what is the required factual answer?",
                model_answer=f"SELECTED_ANSWER_{n}",
                reference_answer=f"REFERENCE_{n}",
                reference_context=[f"EVIDENCE_{n}"],
                original_primary_metric="M7",
                original_secondary_metrics=[],
            )
        )
    prepared = tmp_path / "prepared"
    save_jsonl(prepared / "llama/cases.jsonl", cases)
    (tmp_path / "definitions.json").write_text(json.dumps(definitions), encoding="utf8")
    plan = dict(
        metrics_path="definitions.json",
        metric_ids=["correctness", "completeness"],
        extracted_definition_sha256="fixture",
        source_markdown_sha256="fixture",
        evidence_provenance="Offline fixture",
        judge=dict(
            endpoint=engine.Settings.load().base,
            timeout_seconds=engine.Settings.load().timeout,
            model="gpt-oss-120b",
            concurrency=4,
            min_seconds_between_task_starts=0,
        ),
        input_sha256={},
        software_sha256={},
    )
    monkeypatch.setattr(engine, "ROOT", tmp_path)
    monkeypatch.setattr(engine, "PROCESSED", prepared)
    monkeypatch.setattr(engine, "PLAN", tmp_path / "plan.json")
    monkeypatch.setattr(engine, "APPROVAL", tmp_path / "approval.json")
    engine.PLAN.write_text("{}")
    engine.APPROVAL.write_text("{}")
    monkeypatch.setattr(engine, "verify", lambda: plan)
    lock = threading.Lock()
    state = dict(calls=0, active=0, maximum=0, fail=True)

    class FakeGateway:
        def __init__(self, settings, **kwargs):
            self.settings = settings
            self.model_id = None
            self.history = []
            self.attempts = 0
            self.auth_failed = False

        def discover(self):
            self.model_id = "gpt-oss-120b"

        def close(self):
            pass

        def safe_error(self, exc):
            return str(exc)

        def generate(self, prompt, schema=None):
            with lock:
                state["calls"] += 1
                state["active"] += 1
                state["maximum"] = max(state["maximum"], state["active"])
                fail = state["fail"]
                state["fail"] = False
            self.attempts += 1
            try:
                time.sleep(0.04)
                payload = dict(
                    score=8,
                    reason="Concrete metric-specific fixture explanation",
                    evidence_review_required=True,
                    evidence_review_notes=["Fixture evidence ambiguity"],
                )
                self.history.append(
                    dict(
                        status=500 if fail else 200,
                        request_body=dict(
                            model="gpt-oss-120b", messages=[dict(role="user", content=prompt)]
                        ),
                        raw_response=dict(
                            choices=[dict(message=dict(content=json.dumps(payload)))],
                            usage=dict(total_tokens=10),
                        ),
                    )
                )
                if fail:
                    raise RuntimeError("simulated server failure")
                assert set(schema.model_fields) == {
                    "score",
                    "reason",
                    "evidence_review_required",
                    "evidence_review_notes",
                }
                return schema(**payload)
            finally:
                with lock:
                    state["active"] -= 1

    monkeypatch.setattr(engine, "Gateway", FakeGateway)
    assert engine.execute("llama") == 1
    assert state["calls"] == 8 and 2 <= state["maximum"] <= 4
    assert engine.execute("llama") == 0
    assert state["calls"] == 9
    directory = tmp_path / "outputs/evaluations" / engine.run_id("llama")
    rows = read_results(directory)
    assert len(rows) == 8 and all(
        r["status"] == "SUCCESS" and r["score"] == 0.8 and r["raw_rubric_score"] == 8 for r in rows
    )
    for row in rows:
        raw = json.loads((directory / row["raw_output_file"]).read_text(encoding="utf8"))
        assert len(raw["responses"]) == 1
        prompt = raw["responses"][0]["request_body"]["messages"][0]["content"]
        n = int(row["question_id"][1:])
        assert f"SELECTED_ANSWER_{n}" in prompt
        assert f"REFERENCE_{n}" in prompt and f"EVIDENCE_{n}" in prompt
        assert "OTHER_MODEL_ANSWER" not in prompt
        definition = next(d for d in definitions["metrics"] if d["metric_id"] == row["metric_id"])
        assert all(step in prompt for step in definition["evaluation_steps"])
        assert all(b["expected_outcome"] in prompt for b in definition["rubric_0_to_10"])
        assert definitions["common_scoring_rules"] in prompt
        assert row["evidence_review_required"] and row["evidence_review_notes"] == [
            "Fixture evidence ambiguity"
        ]
    assert engine.execute("llama") == 0 and state["calls"] == 9


def test_dynamic_step_generation_is_rejected():
    from pydantic import BaseModel

    class Steps(BaseModel):
        steps: list[str]

    gateway = type("NoNetwork", (), {"model_id": "gpt-oss-120b"})()
    judge = engine.EvidenceJudge(gateway)
    with pytest.raises(ValueError, match="dynamic step generation prohibited"):
        judge.generate("Generate new steps", Steps)
