import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from ..final_metrics import install_final, validate_final
from ..settings import ROOT, Settings
from ..storage import now, write_json
from .evaluate import artifact_ledger, create_run, evaluate_calibration, safe_run_id, verify_ledger
from .pilot_cases import DATASET, write_cases
from .reports import compare_humans, generate_reports


def dispatch(args):
    if args.command == "validate-metrics":
        print(
            json.dumps(
                validate_final(report_path=ROOT / "docs/metric_validation_report.md"), indent=2
            )
        )
        install_final()
        return 0
    if args.command == "test-metrics":
        environment = dict(os.environ)
        environment.pop("RUN_LIVE_TESTS", None)
        return subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-m", "not integration"],
            cwd=ROOT,
            env=environment,
            check=False,
        ).returncode
    if args.command == "compare-human":
        print(json.dumps(compare_humans(args.workbook, args.output, args.tolerance), indent=2))
        return 0
    if args.command == "calibration-report":
        directory = ROOT / "outputs/calibration" / safe_run_id(args.run_id)
        report_dir = (
            Path(args.report_dir)
            if args.report_dir
            else directory / "reports" / str(time.time_ns())
        )
        # A report-only export uses the same checkpointed results and a new destination.
        generate_reports(directory, args.input, output_dir=report_dir)
        print(f"Reports: {report_dir}")
        return 0
    validate_final()
    install_final()
    if Path(args.input).resolve() == DATASET.resolve():
        write_cases()
    if args.resume and not args.run_id:
        raise ValueError("--resume requires the original --run-id")
    run_id = safe_run_id(args.run_id or "final_v1_" + re.sub(r"[^A-Za-z0-9]", "", now()))
    directory = create_run(ROOT / "outputs/calibration" / run_id, resume=args.resume)
    ledger_path = directory / "prior_artifacts_sha256.json"
    if ledger_path.exists():
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    else:
        ledger = artifact_ledger(ROOT)
        write_json(ledger_path, ledger)
    gateway, judge, failure = None, None, None
    try:
        from ..cli import connect
        from ..judge_adapter import RemoteJudge

        gateway = connect(Settings.load(), report_path=directory / "connection_check.json")
        judge = RemoteJudge(gateway)
    except Exception as exc:
        secret = Settings.load().key.get_secret_value()
        failure = str(exc).replace(secret, "[REDACTED]") if secret else type(exc).__name__
        write_json(
            directory / "gateway_unavailable.json",
            {"status": "UNAVAILABLE", "reason": failure, "timestamp": now()},
        )
        print("Gateway unavailable; preserving readiness/skip states and completing local reports.")
    try:
        rows = evaluate_calibration(
            args.input,
            judge,
            directory,
            repeats=args.repeats,
            resume=args.resume,
            retry_failures=args.retry_failures,
            unavailable_reason=failure,
        )
    finally:
        if gateway:
            gateway.close()
        verify_ledger(ROOT, ledger)
        write_json(
            directory / "prior_artifact_integrity.json",
            {
                "all_prior_artifacts_unchanged": True,
                "checked_files": len(ledger),
                "timestamp": now(),
            },
        )
    destination = (
        directory
        if not (directory / "calibration_summary.xlsx").exists()
        else directory / "reports" / str(time.time_ns())
    )
    generate_reports(directory, args.input, output_dir=destination)
    print(f"Calibration and human-review reports: {destination}")
    print("Metrics remain CALIBRATION_NOT_FROZEN; human labels remain blank.")
    return 1 if any(r["status"] in ("FAILED", "SKIPPED_GATEWAY_UNAVAILABLE") for r in rows) else 0
