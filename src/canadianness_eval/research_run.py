"""Explicitly authorized, full-size provisional experiments using the existing evaluator.

This module does not confer scientific approval and never calls freeze-review.
"""

import argparse
import json
import sys
import time
import uuid
from collections import Counter
from pathlib import Path

from .calibration import factory
from .calibration.evaluate import evaluate_calibration, read_results, safe_run_id
from .calibration.schema import dataset_hash, evidence_readiness, load_cases
from .final_metrics import FINAL_JSON, SOURCE_JSON, file_hash, load_final
from .hpc_ingestion import Generation, join_generations, load_benchmark, read_records
from .hpc_workflow import GENERATIONS, PREPARED, RUN, WORKBOOK
from .settings import ROOT, Settings
from .storage import now, versions, write_json
from .verification.db import process_lock

RUN_ID = "llama_full_20261106_v2"
CONFIG_DIR = ROOT / "config/research" / RUN_ID
PLAN = CONFIG_DIR / "experiment.json"
APPROVAL = CONFIG_DIR / "execution_approval.json"
LABEL = "AI-provisional, pending calibration"
RUBRIC_SHA = "bb9889807b7babc8feed6a97ddd0c12c0fa334627e5d295017167fbd0a767cb2"
TEMPLATE_SHA = "ecb714aa746f7bdce82d86fd9bcc288d4e26ffd15cfa210bbd19a356e095793f"
KNOWN_LIMITATIONS = [
    "Booster-seat M3 conditional-guidance credit and M6 extra-detail deductions remain inconsistent.",
    "Optional reference enrichment and scoring-band justification are not consistently handled.",
    "Institutional duty timing versus factual recall and exact within-band scores are human calibration decisions.",
    "Some ancillary factual claims and reference dates remain unverified by the supplied summaries.",
    "Evidence verification is the imported user benchmark attestation, not new local independent verification.",
    "Gateway-default sampling is not proven deterministic; weights/revision and deployment limits are not independently attested.",
    "No human calibration, team approval, overall weighting policy or scientific-validity approval is implied.",
]
CODE_FILES = [
    "src/canadianness_eval/research_run.py",
    "src/canadianness_eval/research_exports.py",
    "src/canadianness_eval/calibration/evaluate.py",
    "src/canadianness_eval/calibration/factory.py",
    "src/canadianness_eval/calibration/schema.py",
    "src/canadianness_eval/api_client.py",
    "src/canadianness_eval/judge_adapter.py",
    "src/canadianness_eval/model_discovery.py",
    "src/canadianness_eval/settings.py",
    "src/canadianness_eval/storage.py",
    "src/canadianness_eval/hpc_ingestion.py",
    "src/canadianness_eval/hpc_workflow.py",
    "src/canadianness_eval/dataset.py",
    "src/canadianness_eval/final_metrics.py",
    "src/canadianness_eval/freeze_metrics.py",
    "src/canadianness_eval/evaluation_runner.py",
    "src/canadianness_eval/verification/db.py",
]


def exclusive(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def relative(path):
    return str(Path(path).resolve().relative_to(ROOT)).replace("\\", "/")


def confirmation(plan):
    return (
        f"I authorize run {plan['run_id']}: {plan['task_count']:,} {plan['evaluated_model']} metric evaluations "
        f"using the locked v2 configuration, labelled {LABEL}. "
        "This is execution permission only, not scientific or team approval."
    )


def prepare(
    plan_path=PLAN,
    *,
    run_id=RUN_ID,
    model="llama",
    cases_path=PREPARED / "all_cases.jsonl",
    generations_path=GENERATIONS,
    workbook_path=WORKBOOK,
):
    safe_run_id(run_id)
    if run_id in {RUN.name, "llama_pilot_20261106_v2"}:
        raise ValueError("A research run cannot reuse a protected pilot run ID")
    existing_manifest = ROOT / "outputs/evaluations" / run_id / "manifest.json"
    if existing_manifest.exists() and not Path(plan_path).exists():
        raise ValueError(
            "Run ID already has results; use its original experiment plan or a new run ID"
        )
    cases = load_cases(cases_path)
    benchmark = load_benchmark(workbook_path, 756)
    generations = [Generation.model_validate(r) for r in read_records(generations_path)]
    joined = join_generations(benchmark, generations, models=(model,))
    if len(generations) != 756 or not all(ready for *_, ready in joined):
        raise ValueError("756 successful nonempty generation records required")
    case_map = {c.question_id: c for c in cases}
    if (
        len(cases) != 756
        or len(case_map) != 756
        or set(case_map) != {r.question_id for r in benchmark}
    ):
        raise ValueError("Prepared cases must match the 756 benchmark question IDs exactly")
    config = load_final()
    definitions = {m.metric_id: m for m in config.metrics}
    tasks = []
    for row, _, generation, _ in joined:
        case = case_map[row.question_id]
        if (
            case.model_variant != model
            or case.model_answer != generation.answer
            or case.question != row.question
            or case.reference_answer != row.reference_answer
            or case.reference_context != [row.context_text]
            or case.language != row.language
            or case.primary_metric != row.primary_metric
            or set(case.applicable_metrics) != set(row.applicable_metrics)
        ):
            raise ValueError(
                f"Prepared text, response, evidence or applicability mismatch: {row.question_id}"
            )
        if model + "_answer" in row.model_extra and row.model_extra[model + "_answer"] is not None:
            if row.model_extra[model + "_answer"] != generation.answer:
                raise ValueError("Excel and normalized model answer differ")
        for mid in case.applicable_metrics:
            if not evidence_readiness(case, definitions[mid])[0]:
                raise ValueError(f"Evidence gate not satisfied: {case.question_id}/{mid}")
            tasks.append(
                dict(
                    question_id=case.question_id,
                    evaluated_model=model,
                    evaluation_metric=mid,
                    primary_metric=case.primary_metric,
                    language=case.language,
                    metric_role="primary" if mid == case.primary_metric else "secondary",
                )
            )
    keys = {(r["question_id"], r["evaluated_model"], r["evaluation_metric"]) for r in tasks}
    if (
        len(tasks) != len(keys)
        or len(keys) != 1814
        or Counter(r["metric_role"] for r in tasks) != {"primary": 756, "secondary": 1058}
    ):
        raise ValueError("Expected exactly 1814 unique tasks: 756 primary and 1058 secondary")
    if Counter(c.language for c in cases) != {"en": 404, "fr": 352}:
        raise ValueError("Expected 404 EN / 352 FR")
    if file_hash(FINAL_JSON) != RUBRIC_SHA or file_hash(SOURCE_JSON) != RUBRIC_SHA:
        raise ValueError("Rubric checksum does not match the user-selected artifact")
    template = factory.template_metadata()
    if (
        template["evaluator_template_sha256"] != TEMPLATE_SHA
        or template["evaluator_template_version"] != "final-json-factory-v2"
    ):
        raise ValueError("Evaluator differs from the explicitly selected v2 configuration")
    settings = Settings.load()
    settings.require_key()
    if settings.model not in ("auto", "gpt-oss-120b"):
        raise ValueError("Configured judge routing must resolve to gpt-oss-120b")
    pilot = ROOT / "outputs/evaluations/llama_pilot_20261106_v2"
    pilot_manifest = json.loads((pilot / "manifest.json").read_text(encoding="utf-8"))
    if (
        settings.base != pilot_manifest["judge_configuration"]["endpoint"]
        or settings.timeout != 180
    ):
        raise ValueError("Endpoint/timeout must match the selected pilot configuration")
    inputs = [
        Path(cases_path),
        Path(generations_path),
        Path(workbook_path),
        FINAL_JSON,
        SOURCE_JSON,
        factory.INTERPRETATION_PATH,
    ]
    protected = {
        relative(p): file_hash(p) for base in (RUN, pilot) for p in base.rglob("*") if p.is_file()
    }
    plan = dict(
        schema_version="provisional-research-run-v1",
        run_id=run_id,
        evaluated_model=model,
        experiment_state="LOCKED_PENDING_EXECUTION_PERMISSION",
        result_label=LABEL,
        scientific_validity_approved=False,
        team_approval=False,
        rubric_empirically_calibrated=False,
        execution_permission_required=True,
        production_release_gate="UNCHANGED: existing load_frozen approval gate",
        policy_basis="User explicitly requested a separately authorized full-size provisional research pathway; does not authorize execution yet.",
        rubric_version=config.version,
        rubric_status=config.status,
        rubric_sha256=RUBRIC_SHA,
        **template,
        judge=dict(
            model="gpt-oss-120b",
            endpoint=settings.base,
            timeout_seconds=180,
            concurrency=1,
            sampling="gateway default; determinism not established",
            logprobs_requested=False,
            min_seconds_between_task_starts=0.25,
            transient_http_attempts=3,
            validation_attempts=3,
            max_http_attempts_per_metric=9,
            retry_after_max_wait_seconds=60,
            stop_after_consecutive_failed_tasks=5,
        ),
        questions=756,
        task_count=1814,
        primary_tasks=756,
        secondary_tasks=1058,
        language_questions=dict(Counter(c.language for c in cases)),
        metric_tasks=dict(sorted(Counter(t["evaluation_metric"] for t in tasks).items())),
        cases_path=relative(cases_path),
        tasks=tasks,
        dataset_hash=dataset_hash(cases),
        input_sha256={relative(p): file_hash(p) for p in inputs},
        software_sha256={p: file_hash(ROOT / p) for p in CODE_FILES},
        package_versions=versions(),
        python_version=sys.version,
        protected_pilot_sha256=protected,
        known_scoring_limitations=KNOWN_LIMITATIONS,
        run_directory=f"outputs/evaluations/{run_id}",
        output_contract=[
            "all/primary/secondary JSONL and CSV",
            "question/reference/context enriched records",
            "per-metric/language/role summaries",
            "Excel workbook",
            "all raw responses and immutable attempt checkpoints",
            "failure/retry/missing reports",
            "API-reported usage with missing-usage accounting",
        ],
        missing_generation_metadata="HPC model checkpoint revision, prompt template and inference settings were not supplied; not invented.",
    )
    plan_path = Path(plan_path)
    if plan_path.exists():
        if json.loads(plan_path.read_text(encoding="utf-8")) != plan:
            raise ValueError(
                "Locked experiment differs; preserve it and choose a new research plan/run ID"
            )
    else:
        exclusive(plan_path, plan)
    request = dict(
        status="PENDING_EXECUTION_AUTHORIZATION",
        experiment_sha256=file_hash(plan_path),
        run_id=run_id,
        authorized_by=None,
        authorized_at=None,
        execution_authorized=False,
        scientific_validity_approved=False,
        team_approval=False,
        rubric_empirically_calibrated=False,
        required_confirmation=confirmation(plan),
        scope="One complete experiment plus same-configuration missing/failed-task resumption",
        result_label=LABEL,
        known_limitations=KNOWN_LIMITATIONS,
    )
    request_path = plan_path.parent / "approval_request.json"
    if not request_path.exists():
        exclusive(request_path, request)
    return plan


def verify_plan(plan_path=PLAN, *, pilots=True):
    plan_path = Path(plan_path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    safe_run_id(plan["run_id"])
    if plan["run_directory"] != f"outputs/evaluations/{plan['run_id']}" or plan["run_id"] in {
        RUN.name,
        "llama_pilot_20261106_v2",
    }:
        raise ValueError("Research directory must be isolated from protected pilot results")
    if any(
        plan.get(k) is not False
        for k in ("scientific_validity_approved", "team_approval", "rubric_empirically_calibrated")
    ):
        raise ValueError("Provisional execution does not grant scientific or team approval")
    if (
        plan["rubric_sha256"] != RUBRIC_SHA
        or plan["evaluator_template_sha256"] != TEMPLATE_SHA
        or factory.template_metadata()["evaluator_template_sha256"] != TEMPLATE_SHA
    ):
        raise ValueError("Pinned rubric/evaluator identity mismatch")
    for group in ("input_sha256", "software_sha256"):
        for path, expected in plan[group].items():
            if file_hash(ROOT / path) != expected:
                raise ValueError(f"Locked experiment file changed: {path}")
    if versions() != plan["package_versions"]:
        raise ValueError("Package versions changed")
    if sys.version != plan["python_version"]:
        raise ValueError("Python version changed")
    if pilots:
        for path, expected in plan["protected_pilot_sha256"].items():
            if file_hash(ROOT / path) != expected:
                raise ValueError(f"Protected pilot artifact changed: {path}")
    cases = load_cases(ROOT / plan["cases_path"])
    if dataset_hash(cases) != plan["dataset_hash"]:
        raise ValueError("Dataset changed")
    if (
        plan["task_count"] != len(plan["tasks"])
        or len(
            {
                (r["question_id"], r["evaluated_model"], r["evaluation_metric"])
                for r in plan["tasks"]
            }
        )
        != plan["task_count"]
    ):
        raise ValueError("Invalid task inventory")
    expected = {
        (c.question_id, c.model_variant, mid): (
            c.primary_metric,
            c.language,
            "primary" if mid == c.primary_metric else "secondary",
        )
        for c in cases
        for mid in c.applicable_metrics
    }
    actual = {
        (r["question_id"], r["evaluated_model"], r["evaluation_metric"]): (
            r["primary_metric"],
            r["language"],
            r["metric_role"],
        )
        for r in plan["tasks"]
    }
    if (
        expected != actual
        or len(expected) != 1814
        or len(cases) != 756
        or any(c.model_variant != plan["evaluated_model"] for c in cases)
    ):
        raise ValueError("Locked task assignments differ from the complete model dataset")
    return plan


def authorize(plan_path, approval_path, *, approved_by, statement):
    plan = verify_plan(plan_path)
    if not approved_by.strip() or statement != confirmation(plan):
        raise ValueError("Explicit execution-only confirmation and authorizer identity required")
    approval = dict(
        status="EXECUTION_AUTHORIZED",
        execution_authorized=True,
        authorized_by=approved_by,
        authorized_at=now(),
        authorization_statement=statement,
        experiment_sha256=file_hash(plan_path),
        run_id=plan["run_id"],
        scope="One complete provisional experiment plus identical-configuration missing/failed-task resumption",
        scientific_validity_approved=False,
        team_approval=False,
        rubric_empirically_calibrated=False,
        result_label=LABEL,
    )
    exclusive(approval_path, approval)
    return approval


def require_approval(plan_path, approval_path):
    plan = verify_plan(plan_path)
    path = Path(approval_path)
    if not path.exists():
        raise ValueError(
            "NO-GO: explicit provisional execution permission is missing; see approval_request.json"
        )
    approval = json.loads(path.read_text(encoding="utf-8"))
    if (
        approval.get("status") != "EXECUTION_AUTHORIZED"
        or approval.get("execution_authorized") is not True
        or approval.get("experiment_sha256") != file_hash(plan_path)
        or approval.get("run_id") != plan["run_id"]
        or not approval.get("authorized_by")
        or not approval.get("authorized_at")
        or approval.get("authorization_statement") != confirmation(plan)
        or any(
            approval.get(k) is not False
            for k in (
                "scientific_validity_approved",
                "team_approval",
                "rubric_empirically_calibrated",
            )
        )
    ):
        raise ValueError("NO-GO: execution record is incomplete, changed or for another experiment")
    return plan, approval


def execute(plan_path=PLAN, approval_path=APPROVAL, *, resume=True, retry_failures=True):
    # Authorization, full input/software verification and exclusive lock precede any network request.
    plan, approval = require_approval(plan_path, approval_path)
    from .api_client import Gateway
    from .judge_adapter import RemoteJudge
    from .research_exports import export_research_results

    directory = ROOT / plan["run_directory"]
    directory.mkdir(parents=True, exist_ok=True)
    with process_lock(directory / "run.lock"):
        plan, approval = require_approval(plan_path, approval_path)
        existing = directory / "manifest.json"
        if existing.exists():
            prior = json.loads(existing.read_text(encoding="utf-8")).get("run_metadata", {})
            if prior.get("experiment_sha256") != file_hash(plan_path) or prior.get(
                "execution_approval_sha256"
            ) != file_hash(approval_path):
                raise ValueError("Existing results belong to another experiment or authorization")
        settings = Settings.load()
        if (
            settings.base != plan["judge"]["endpoint"]
            or settings.timeout != plan["judge"]["timeout_seconds"]
            or settings.model not in ("auto", plan["judge"]["model"])
        ):
            raise ValueError("Configured endpoint/model/timeout differs from locked experiment")
        session = uuid.uuid4().hex
        metadata = dict(
            phase="FULL_PROVISIONAL_RESEARCH",
            experiment_sha256=file_hash(plan_path),
            execution_approval_sha256=file_hash(approval_path),
            result_label=LABEL,
            scientific_validity_approved=False,
            team_approval=False,
            rubric_empirically_calibrated=False,
            known_scoring_limitations=plan["known_scoring_limitations"],
            model=plan["evaluated_model"],
        )
        gateway = Gateway(settings)
        started = now()
        last_start = 0
        consecutive = 0
        completed = 0
        input_stats = {
            p: ((ROOT / p).stat().st_size, (ROOT / p).stat().st_mtime_ns)
            for p in plan["input_sha256"]
        }

        def guard():
            nonlocal last_start
            if gateway.model_id != plan["judge"]["model"]:
                raise ValueError("Judge identity changed")
            for p, expected in plan["software_sha256"].items():
                if file_hash(ROOT / p) != expected:
                    raise ValueError(f"Execution software changed: {p}")
            for p, expected in input_stats.items():
                info = (ROOT / p).stat()
                if (info.st_size, info.st_mtime_ns) != expected:
                    raise ValueError(f"Input/configuration changed during execution: {p}")
            if (
                file_hash(plan_path) != metadata["experiment_sha256"]
                or file_hash(approval_path) != metadata["execution_approval_sha256"]
            ):
                raise ValueError("Experiment or authorization changed during execution")
            delay = plan["judge"]["min_seconds_between_task_starts"] - (
                time.monotonic() - last_start
            )
            if delay > 0:
                time.sleep(delay)
            last_start = time.monotonic()

        def checkpoint(row):
            nonlocal consecutive, completed
            completed += 1
            consecutive = consecutive + 1 if row["status"] == "FAILED" else 0
            gateway.history.clear()  # Raw events and the metric checkpoint are already published.
            write_json(
                directory / "progress.json",
                dict(
                    run_id=plan["run_id"],
                    session=session,
                    completed_this_session=completed,
                    last_question_id=row["question_id"],
                    last_metric=row["metric_id"],
                    last_status=row["status"],
                    timestamp=now(),
                    result_label=LABEL,
                ),
            )
            if (
                gateway.auth_failed
                or (row.get("error") and "Rate limit requests" in row["error"])
                or (row.get("error") and "HTTP 429" in row["error"])
            ):
                raise RuntimeError(
                    "Execution stopped after checkpoint: authentication or sustained rate-limit failure"
                )
            if consecutive >= plan["judge"]["stop_after_consecutive_failed_tasks"]:
                raise RuntimeError(
                    "Execution stopped after checkpoint: consecutive failure limit reached"
                )

        outcome = "INTERRUPTED"
        failure = None
        try:
            gateway.discover()
            if gateway.model_id != plan["judge"]["model"]:
                raise ValueError("Discovery did not resolve the pinned judge")
            write_json(directory / "sessions" / f"{session}_discovery.json", gateway.history)
            gateway.history.clear()
            evaluate_calibration(
                ROOT / plan["cases_path"],
                RemoteJudge(gateway),
                directory,
                config_path=FINAL_JSON,
                repeats=1,
                resume=resume,
                retry_failures=retry_failures,
                run_metadata=metadata,
                execution_guard=guard,
                checkpoint_callback=checkpoint,
            )
            outcome = "COMPLETED_ENGINE_PASS"
        except KeyboardInterrupt:
            failure = (
                "KeyboardInterrupt: resume only missing/failed tasks with the same configuration"
            )
        except Exception as exc:
            failure = gateway.safe_error(exc)
            outcome = "STOPPED_WITH_ERROR"
        finally:
            if gateway.history:
                write_json(
                    directory / "sessions" / f"{session}_uncheckpointed_events.json",
                    gateway.history,
                )
            write_json(
                directory / "sessions" / f"{session}.json",
                dict(
                    started=started,
                    ended=now(),
                    outcome=outcome,
                    error=failure,
                    http_attempts=gateway.attempts,
                    completed_this_session=completed,
                    approval_sha256=metadata["execution_approval_sha256"],
                    result_label=LABEL,
                ),
            )
            gateway.close()
            export_research_results(directory, plan)
        verify_plan(plan_path)
        rows = [r for r in read_results(directory) if r["applicable"]]
        successes = sum(r["status"] == "SUCCESS" for r in rows)
        return 0 if successes == plan["task_count"] and outcome == "COMPLETED_ENGINE_PASS" else 1


def show_status(plan_path=PLAN, approval_path=APPROVAL):
    """Read-only filesystem monitor: no gateway construction, authorization or writes."""
    plan_path = Path(plan_path)
    if not plan_path.exists():
        print(
            f"{now()} NOT STARTED: full-run setup is being prepared; execution permission pending.",
            flush=True,
        )
        return
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    directory = ROOT / plan["run_directory"]
    rows = [r for r in read_results(directory) if r["applicable"]]
    succeeded = sum(r["status"] == "SUCCESS" for r in rows)
    failed = sum(r["status"] != "SUCCESS" for r in rows)
    remaining = plan["task_count"] - len(rows)
    permission = "recorded" if Path(approval_path).exists() else "PENDING"
    progress_path = directory / "progress.json"
    last = json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.exists() else {}
    print(
        f"{now()} {plan['run_id']} | successful {succeeded}/{plan['task_count']} | "
        f"failed/skipped {failed} | pending {remaining} | execution permission {permission} | "
        f"last {last.get('last_question_id', '-')} {last.get('last_metric', '')}",
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["prepare", "check", "authorize", "run", "report", "status", "watch"]
    )
    parser.add_argument("--plan", default=str(PLAN))
    parser.add_argument("--approval", default=str(APPROVAL))
    parser.add_argument("--approved-by")
    parser.add_argument("--statement")
    parser.add_argument("--run-id", default=RUN_ID)
    parser.add_argument("--model", default="llama", choices=["llama", "gc_llm", "apertus"])
    parser.add_argument("--cases", default=str(PREPARED / "all_cases.jsonl"))
    parser.add_argument("--generations", default=str(GENERATIONS))
    args = parser.parse_args()
    if args.command in ("status", "watch"):
        try:
            while True:
                show_status(args.plan, args.approval)
                if args.command == "status":
                    return 0
                time.sleep(5)
        except KeyboardInterrupt:
            return 0
    if args.command == "prepare":
        plan = prepare(
            args.plan,
            run_id=args.run_id,
            model=args.model,
            cases_path=args.cases,
            generations_path=args.generations,
        )
        print("Prepared locked experiment; NO-GO until explicit execution authorization.")
        print(confirmation(plan))
        return 0
    if args.command == "check":
        plan = verify_plan(args.plan)
        try:
            require_approval(args.plan, args.approval)
        except ValueError as exc:
            print(str(exc))
            return 1
        print("GO: explicit execution authorization exists for the locked provisional experiment.")
        return 0
    if args.command == "authorize":
        if not args.approved_by or not args.statement:
            parser.error(
                "--approved-by and --statement are required; use only after actual user authorization"
            )
        authorize(args.plan, args.approval, approved_by=args.approved_by, statement=args.statement)
        print("Execution permission recorded; scientific and team approval remain false.")
        return 0
    if args.command == "report":
        from .research_exports import export_research_results

        plan = verify_plan(args.plan)
        export_research_results(ROOT / plan["run_directory"], plan)
        return 0
    return execute(args.plan, args.approval)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from None
