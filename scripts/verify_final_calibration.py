"""Audit real final-metric artifacts without printing credentials or modifying experiments."""

import json
from collections import Counter

from openpyxl import load_workbook

from canadianness_eval.calibration.evaluate import read_results, verify_ledger
from canadianness_eval.final_metrics import FINAL_JSON, SOURCE_JSON, file_hash, load_final
from canadianness_eval.settings import ROOT, Settings
from canadianness_eval.storage import now, write_json


def main():
    config = load_final()
    assert file_hash(SOURCE_JSON) == file_hash(FINAL_JSON)
    secret = Settings.load().key.get_secret_value()
    runs = []
    for name, expected in [
        ("final_v1_calibration_20261103_01", 141),
        ("final_v1_french_supplement_20261103_01", 6),
    ]:
        directory = ROOT / "outputs/calibration" / name
        rows = read_results(directory)
        successful = [r for r in rows if r["status"] == "SUCCESS"]
        assert len(successful) == expected
        assert all(r["metric_json_sha256"] == file_hash(FINAL_JSON) for r in rows)
        assert all(0 <= r["score"] <= 1 and r["score"] == r["deepeval_score"] for r in successful)
        assert all(r["score"] is None for r in rows if r["status"] != "SUCCESS")
        assert all(r["evidence_status"] in ("VERIFIED", "NOT_REQUIRED") for r in successful)
        assert all(
            Counter(r["repeat"] for r in successful)[repeat] == expected // 3
            for repeat in (1, 2, 3)
        )
        ledger = json.loads((directory / "prior_artifacts_sha256.json").read_text(encoding="utf-8"))
        verify_ledger(ROOT, ledger)
        for workbook in directory.rglob("human_calibration_review.xlsx"):
            book = load_workbook(workbook)
            for row in book["Human review"].iter_rows(min_row=2):
                assert row[9].value is None and row[10].value is None and row[11].value is None
            book.close()
        if secret:
            for path in directory.rglob("*"):
                if path.is_file() and path.suffix in (".json", ".jsonl", ".md", ".csv"):
                    assert secret not in path.read_text(encoding="utf-8"), (
                        "Secret found in result artifact"
                    )
        runs.append(
            dict(
                run_id=name,
                successful_scores=len(successful),
                status_counts=dict(Counter(r["status"] for r in rows)),
                protected_artifacts_unchanged=len(ledger),
                human_scores_blank=True,
            )
        )
    report = dict(
        timestamp=now(),
        metric_version=config.version,
        selected_steps=42,
        configuration_unchanged=True,
        runs=runs,
        credentials_absent=True,
        frozen_versions=len(list((ROOT / "config/frozen").glob("*.yaml"))),
    )
    target = ROOT / "outputs/calibration/final_calibration_audit.json"
    if target.exists():
        raise ValueError("Audit already exists; preserve it and choose a new report version")
    write_json(target, report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
