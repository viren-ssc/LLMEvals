# Mixed-temperature workbook (user-labelled temperature 0.7)

**AI-provisional, pending calibration.**

| Model | Questions | Successful evaluations | Workbook | Every score and explanation |
|---|---:|---:|---|---|
| llama | 756 | 1814 | [Excel](../../outputs/evaluations/llama_mixed_temperature_workbook_c4_20261107_v2/full_results.xlsx) | [JSONL](../../outputs/evaluations/llama_mixed_temperature_workbook_c4_20261107_v2/all_results.jsonl) · [CSV](../../outputs/evaluations/llama_mixed_temperature_workbook_c4_20261107_v2/all_results.csv) |
| gc_llm | 756 | 1814 | [Excel](../../outputs/evaluations/gc_llm_mixed_temperature_workbook_c4_20261107_v2/full_results.xlsx) | [JSONL](../../outputs/evaluations/gc_llm_mixed_temperature_workbook_c4_20261107_v2/all_results.jsonl) · [CSV](../../outputs/evaluations/gc_llm_mixed_temperature_workbook_c4_20261107_v2/all_results.csv) |
| apertus | 756 | 1814 | [Excel](../../outputs/evaluations/apertus_mixed_temperature_workbook_c4_20261107_v2/full_results.xlsx) | [JSONL](../../outputs/evaluations/apertus_mixed_temperature_workbook_c4_20261107_v2/all_results.jsonl) · [CSV](../../outputs/evaluations/apertus_mixed_temperature_workbook_c4_20261107_v2/all_results.csv) |

## Metric means (0–1)

| Model | Metric | Evaluations | Mean |
|---|---|---:|---:|
| llama | M1 | 76 | 0.9158 |
| llama | M2 | 234 | 0.6714 |
| llama | M3 | 327 | 0.6624 |
| llama | M4 | 112 | 0.8759 |
| llama | M5 | 174 | 0.6713 |
| llama | M6 | 253 | 0.6455 |
| llama | M7 | 638 | 0.6886 |
| gc_llm | M1 | 76 | 0.6724 |
| gc_llm | M2 | 234 | 0.4239 |
| gc_llm | M3 | 327 | 0.4199 |
| gc_llm | M4 | 112 | 0.5366 |
| gc_llm | M5 | 174 | 0.4546 |
| gc_llm | M6 | 253 | 0.3858 |
| gc_llm | M7 | 638 | 0.4412 |
| apertus | M1 | 76 | 0.8618 |
| apertus | M2 | 234 | 0.6316 |
| apertus | M3 | 327 | 0.6226 |
| apertus | M4 | 112 | 0.7982 |
| apertus | M5 | 174 | 0.6707 |
| apertus | M6 | 253 | 0.5838 |
| apertus | M7 | 638 | 0.6312 |

Each run folder also contains reference/context-enriched question records, language breakdowns, execution manifests, failure/retry accounting and immutable per-metric checkpoints.

## Source answers

[Supplied workbook](../../data/incoming/mixed_temperature_three_model/canadianness_756_three_model_answers_MIXED_TEMPERATURE_COMPLETE.xlsx)

GC LLM has 755 temperature-0.7 answers and one reused temperature-0 answer. Apertus/Llama temperature metadata is not independently recorded in the workbook.

[Three-condition model comparisons](../../outputs/comparisons/)

[Exact seven-metric rubric](../../config/final/2026-11-03-v1/metrics_final.json)
