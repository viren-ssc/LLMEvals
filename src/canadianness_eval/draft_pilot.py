"""Explicit exploratory scoring of unapproved drafts; never creates a frozen config."""

import json
import time
from pathlib import Path

from .dataset import load_dataset
from .evaluation_runner import make_metric, test_case
from .metric_definitions import load_metrics
from .pilot import report_pilot
from .rubric_builder import load_rubrics
from .settings import ROOT
from .storage import digest, now, versions, write_json


def run_draft_pilot(judge, output_dir=ROOT / "outputs/pilot/draft"):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics, rubrics = load_metrics(), load_rubrics()
    definitions = {}
    for metric in metrics:
        mid = metric["metric_id"]
        raw = json.loads(
            (ROOT / "outputs/generations" / mid / "run_01.json").read_text(encoding="utf-8")
        )
        if raw["status"] != "success":
            raise ValueError("Draft pilot needs successful first-run proposals for all metrics")
        definitions[mid] = {
            **metric,
            "evaluation_steps": raw["evaluation_steps"],
            "rubric": rubrics[mid]["bands"],
            "rubric_guidance": rubrics[mid]["guidance"],
        }
    signature = digest(definitions)
    rows = []
    cases_path = ROOT / "data/examples/pilot.jsonl"
    for case in load_dataset(cases_path):
        mid = case.applicable_metrics[0]
        path = output_dir / (case.question_id + ".json")
        if path.exists():
            previous = json.loads(path.read_text(encoding="utf-8"))
            if previous.get("draft_hash") != signature or previous.get("case_hash") != digest(
                case.model_dump()
            ):
                raise ValueError("Draft pilot inputs changed; choose new output directory")
            if previous["status"] == "success":
                rows.append(previous)
                continue
        row = dict(
            question_id=case.question_id,
            model_variant=case.model_variant,
            metric_id=mid,
            score=None,
            reason=None,
            status="failed",
            research_state="DRAFT_UNAPPROVED",
            expected_quality=case.expected_quality,
            judge_model=judge.get_model_name(),
            draft_hash=signature,
            case_hash=digest(case.model_dump()),
            timestamp=now(),
            package_versions=versions(),
            illustrative=True,
        )
        start = time.perf_counter()
        offset = len(judge.gateway.history)
        try:
            metric = make_metric(definitions[mid], judge)
            metric.measure(test_case(case, definitions[mid]))
            if not 0 <= metric.score <= 1:
                raise ValueError("Score outside [0,1]")
            row.update(score=metric.score, reason=metric.reason, status="success")
        except Exception as exc:
            row["error"] = judge.gateway.safe_error(exc)
        row.update(
            latency_seconds=time.perf_counter() - start, responses=judge.gateway.history[offset:]
        )
        write_json(path, row)
        rows.append(row)
        print(f"Draft pilot {case.question_id}: {row['status']}", flush=True)
    (output_dir / "results.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8"
    )
    from .results_export import export_results

    export_results(rows, output_dir)
    report_pilot(rows, cases_path, output_dir)
    return rows
