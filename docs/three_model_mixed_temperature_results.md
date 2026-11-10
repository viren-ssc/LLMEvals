# Three-model mixed-temperature workbook evaluation

AI-provisional, pending calibration

Completed 5,442/5,442 metric evaluations, 1,814 per model, in order Llama, GC LLM, Apertus. Each run used four-worker scheduling, the same fixed v2 evaluator and rubric, and individual checkpoint/retry persistence. All original workbook response strings were retained. Previous benchmark results were preserved.

| Metric | Llama | GC LLM | Apertus |
|---|---:|---:|---:|
| M1 | 0.9158 | 0.6724 | 0.8618 |
| M2 | 0.6714 | 0.4239 | 0.6316 |
| M3 | 0.6624 | 0.4199 | 0.6226 |
| M4 | 0.8759 | 0.5366 | 0.7982 |
| M5 | 0.6713 | 0.4546 | 0.6707 |
| M6 | 0.6455 | 0.3858 | 0.5838 |
| M7 | 0.6886 | 0.4412 | 0.6312 |

The GC LLM source contains 755 temperature-0.7 responses and one explicitly reused temperature-0.0 response. Temperature and source-run labels are preserved at question level. The other two models lack equivalent temperature metadata in this workbook. Full generation inference settings, revisions and termination metadata are not supplied and were not inferred from the earlier datasets. Consequently these are mixed-condition, AI-provisional comparisons, not controlled generation-condition or calibrated scientific rankings.

Judge temperature remains omitted, matching the original scoring protocol; server-default sampling and shared-server load can vary. Rubric interpretation limitations from the original pilots remain documented in each run manifest. No arbitrary combined Canadian-ness score was computed.

Source workbook SHA-256: `2c28b3a8aadda242394e047b092a2c25913844ea498f2207a72a869710e6dd15`

Artifacts: `three_model_mixed_temperature_results.xlsx`, `all_three_model_results.*`, `three_model_metric_summaries.*`, `matched_question_metric_scores.*`. Individual run folders retain all raw judge responses, attempts, errors/retries, API usage, immutable manifests and execution-only approval records. English/French and primary/secondary comparisons appear in both individual and combined exports.
