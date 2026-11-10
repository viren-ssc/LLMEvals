# Original versus cleaned three-model evaluation

AI-provisional, pending calibration

Completed six distinct runs: 10,884 metric evaluations, 1,814 per run, with four-worker scheduling and the unchanged v2 scorer/rubric. Question IDs, reference evidence, language and primary/secondary assignments are aligned across the six runs. All supplied cleaned strings were preserved; the evaluator performed no additional editing or generation.

Changed answers versus original workbook: {'llama': 8, 'gc_llm': 269, 'apertus': 140}.

| Model | Metric | Pairs | Original mean | Cleaned mean | Mean change |
|---|---|---:|---:|---:|---:|
| apertus | M1 | 76 | 0.8618 | 0.8605 | -0.0013 |
| apertus | M2 | 234 | 0.6316 | 0.6282 | -0.0034 |
| apertus | M3 | 327 | 0.6226 | 0.6141 | -0.0086 |
| apertus | M4 | 112 | 0.7982 | 0.7920 | -0.0062 |
| apertus | M5 | 174 | 0.6707 | 0.6701 | -0.0006 |
| apertus | M6 | 253 | 0.5838 | 0.5798 | -0.0040 |
| apertus | M7 | 638 | 0.6312 | 0.6359 | +0.0047 |
| gc_llm | M1 | 76 | 0.6724 | 0.6829 | +0.0105 |
| gc_llm | M2 | 234 | 0.4239 | 0.4346 | +0.0107 |
| gc_llm | M3 | 327 | 0.4199 | 0.4095 | -0.0104 |
| gc_llm | M4 | 112 | 0.5366 | 0.5339 | -0.0027 |
| gc_llm | M5 | 174 | 0.4546 | 0.4483 | -0.0063 |
| gc_llm | M6 | 253 | 0.3858 | 0.3897 | +0.0040 |
| gc_llm | M7 | 638 | 0.4412 | 0.4473 | +0.0061 |
| llama | M1 | 76 | 0.9158 | 0.9092 | -0.0066 |
| llama | M2 | 234 | 0.6714 | 0.6795 | +0.0081 |
| llama | M3 | 327 | 0.6624 | 0.6526 | -0.0098 |
| llama | M4 | 112 | 0.8759 | 0.8580 | -0.0179 |
| llama | M5 | 174 | 0.6713 | 0.6787 | +0.0075 |
| llama | M6 | 253 | 0.6455 | 0.6435 | -0.0020 |
| llama | M7 | 638 | 0.6886 | 0.6862 | -0.0024 |

Changed and unchanged answer subsets are exported separately by metric. Score changes for identical answers reflect repeat-judging variation, which helps interpret but does not eliminate uncertainty in cleaning comparisons. Cleaning may remove correct information or alter meaning as well as repetition. This is an edited-response experiment, not proof of judge bias or improved original model behavior. Generation and cleaning-method metadata were not supplied in the cleaned JSONL. The original workbook GC temperature mixture remains a limitation of the original condition. Judge-server default temperature, caching and load are uncontrolled. No combined Canadian-ness score or scientific/team approval is claimed.

Cleaned source SHA-256: `c5490703a827764f63e0ce436f098365fcec8c7981c362a7062bb32022344610`

Files: `six_run_original_vs_cleaned_results.xlsx`, `all_six_run_results.*`, `original_vs_cleaned_metric_pairs.*`, `original_vs_cleaned_summaries.*`. Each model/variant run separately retains all scores, reasons, input provenance, checkpoint attempts, retries, usage and immutable execution configuration.
