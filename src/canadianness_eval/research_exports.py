"""Full provisional-run exports derived from immutable existing metric checkpoints."""

import csv
import json
from collections import Counter
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from .calibration.evaluate import read_results
from .calibration.schema import load_cases
from .final_metrics import file_hash
from .hpc_workflow import export_reports
from .settings import ROOT
from .storage import write_json

LABEL = "AI-provisional, pending calibration"


def table(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.with_suffix(".jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n" for r in rows),
        encoding="utf-8",
    )
    with path.with_suffix(".csv").open("w", encoding="utf-8-sig", newline="") as handle:
        if rows:
            writer = csv.DictWriter(
                handle, fieldnames=list(dict.fromkeys(k for row in rows for k in row))
            )
            writer.writeheader()
            writer.writerows(
                {
                    k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                    for k, v in r.items()
                }
                for r in rows
            )


def add_sheet(book, title, rows):
    sheet = book.create_sheet(title)
    if not rows:
        sheet.append(["result_label", "status"])
        sheet.append([LABEL, "No records in this category"])
        return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    sheet.append(keys)
    for row in rows:
        values = []
        for k in keys:
            value = row.get(k)
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            values.append(value)
        sheet.append(values)
    for cells in sheet:
        for cell in cells:
            if isinstance(cell.value, str):
                cell.data_type = "s"
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in sheet.columns:
        sheet.column_dimensions[column[0].column_letter].width = 25


def export_research_results(directory, plan):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    expected_cases_hash = plan.get("input_sha256", {}).get(plan["cases_path"])
    if expected_cases_hash and file_hash(ROOT / plan["cases_path"]) != expected_cases_hash:
        raise ValueError("Cannot export using a changed case dataset; restore the locked inputs")
    cases = {c.question_id: c for c in load_cases(ROOT / plan["cases_path"])}
    latest = [r for r in read_results(directory) if r["applicable"]]
    expected = {
        (t["question_id"], t["evaluated_model"], t["evaluation_metric"]): t for t in plan["tasks"]
    }
    indexed = {(r["question_id"], r["model_variant"], r["metric_id"]): r for r in latest}
    if not set(indexed) <= set(expected):
        raise ValueError("Output contains tasks outside the locked model/run plan")
    statistics = export_reports(directory, statistics_filename="run_statistics.json")
    records = []
    for key, task in expected.items():
        saved = indexed.get(key)
        case = cases[task["question_id"]]
        record = dict(
            **task,
            question=case.question,
            model_answer=case.model_answer,
            reference_answer=case.reference_answer,
            context_supporting_summary=case.reference_context,
            applicable_metrics=case.applicable_metrics,
            score=saved["score"] if saved else None,
            judge_reason=saved["reason"] if saved else None,
            status=saved["status"] if saved else "PENDING",
            judge_model=plan["judge"]["model"],
            rubric_version=plan["rubric_version"],
            rubric_sha256=plan["rubric_sha256"],
            evaluator_template_version=plan["evaluator_template_version"],
            evaluator_template_sha256=plan["evaluator_template_sha256"],
            evaluation_run_id=plan["run_id"],
            evaluation_timestamp=saved["timestamp"] if saved else None,
            completion_timestamp=saved.get("completion_timestamp") if saved else None,
            judge_configuration=saved["judge_configuration"] if saved else plan["judge"],
            attempt=saved["attempt"] if saved else None,
            error_message=saved["error"] if saved else None,
            request_attempts=saved["request_attempts"] if saved else 0,
            raw_output_file=saved["raw_output_file"] if saved else None,
            result_label=LABEL,
            provisional=True,
            scientific_validity_approved=False,
        )
        records.append(record)
    table(directory / "all_results", records)
    table(directory / "primary_results", [r for r in records if r["metric_role"] == "primary"])
    table(directory / "secondary_results", [r for r in records if r["metric_role"] == "secondary"])
    failures = [r for r in records if r["status"] not in ("SUCCESS", "PENDING")]
    missing = [r for r in records if r["status"] == "PENDING"]
    table(directory / "failures", failures)
    table(directory / "missing_tasks", missing)
    attempts = []
    usage = Counter()
    api_calls = 0
    usage_missing = 0
    http_statuses = Counter()
    for path in sorted((directory / "records").glob("*.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        if not row["applicable"]:
            continue
        raw_path = row.get("raw_output_file")
        events = (
            json.loads((directory / raw_path).read_text(encoding="utf-8"))["responses"]
            if raw_path
            else []
        )
        row_usage = Counter()
        for event in events:
            api_calls += 1
            http_statuses[str(event["status"])] += 1
            reported = event.get("raw_response", {}).get("usage")
            if not reported:
                usage_missing += 1
            for key, value in (reported or {}).items():
                if isinstance(value, int):
                    usage[key] += value
                    row_usage[key] += value
        attempts.append(
            dict(
                question_id=row["question_id"],
                evaluated_model=row["model_variant"],
                evaluation_metric=row["metric_id"],
                attempt=row["attempt"],
                status=row["status"],
                error_message=row["error"],
                http_attempts=row["request_attempts"],
                timestamp=row["timestamp"],
                completion_timestamp=row.get("completion_timestamp"),
                latency_seconds=row["latency_seconds"],
                api_reported_tokens=dict(row_usage),
                raw_output_file=raw_path,
                result_label=LABEL,
            )
        )
    table(directory / "attempts", attempts)
    table(
        directory / "retry_report",
        [r for r in attempts if r["attempt"] > 1 or r["http_attempts"] > 1],
    )
    summaries = json.loads((directory / "metric_summaries.json").read_text(encoding="utf-8"))
    for row in summaries:
        row["result_label"] = LABEL
    # Include planned denominators separately from the observed means; no pending/failed score becomes zero.
    for row in summaries:
        dims = row["grouping"].split("/")
        row["planned"] = sum(all(task[k] == row[k] for k in dims) for task in plan["tasks"])
        row["pending"] = row["planned"] - row["count"]
    table(directory / "all_metric_summaries", summaries)
    session_calls = 0
    session_rows = []
    for path in (directory / "sessions").glob("*.json"):
        if path.name.endswith(("_discovery.json", "_uncheckpointed_events.json")):
            continue
        session_rows.append(json.loads(path.read_text(encoding="utf-8")))
    discovery_calls = 0
    uncheckpointed_calls = 0
    uncheckpointed_usage = Counter()
    for path in (directory / "sessions").glob("*_discovery.json"):
        discovery_calls += len(json.loads(path.read_text(encoding="utf-8")))
    for path in (directory / "sessions").glob("*_uncheckpointed_events.json"):
        events = json.loads(path.read_text(encoding="utf-8"))
        uncheckpointed_calls += len(events)
        for event in events:
            for key, value in event.get("raw_response", {}).get("usage", {}).items():
                if isinstance(value, int):
                    uncheckpointed_usage[key] += value
    session_calls = sum(r["http_attempts"] for r in session_rows)
    summary = dict(
        run_id=plan["run_id"],
        evaluated_model=plan["evaluated_model"],
        planned=plan["task_count"],
        successful=sum(r["status"] == "SUCCESS" for r in records),
        failed_or_skipped=len(failures),
        missing=len(missing),
        status_counts=dict(Counter(r["status"] for r in records)),
        result_label=LABEL,
        scientific_validity_approved=False,
        rubric_empirically_calibrated=False,
        scoring_http_attempts=api_calls,
        discovery_http_attempts=discovery_calls,
        uncheckpointed_http_events=uncheckpointed_calls,
        session_http_attempts=session_calls,
        api_reported_tokens=dict(usage),
        uncheckpointed_api_reported_tokens=dict(uncheckpointed_usage),
        scoring_http_events_without_usage=usage_missing,
        http_status_counts=dict(http_statuses),
        accounting_note="Tokens include all checkpointed attempts, including failures/retries with reported usage. Uncheckpointed events are reported separately; interrupted in-flight or unreported usage is unknown, not zero.",
        known_scoring_limitations=plan["known_scoring_limitations"],
        observed_statistics=statistics,
    )
    write_json(directory / "full_run_summary.json", summary)
    write_json(directory / "locked_experiment.json", plan)
    book = Workbook()
    book.remove(book.active)
    add_sheet(book, "All metric scores", records)
    add_sheet(book, "Primary only", [r for r in records if r["metric_role"] == "primary"])
    add_sheet(book, "Secondary only", [r for r in records if r["metric_role"] == "secondary"])
    add_sheet(book, "Metric language role means", summaries)
    add_sheet(book, "Failures", failures)
    add_sheet(book, "Missing tasks", missing)
    add_sheet(book, "Attempts and retries", attempts)
    add_sheet(
        book,
        "Experiment manifest",
        [
            dict(key=k, value=v, result_label=LABEL)
            for k, v in plan.items()
            if k not in ("tasks", "protected_pilot_sha256")
        ],
    )
    add_sheet(
        book, "Run summary", [dict(key=k, value=v, result_label=LABEL) for k, v in summary.items()]
    )
    book.save(directory / "full_results.xlsx")
    report = [
        f"# {plan['evaluated_model']} provisional research run: {plan['run_id']}",
        "",
        f"**{LABEL}**. Scientific/team approval and empirical calibration have not been conferred.",
        "",
        f"Successful: {summary['successful']}/{plan['task_count']}; failed/skipped: {len(failures)}; pending: {len(missing)}.",
        "",
        "| Metric | Planned | Scored | Mean |",
        "|---|---:|---:|---:|",
    ]
    for mid in sorted({t["evaluation_metric"] for t in plan["tasks"]}):
        found = next(
            (
                r
                for r in summaries
                if r["grouping"] == "evaluated_model/evaluation_metric"
                and r["evaluation_metric"] == mid
            ),
            None,
        )
        planned = sum(t["evaluation_metric"] == mid for t in plan["tasks"])
        mean = f"{found['mean']:.4f}" if found and found["mean"] is not None else "not scored"
        report.append(f"| {mid} | {planned} | {found['scored'] if found else 0} | {mean} |")
    report += [
        "",
        "Language and assignment breakdowns are in all_metric_summaries.csv and full_results.xlsx. Failed/pending records never count as zero scores. No combined Canadian-ness score is calculated.",
        "",
        "## Known limitations",
        "",
    ]
    report.extend("- " + item for item in plan["known_scoring_limitations"])
    report += [
        "",
        "Individual questions, unchanged model responses, reference answers, supporting summaries, scores and reasons are in all_results.jsonl/CSV and full_results.xlsx. Primary-only/secondary-only files, failure/missing/retry reports, raw responses, session accounting and the locked experiment manifest are retained alongside them.",
        "",
    ]
    (directory / "full_run_report.md").write_text("\n".join(report), encoding="utf-8")
    return summary
