import json

import httpx
import pytest
from openpyxl import load_workbook
from test_hpc_workflow import cases

from canadianness_eval import api_client, research_exports, research_run
from canadianness_eval.api_client import Gateway, GatewayError
from canadianness_eval.final_metrics import file_hash
from canadianness_eval.hpc_workflow import save_jsonl
from canadianness_eval.settings import Settings
from canadianness_eval.storage import write_json


def test_real_workload_locks_without_authorizing(tmp_path, monkeypatch):
    plan_path = tmp_path / "experiment.json"
    plan = research_run.prepare(plan_path, run_id="test_only_not_authorized")
    assert (
        plan["task_count"] == 1814
        and plan["primary_tasks"] == 756
        and plan["secondary_tasks"] == 1058
    )
    assert plan["evaluator_template_sha256"] == research_run.TEMPLATE_SHA
    assert not plan["scientific_validity_approved"]
    request = json.loads((tmp_path / "approval_request.json").read_text(encoding="utf8"))
    assert request["execution_authorized"] is False
    approval_path = tmp_path / "execution_approval.json"
    monkeypatch.setattr(
        api_client,
        "Gateway",
        lambda *_: pytest.fail("Network client must not be constructed without approval"),
    )
    with pytest.raises(ValueError, match="NO-GO"):
        research_run.execute(plan_path, approval_path)
    # Only a temporary test attestation; never a real experiment approval.
    research_run.authorize(
        plan_path,
        approval_path,
        approved_by="SYNTHETIC PYTEST ONLY",
        statement=research_run.confirmation(plan),
    )
    _, approval = research_run.require_approval(plan_path, approval_path)
    assert approval["scientific_validity_approved"] is False and approval["team_approval"] is False
    altered = dict(plan, task_count=1)
    write_json(plan_path, altered)
    with pytest.raises(ValueError):
        research_run.require_approval(plan_path, approval_path)


def test_retry_after_is_respected_and_bounded(gateway_factory):
    statuses = iter([429, 200])
    delays = []
    gateway = gateway_factory(
        lambda _: httpx.Response(next(statuses), headers={"Retry-After": "4"})
    )
    gateway.sleep = delays.append
    assert gateway.request("GET", "models").status_code == 200
    assert delays == [4]
    assert gateway.history[0]["retry_delay_seconds"] == 4
    gateway = gateway_factory(lambda _: httpx.Response(429, headers={"Retry-After": "120"}))
    gateway.sleep = lambda _: pytest.fail("Long server delay should checkpoint and stop, not block")
    with pytest.raises(GatewayError, match="checkpoint"):
        gateway.request("GET", "models")
    assert gateway.attempts == 1


def tiny_plan(tmp_path, monkeypatch):
    examples = cases()[2:4]
    examples[0].secondary_metrics = ["M6"]
    examples[0].applicable_metrics = ["M3", "M6"]
    examples[0].evidence_review.sufficient_for_metrics = ["M3", "M6"]
    data = tmp_path / "cases.jsonl"
    save_jsonl(data, [c.model_dump() for c in examples])
    tasks = [
        dict(
            question_id=c.question_id,
            evaluated_model="llama",
            evaluation_metric=m,
            primary_metric=c.primary_metric,
            language=c.language,
            metric_role="primary" if m == c.primary_metric else "secondary",
        )
        for c in examples
        for m in c.applicable_metrics
    ]
    plan = dict(
        run_id="test_tiny",
        run_directory="results",
        evaluated_model="llama",
        task_count=3,
        cases_path="cases.jsonl",
        tasks=tasks,
        input_sha256={"cases.jsonl": file_hash(data)},
        software_sha256={},
        judge=dict(
            model="gpt-oss-120b",
            endpoint="https://example.com/v1",
            timeout_seconds=180,
            min_seconds_between_task_starts=0,
            stop_after_consecutive_failed_tasks=5,
        ),
        rubric_version="test-only",
        rubric_sha256=research_run.RUBRIC_SHA,
        evaluator_template_version="final-json-factory-v2",
        evaluator_template_sha256=research_run.TEMPLATE_SHA,
        known_scoring_limitations=["synthetic fixture"],
    )
    plan_path = tmp_path / "experiment.json"
    write_json(plan_path, plan)
    approval_path = tmp_path / "approval.json"
    write_json(
        approval_path,
        dict(
            status="EXECUTION_AUTHORIZED",
            execution_authorized=True,
            experiment_sha256=file_hash(plan_path),
            run_id=plan["run_id"],
            authorized_by="SYNTHETIC TEST ONLY",
            authorized_at="test",
            authorization_statement=research_run.confirmation(plan),
            scientific_validity_approved=False,
            team_approval=False,
            rubric_empirically_calibrated=False,
        ),
    )
    monkeypatch.setattr(research_run, "ROOT", tmp_path)
    monkeypatch.setattr(research_exports, "ROOT", tmp_path)
    monkeypatch.setattr(research_run, "verify_plan", lambda *a, **k: plan)
    monkeypatch.setattr(
        Settings,
        "load",
        classmethod(
            lambda cls, *a, **k: Settings(key="test-secret", base="https://example.com/v1")
        ),
    )
    return plan_path, approval_path


def test_research_execution_retry_resume_and_exports(tmp_path, monkeypatch):
    plan_path, approval_path = tiny_plan(tmp_path, monkeypatch)
    available = False
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "gpt-oss-120b"}]})
        if not available:
            return httpx.Response(503)
        return httpx.Response(
            200,
            json={
                "model": "gpt-oss-120b",
                "choices": [
                    {"message": {"content": '{"score":8,"reason":"Specific fixture reason"}'}}
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            },
        )

    monkeypatch.setattr(
        api_client,
        "Gateway",
        lambda s: Gateway(s, transport=httpx.MockTransport(handler), sleep=lambda _: None),
    )
    assert research_run.execute(plan_path, approval_path) == 1
    first = json.loads((tmp_path / "results/full_run_summary.json").read_text(encoding="utf8"))
    assert first["successful"] == 0 and first["failed_or_skipped"] == 3
    available = True
    assert research_run.execute(plan_path, approval_path) == 0
    completed_calls = len(calls)
    assert research_run.execute(plan_path, approval_path) == 0
    assert len(calls) == completed_calls + 1  # Discovery only; no duplicated scoring requests.
    report = json.loads((tmp_path / "results/full_run_summary.json").read_text(encoding="utf8"))
    assert report["successful"] == 3 and report["missing"] == 0
    assert report["api_reported_tokens"]["total_tokens"] == 360
    assert report["scoring_http_attempts"] == 12  # 9 failed HTTP attempts plus 3 successes.
    rows = [
        json.loads(s)
        for s in (tmp_path / "results/all_results.jsonl").read_text(encoding="utf8").splitlines()
    ]
    assert len(rows) == 3 and all(r["judge_reason"] and r["completion_timestamp"] for r in rows)
    assert all(
        r["result_label"] == research_run.LABEL and r["model_answer"] and r["reference_answer"]
        for r in rows
    )
    book = load_workbook(tmp_path / "results/full_results.xlsx", read_only=True)
    assert book["All metric scores"].max_row == 4
    assert book["Primary only"].max_row == 3 and book["Secondary only"].max_row == 2
    book.close()


def test_interruption_saves_current_metric_and_resumes_only_missing(tmp_path, monkeypatch):
    plan_path, approval_path = tiny_plan(tmp_path, monkeypatch)
    count = 0
    interrupted = False

    def handler(request):
        nonlocal count, interrupted
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "gpt-oss-120b"}]})
        count += 1
        if count == 2 and not interrupted:
            interrupted = True
            raise KeyboardInterrupt()
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"score":9,"reason":"Recovered fixture"}'}}]
            },
        )

    monkeypatch.setattr(
        api_client,
        "Gateway",
        lambda s: Gateway(s, transport=httpx.MockTransport(handler), sleep=lambda _: None),
    )
    assert research_run.execute(plan_path, approval_path) == 1
    summary = json.loads((tmp_path / "results/full_run_summary.json").read_text(encoding="utf8"))
    assert summary["successful"] == 1 and summary["missing"] == 2
    records = list((tmp_path / "results/records").glob("*.json"))
    preserved = {p.name: p.read_bytes() for p in records}
    assert research_run.execute(plan_path, approval_path) == 0
    assert all(
        (tmp_path / "results/records" / name).read_bytes() == content
        for name, content in preserved.items()
    )
    assert count == 4  # One successful task, interrupted in-flight task, two missing-task calls.


def test_monitor_never_constructs_gateway(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        api_client, "Gateway", lambda *_: pytest.fail("Read-only monitor contacted judge")
    )
    research_run.show_status(tmp_path / "missing.json", tmp_path / "approval.json")
    assert "NOT STARTED" in capsys.readouterr().out


def test_execution_detects_software_drift_before_next_metric(tmp_path, monkeypatch):
    plan_path, approval_path = tiny_plan(tmp_path, monkeypatch)
    locked = tmp_path / "locked_component.py"
    locked.write_text("original", encoding="utf8")
    plan = research_run.verify_plan(plan_path)
    plan["software_sha256"] = {"locked_component.py": file_hash(locked)}
    write_json(plan_path, plan)
    approval = json.loads(approval_path.read_text(encoding="utf8"))
    approval["experiment_sha256"] = file_hash(plan_path)
    write_json(approval_path, approval)
    count = 0

    def handler(request):
        nonlocal count
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "gpt-oss-120b"}]})
        count += 1
        if count == 1:
            locked.write_text("changed", encoding="utf8")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"score":8,"reason":"Specific fixture"}'}}]},
        )

    monkeypatch.setattr(
        api_client,
        "Gateway",
        lambda s: Gateway(s, transport=httpx.MockTransport(handler), sleep=lambda _: None),
    )
    assert research_run.execute(plan_path, approval_path) == 1
    assert count == 1
    summary = json.loads((tmp_path / "results/full_run_summary.json").read_text(encoding="utf8"))
    assert summary["successful"] == 1 and summary["missing"] == 2
    locked.write_text("original", encoding="utf8")
    assert research_run.execute(plan_path, approval_path) == 0
    assert count == 3
