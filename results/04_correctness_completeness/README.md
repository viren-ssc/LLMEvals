# Cleaned responses: correctness and completeness

**AI-provisional, pending calibration.**

| Model | Questions | Successful evaluations | Workbook | Every score and explanation |
|---|---:|---:|---|---|
| llama | 756 | 1512 | [Excel](../../outputs/evaluations/llama_general_quality_cleaned_20261107_v1/full_results.xlsx) | [JSONL](../../outputs/evaluations/llama_general_quality_cleaned_20261107_v1/all_results.jsonl) · [CSV](../../outputs/evaluations/llama_general_quality_cleaned_20261107_v1/all_results.csv) |
| gc_llm | 756 | 1512 | [Excel](../../outputs/evaluations/gc_llm_general_quality_cleaned_20261107_v1/full_results.xlsx) | [JSONL](../../outputs/evaluations/gc_llm_general_quality_cleaned_20261107_v1/all_results.jsonl) · [CSV](../../outputs/evaluations/gc_llm_general_quality_cleaned_20261107_v1/all_results.csv) |
| apertus | 756 | 1512 | [Excel](../../outputs/evaluations/apertus_general_quality_cleaned_20261107_v1/full_results.xlsx) | [JSONL](../../outputs/evaluations/apertus_general_quality_cleaned_20261107_v1/all_results.jsonl) · [CSV](../../outputs/evaluations/apertus_general_quality_cleaned_20261107_v1/all_results.csv) |

## Metric means (0–1)

| Model | Metric | Evaluations | Mean |
|---|---|---:|---:|
| llama | completeness | 756 | 0.7184 |
| llama | correctness | 756 | 0.7591 |
| gc_llm | completeness | 756 | 0.4636 |
| gc_llm | correctness | 756 | 0.4821 |
| apertus | completeness | 756 | 0.6799 |
| apertus | correctness | 756 | 0.6892 |

Each run folder also contains reference/context-enriched question records, language breakdowns, execution manifests, failure/retry accounting and immutable per-metric checkpoints.

## Source answers

[Supplied cleaned JSONL](../../data/incoming/cleaned_three_model/Canadian_ness_Three_Models_Cleaned_for_Evaluation.jsonl)

Cleaned strings are edited responses, not generations at a third temperature. References were not changed to favour a model.

[Combined Excel and paired comparisons](../../outputs/queues/general_quality_cleaned_20261107_v1/)

[Exact two-metric definitions](../../config/general_answer_quality/2026-11-07-user-v1/metrics_extracted.json)
