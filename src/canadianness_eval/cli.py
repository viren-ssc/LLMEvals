import argparse
import json
import sys
import time
from pathlib import Path

from pydantic import BaseModel

from .settings import ROOT, Settings
from .storage import digest, now, versions, write_json


class Smoke(BaseModel):
    answer: str


def connect(settings, report_path=None):
    from .api_client import Gateway

    gateway = Gateway(settings)
    try:
        print("Connecting to LLM gateway...", flush=True)
        ids = gateway.discover()
        print("Accessible models: " + ", ".join(ids), flush=True)
        print("Selected judge: " + gateway.model_id, flush=True)
        start = time.perf_counter()
        reply = gateway.generate("What is the capital city of Manitoba, Canada? Answer briefly.")
        if "winnipeg" not in reply.lower():
            raise ValueError("Connection responded, but the Winnipeg factual smoke check failed")
        structured = gateway.generate(
            "Return the capital city of Manitoba in the answer field.", Smoke
        )
        if "winnipeg" not in structured.answer.lower():
            raise ValueError("Structured smoke check returned an unexpected answer")
        report = dict(
            status="success",
            model_id=gateway.model_id,
            accessible_models=ids,
            latency_seconds=time.perf_counter() - start,
            structured_mode=gateway.structured_mode,
            timestamp=now(),
            package_versions=versions(),
        )
        write_json(report_path or ROOT / "outputs/connection_check.json", report)
        print(
            f"Connection and structured smoke checks successful ({gateway.structured_mode})",
            flush=True,
        )
        return gateway
    except Exception:
        gateway.close()
        raise


def prepare(args):
    from .consolidate_steps import consolidate
    from .metric_definitions import load_metrics
    from .review_workbook import create_workbook
    from .rubric_builder import load_rubrics

    metrics, rubrics = load_metrics(), load_rubrics()
    workbook = Path(args.workbook)
    if workbook.exists():
        raise ValueError(
            "Workbook exists; use --workbook with a new path to protect reviewer edits"
        )
    records = []
    if not args.offline:
        from .generate_steps import generate_all
        from .judge_adapter import RemoteJudge

        settings = Settings.load()
        gateway = connect(settings)
        try:
            records = generate_all(
                metrics,
                RemoteJudge(gateway),
                ROOT / "outputs/generations",
                args.runs or settings.runs,
                args.force,
            )
        finally:
            gateway.close()
    else:
        for path in sorted((ROOT / "outputs/generations").glob("M*/run_*.json")):
            records.append(json.loads(path.read_text(encoding="utf-8")))
    candidates, coverage = consolidate(records, metrics)
    output = ROOT / "outputs/consolidated"
    output.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(output / "step_candidates.csv", index=False, encoding="utf-8-sig")
    coverage.to_csv(output / "metric_coverage.csv", index=False, encoding="utf-8-sig")
    report = dict(
        status="DRAFT: awaiting human review",
        timestamp=now(),
        offline=args.offline,
        metrics=7,
        metric_definitions_hash=digest(metrics),
        expected_runs=7 * (args.runs or Settings.load().runs),
        recorded_runs=len(records),
        total_generation_http_attempts=sum(r.get("attempt_count", 0) for r in records),
        successful=sum(r["status"] == "success" for r in records),
        failed=sum(r["status"] != "success" for r in records),
        candidate_steps=len(candidates),
        workbook=str(workbook),
        package_versions=versions(),
    )
    create_workbook(workbook, candidates, coverage, rubrics, report)
    write_json(output / "preparation_report.json", report)
    print(json.dumps(report, indent=2))
    print(
        "Review candidates, order selected steps, edit rubric bands, mark approvals Yes. Then freeze-review."
    )
    return 1 if report["failed"] else 0


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Canadian-ness GEval Research Framework")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check-connection")
    sub.add_parser(
        "validate-metrics", help="Validate the exact supplied JSON against the review workbook"
    )
    sub.add_parser("test-metrics", help="Run local mocked tests without live inference")
    calibration = sub.add_parser(
        "calibrate", help="Repeated calibration of final proposals; never freezes metrics"
    )
    calibration.add_argument("--input", default=str(ROOT / "data/calibration/final_v1_cases.jsonl"))
    calibration.add_argument("--run-id")
    calibration.add_argument("--repeats", type=int, default=3, choices=range(1, 6))
    calibration.add_argument("--resume", action="store_true")
    calibration.add_argument("--retry-failures", action="store_true")
    report = sub.add_parser(
        "calibration-report", help="Analyze saved final-metric calibration results"
    )
    report.add_argument("--run-id", required=True)
    report.add_argument("--input", default=str(ROOT / "data/calibration/final_v1_cases.jsonl"))
    report.add_argument("--report-dir")
    humans = sub.add_parser(
        "compare-human", help="Analyze actual human labels; blank labels remain pending"
    )
    humans.add_argument("--workbook", required=True)
    humans.add_argument("--output", required=True)
    humans.add_argument("--tolerance", type=float, default=0.1)
    viewer = sub.add_parser(
        "watch", help="Watch locally saved inference responses as requests finish"
    )
    viewer.add_argument("--once", action="store_true")
    sub.add_parser(
        "draft-pilot", help="Exploratory pilot only; uses unapproved first-run proposals"
    )
    prep = sub.add_parser("prepare-review")
    prep.add_argument("--runs", type=int, choices=[3, 4])
    prep.add_argument("--offline", action="store_true")
    prep.add_argument("--force", action="store_true")
    prep.add_argument("--workbook", default=str(ROOT / "review/Canadian_Ness_GEVAL_Review.xlsx"))
    freeze = sub.add_parser("freeze-review")
    freeze.add_argument("--workbook", default=str(ROOT / "review/Canadian_Ness_GEVAL_Review.xlsx"))
    freeze.add_argument("--reviewer", required=True)
    freeze.add_argument("--version", default="v1")
    for name in ("evaluate", "pilot"):
        run = sub.add_parser(name)
        run.add_argument(
            "--input",
            default=str(ROOT / "data/examples/pilot.jsonl") if name == "pilot" else None,
            required=name == "evaluate",
        )
        run.add_argument("--frozen", default=str(ROOT / "config/frozen/canadianness_geval_v1.yaml"))
        run.add_argument(
            "--output",
            default=str(
                ROOT / f"outputs/{'pilot' if name == 'pilot' else 'evaluations'}/results.jsonl"
            ),
        )
    validate = sub.add_parser("validate-dataset")
    validate.add_argument("--input", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command in (
            "validate-metrics",
            "test-metrics",
            "calibrate",
            "calibration-report",
            "compare-human",
        ):
            from .calibration.workflow import dispatch

            return dispatch(args)
        if args.command == "watch":
            from .watch import watch

            watch(once=args.once)
            return 0
        if args.command == "prepare-review":
            return prepare(args)
        if args.command == "check-connection":
            connect(Settings.load()).close()
        elif args.command == "draft-pilot":
            from .draft_pilot import run_draft_pilot
            from .judge_adapter import RemoteJudge

            gateway = connect(Settings.load())
            try:
                rows = run_draft_pilot(RemoteJudge(gateway))
                return 1 if any(r["status"] != "success" for r in rows) else 0
            finally:
                gateway.close()
        elif args.command == "freeze-review":
            from .freeze_metrics import freeze

            result = freeze(
                args.workbook,
                ROOT / "config/frozen" / f"canadianness_geval_{args.version}.yaml",
                args.reviewer,
                args.version,
            )
            print("Frozen configuration: " + result["configuration_hash"])
        elif args.command == "validate-dataset":
            from .dataset import load_dataset

            print(f"Valid records: {len(load_dataset(args.input))}")
        elif args.command in ("evaluate", "pilot"):
            from .freeze_metrics import load_frozen

            load_frozen(args.frozen)  # Fail before any API calls if no approval exists.
            from .dataset import load_dataset

            load_dataset(args.input)
            from .evaluation_runner import evaluate
            from .judge_adapter import RemoteJudge
            from .results_export import export_results

            gateway = connect(Settings.load())
            try:
                rows = evaluate(args.input, args.frozen, RemoteJudge(gateway), args.output)
                export_results(rows, Path(args.output).parent)
                if args.command == "pilot":
                    from .pilot import report_pilot

                    report_pilot(rows, args.input, Path(args.output).parent)
                return 1 if any(r["status"] == "failed" for r in rows) else 0
            finally:
                gateway.close()
        return 0
    except Exception as exc:
        # Do not expose arbitrary SDK/HTTP exception bodies or request headers.
        from .api_client import GatewayError

        if isinstance(exc, (ValueError, FileNotFoundError, GatewayError)):
            message = str(exc)
            secret = Settings.load().key.get_secret_value()
            if secret:
                message = message.replace(secret, "[REDACTED]")
            print("ERROR: " + message, file=sys.stderr)
        else:
            print(
                "ERROR: " + type(exc).__name__ + "; inspect local inputs and run tests.",
                file=sys.stderr,
            )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
