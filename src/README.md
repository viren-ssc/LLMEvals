# Code map

All importable implementation is in `canadianness_eval/`.

| Area | Files |
|---|---|
| Connection and judge | `settings.py`, `api_client.py`, `model_discovery.py`, `judge_adapter.py` |
| Input contracts | `dataset.py`, `hpc_ingestion.py`, `calibration/schema.py` |
| Fixed research metric construction | `final_metrics.py`, `calibration/factory.py` |
| Per-metric checkpoints | `calibration/evaluate.py` |
| Locked CORE research execution | `research_run.py`, `concurrent_research.py`, `research_exports.py` |
| Three-model CORE queues | `queued_workbook.py`, `queued_cleaned.py` |
| Two additional metrics | `general_quality_setup.py`, `general_quality_run.py` |
| Generic approved-frozen evaluation | `cli.py`, `evaluation_runner.py`, `freeze_metrics.py`, `results_export.py` |
| Optional reference verification | `verification/` |

Source paths and bytes are hashed in past experiments. This reorganization does not relocate or alter the original evaluator, rubrics or gateway code.
