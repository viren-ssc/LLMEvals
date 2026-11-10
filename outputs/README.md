# Canonical evaluation artifacts

For a readable starting point, open the [four-experiment results index](../results/README.md).

| Folder | Purpose |
|---|---|
| `evaluations/<run_id>/` | Complete scores, explanations, workbooks and metric checkpoints |
| `comparisons/` | Side-by-side model/condition comparison tables and workbooks |
| `queues/general_quality_cleaned_20261107_v1/` | Combined three-model correctness/completeness results |
| Other `queues/` | Completed orchestration records and combined CORE exports |
| `calibration/`, `pilot/`, `generations/`, `consolidated/` | Historical development/approval evidence retained where bound by manifests |
| `archives/` | Compact report archive, if present; canonical unpacked outputs remain authoritative |

## Inside a completed run

Start with **`full_results.xlsx`**, **`all_results.jsonl` / `all_results.csv`** and **`full_run_report.md`**. Individual records preserve question, selected response, reference evidence, metric, score and judge reasoning. Summary/failure/retry files make reporting easier.

`records/` holds immutable metric attempts used for resume; `raw/` preserves judge responses; `sessions/` preserves request accounting. These are canonical records, not disposable caches. Some byte-identical worker copies can be removed without changing these canonical records.

Historical paths remain because locked manifests and existing commands refer to them. Results indexes link here rather than creating another large copy. **All results are AI-provisional, pending calibration.**
