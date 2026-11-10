# Repetition-cleaned responses: M1–M7

**AI-provisional, pending calibration.**

| Model | Questions | Successful evaluations | Workbook | Every score and explanation |
|---|---:|---:|---|---|
| llama | 756 | 1814 | [Excel](../../outputs/evaluations/llama_cleaned_responses_c4_20261107_v2/full_results.xlsx) | [JSONL](../../outputs/evaluations/llama_cleaned_responses_c4_20261107_v2/all_results.jsonl) · [CSV](../../outputs/evaluations/llama_cleaned_responses_c4_20261107_v2/all_results.csv) |
| gc_llm | 756 | 1814 | [Excel](../../outputs/evaluations/gc_llm_cleaned_responses_c4_20261107_v2/full_results.xlsx) | [JSONL](../../outputs/evaluations/gc_llm_cleaned_responses_c4_20261107_v2/all_results.jsonl) · [CSV](../../outputs/evaluations/gc_llm_cleaned_responses_c4_20261107_v2/all_results.csv) |
| apertus | 756 | 1814 | [Excel](../../outputs/evaluations/apertus_cleaned_responses_c4_20261107_v2/full_results.xlsx) | [JSONL](../../outputs/evaluations/apertus_cleaned_responses_c4_20261107_v2/all_results.jsonl) · [CSV](../../outputs/evaluations/apertus_cleaned_responses_c4_20261107_v2/all_results.csv) |

## Metric means (0–1)

| Model | Metric | Evaluations | Mean |
|---|---|---:|---:|
| llama | M1 | 76 | 0.9092 |
| llama | M2 | 234 | 0.6795 |
| llama | M3 | 327 | 0.6526 |
| llama | M4 | 112 | 0.8580 |
| llama | M5 | 174 | 0.6787 |
| llama | M6 | 253 | 0.6435 |
| llama | M7 | 638 | 0.6862 |
| gc_llm | M1 | 76 | 0.6829 |
| gc_llm | M2 | 234 | 0.4346 |
| gc_llm | M3 | 327 | 0.4095 |
| gc_llm | M4 | 112 | 0.5339 |
| gc_llm | M5 | 174 | 0.4483 |
| gc_llm | M6 | 253 | 0.3897 |
| gc_llm | M7 | 638 | 0.4473 |
| apertus | M1 | 76 | 0.8605 |
| apertus | M2 | 234 | 0.6282 |
| apertus | M3 | 327 | 0.6141 |
| apertus | M4 | 112 | 0.7920 |
| apertus | M5 | 174 | 0.6701 |
| apertus | M6 | 253 | 0.5798 |
| apertus | M7 | 638 | 0.6359 |

Each run folder also contains reference/context-enriched question records, language breakdowns, execution manifests, failure/retry accounting and immutable per-metric checkpoints.

## Source answers

[Supplied cleaned JSONL](../../data/incoming/cleaned_three_model/Canadian_ness_Three_Models_Cleaned_for_Evaluation.jsonl)

Cleaned strings are edited responses, not generations at a third temperature. References were not changed to favour a model.

[Three-condition model comparisons](../../outputs/comparisons/)

[Exact seven-metric rubric](../../config/final/2026-11-03-v1/metrics_final.json)
