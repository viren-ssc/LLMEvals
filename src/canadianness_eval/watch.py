"""Read-only local inference watcher. Does not transmit data or display credentials."""

import json
import time

from .settings import ROOT


def watch(interval=1.0, once=False):
    seen = {}
    print(
        "Watching local inference artifacts. Ctrl+C stops this viewer; inference continues.",
        flush=True,
    )
    try:
        while True:
            generations = sorted((ROOT / "outputs/generations").glob("M*/run_*.json"))
            pilots = sorted((ROOT / "outputs/pilot").rglob("PILOT-*.json"))
            calibrations = sorted((ROOT / "outputs/calibration").glob("*/records/*.json"))
            success = failed = 0
            for path in generations + pilots + calibrations:
                try:
                    stamp = path.stat().st_mtime_ns
                    row = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if path in generations:
                    success += row.get("status") == "success"
                    failed += row.get("status") == "failed"
                if seen.get(path) == stamp:
                    continue
                seen[path] = stamp
                if row.get("status") == "NOT_APPLICABLE":
                    continue
                label = row.get("question_id") or f"{row['metric_id']} run {row['run_number']}"
                if row.get("evaluation_run_id"):
                    label += f" / {row['metric_id']} repeat {row['repeat']}"
                print(
                    f"\n[{row.get('timestamp', row.get('generation_timestamp', ''))}] {label}: {row['status']}",
                    flush=True,
                )
                if "evaluation_steps" in row:
                    for index, step in enumerate(row["evaluation_steps"], 1):
                        print(f"  {index}. {step}", flush=True)
                if row.get("score") is not None:
                    print(f"  Score: {row['score']} | {row.get('reason', '')}", flush=True)
                if row.get("error"):
                    print("  Error: " + row["error"], flush=True)
            if once or generations or pilots:
                counts = (success, failed, len(pilots))
                if seen.get("counts") != counts:
                    print(
                        f"\nSaved generation sets: {success} successful, {failed} failed. Saved pilot cases: {len(pilots)}.",
                        flush=True,
                    )
                    seen["counts"] = counts
            if once:
                return
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nViewer stopped.")
