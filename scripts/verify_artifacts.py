"""Read-only audit of real generation artifacts, provenance and review state."""

import json
from collections import Counter

import pandas as pd
from openpyxl import load_workbook

from canadianness_eval.generate_steps import Steps
from canadianness_eval.metric_definitions import load_metrics
from canadianness_eval.rubric_builder import load_rubrics
from canadianness_eval.settings import ROOT, Settings
from canadianness_eval.storage import now, write_json


def main():
    metrics = load_metrics()
    load_rubrics()
    records = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted((ROOT / "outputs/generations").glob("M*/run_*.json"))
    ]
    counts = Counter(r["metric_id"] for r in records if r["status"] == "success")
    for record in records:
        if record["status"] == "success":
            Steps(steps=record["evaluation_steps"])
            assert record["responses"], "Missing raw response provenance"
    candidate_count = sum(len(r["evaluation_steps"]) for r in records)
    workbook = ROOT / "review/Canadian_Ness_GEVAL_Review.xlsx"
    candidates = pd.read_excel(workbook, sheet_name="Step Candidates", keep_default_na=False)
    assert len(candidates) == candidate_count
    assert sorted(candidates.original_step) == sorted(
        s for r in records for s in r["evaluation_steps"]
    )
    book = load_workbook(workbook)
    assert len(book.sheetnames) == 4
    secret = Settings.load().key.get_secret_value()
    if secret:
        for folder in ("src", "scripts", "tests", "config", "docs", "data", "outputs"):
            for path in (ROOT / folder).rglob("*"):
                if path.is_file() and path.suffix in (
                    ".py",
                    ".json",
                    ".jsonl",
                    ".csv",
                    ".yaml",
                    ".md",
                    ".txt",
                ):
                    assert secret not in path.read_text(encoding="utf-8-sig", errors="replace"), (
                        "Credential found in artifact"
                    )
        for sheet in book:
            for row in sheet:
                assert all(secret not in str(cell.value) for cell in row), (
                    "Credential found in workbook"
                )
    book.close()
    report = dict(
        timestamp=now(),
        metrics=len(metrics),
        recorded_generation_sets=len(records),
        successful_sets_by_metric=dict(counts),
        candidate_steps=candidate_count,
        workbook_original_text_matches=True,
        credentials_absent_from_artifacts=True,
        frozen_versions=len(list((ROOT / "config/frozen").glob("*.yaml"))),
    )
    write_json(ROOT / "outputs/artifact_verification.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
