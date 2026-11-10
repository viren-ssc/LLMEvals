"""Read local metric checkpoints; no judge requests or experimental changes."""

import json
import statistics
from collections import Counter
from datetime import UTC, datetime

from canadianness_eval.apertus_research import PLAN
from canadianness_eval.calibration.evaluate import read_results
from canadianness_eval.settings import ROOT

plan = json.loads(PLAN.read_text(encoding="utf8"))
directory = ROOT / plan["run_directory"]
rows = [r for r in read_results(directory) if r["applicable"]]
now = datetime.now(UTC)
recent = [r for r in rows if (now - datetime.fromisoformat(r["completion_timestamp"])).total_seconds() <= 120]
good = [r for r in recent if r["status"] == "SUCCESS"]
snapshot = dict(
    timestamp=now.isoformat(),
    run_id=plan["run_id"],
    successful=sum(r["status"] == "SUCCESS" for r in rows),
    failed=sum(r["status"] != "SUCCESS" for r in rows),
    pending=plan["task_count"] - len(rows),
    recent_120s_successes=len(good),
    recent_successful_per_minute=len(good) / 2,
    recent_mean_latency_seconds=statistics.mean(r["latency_seconds"] for r in good) if good else None,
    recent_errors=dict(Counter(r.get("error") for r in recent if r["status"] != "SUCCESS")),
    concurrency=plan["judge"]["concurrency"],
    result_label="AI-provisional, pending calibration",
)
destination = ROOT / "outputs/diagnostics/apertus_performance_2min.jsonl"
destination.parent.mkdir(parents=True, exist_ok=True)
with destination.open("a", encoding="utf8") as handle:
    handle.write(json.dumps(snapshot) + "\n")
print(json.dumps(snapshot), flush=True)
