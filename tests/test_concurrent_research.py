import json
import threading
import time

from canadianness_eval import concurrent_research as engine
from canadianness_eval.calibration.evaluate import read_results
from canadianness_eval.calibration.schema import dataset_hash, load_cases
from canadianness_eval.final_metrics import file_hash
from canadianness_eval.hpc_workflow import save_jsonl
from canadianness_eval.settings import ROOT


def test_concurrent_checkpoint_resume_and_payload_isolation(tmp_path, monkeypatch):
    cases = load_cases(ROOT / "data/processed/llama_756_v1/all_cases.jsonl")[:6]
    for case in cases:
        case.model_variant = "apertus"
    case_path = tmp_path / "cases.jsonl"
    save_jsonl(case_path, [c.model_dump() for c in cases])
    plan = json.loads((ROOT / "config/research/llama_full_20261106_v2/experiment.json").read_text())
    plan.update(
        run_id="test-concurrency",
        run_directory=str(tmp_path / "run"),
        evaluated_model="apertus",
        cases_path=str(case_path),
        dataset_hash=dataset_hash(cases),
        execution_engine="concurrent-research-v1",
        software_sha256={},
        input_sha256={str(case_path): file_hash(case_path)},
    )
    plan["tasks"] = [
        dict(t, evaluated_model="apertus")
        for t in plan["tasks"]
        if t["question_id"] in {c.question_id for c in cases}
    ]
    plan["task_count"] = len(plan["tasks"])
    plan["judge"]["concurrency"] = 4
    plan["judge"]["min_seconds_between_task_starts"] = 0
    plan_path, approval = tmp_path / "plan.json", tmp_path / "approval.json"
    plan_path.write_text(json.dumps(plan))
    approval.write_text("{}")
    monkeypatch.setattr(engine, "require_approval", lambda *a: (plan, {}))
    monkeypatch.setattr(engine, "verify_plan", lambda *a: plan)
    state = {"active": 0, "maximum": 0, "calls": 0, "fail_once": True}
    lock = threading.Lock()

    class FakeGateway:
        def __init__(self, settings, **kwargs):
            self.settings = settings
            self.history = []
            self.attempts = 0
            self.model_id = None
            self.auth_failed = False
            self.structured_mode = "json_schema"

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
                fail = state["fail_once"]
                state["fail_once"] = False
            self.attempts += 1
            try:
                time.sleep(0.04)
                self.history.append(
                    dict(
                        status=500 if fail else 200,
                        request_body={
                            "model": self.model_id,
                            "messages": [{"role": "user", "content": prompt}],
                        },
                        raw_response={"usage": {"total_tokens": 10}},
                    )
                )
                if fail:
                    raise RuntimeError("simulated transient server failure")
                return schema(score=8, reason="Concrete rubric-relevant explanation")
            finally:
                with lock:
                    state["active"] -= 1

    monkeypatch.setattr(engine, "Gateway", FakeGateway)
    assert engine.execute(plan_path, approval) == 1
    assert 2 <= state["maximum"] <= 4
    first_calls = state["calls"]
    assert first_calls == plan["task_count"]
    assert engine.execute(plan_path, approval) == 0
    assert state["calls"] == first_calls + 1
    directory = tmp_path / "run"
    latest = read_results(directory)
    assert len(latest) == plan["task_count"]
    assert all(r["status"] == "SUCCESS" for r in latest)
    assert all(r["judge_configuration"]["concurrency"] == 4 for r in latest)
    assert all(r["evaluation_run_id"] == "run" for r in latest)
    # Every raw response belongs to this exact question and metric; no worker history leaks.
    indexed = {c.question_id: c for c in cases}
    for row in latest:
        payload = json.loads((directory / row["raw_output_file"]).read_text(encoding="utf8"))
        assert len(payload["responses"]) == 1
        prompt = payload["responses"][0]["request_body"]["messages"][0]["content"]
        assert indexed[row["question_id"]].question in prompt
        assert indexed[row["question_id"]].model_answer in prompt
    # A third identical execution is a no-op for successful tasks.
    assert engine.execute(plan_path, approval) == 0
    assert state["calls"] == first_calls + 1
    # Reconcile a durable shard checkpoint that was not promoted before interruption.
    victim = next((directory / "records").glob("*.json"))
    victim.unlink()
    assert engine.execute(plan_path, approval) == 0
    assert state["calls"] == first_calls + 1
    assert len(read_results(directory)) == plan["task_count"]
