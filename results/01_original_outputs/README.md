# Original outputs (user-labelled temperature 0)

**AI-provisional, pending calibration.**

| Model | Questions | Successful evaluations | Workbook | Every score and explanation |
|---|---:|---:|---|---|
| llama | 756 | 1814 | [Excel](../../outputs/evaluations/llama_full_20261106_v2/full_results.xlsx) | [JSONL](../../outputs/evaluations/llama_full_20261106_v2/all_results.jsonl) · [CSV](../../outputs/evaluations/llama_full_20261106_v2/all_results.csv) |
| gc_llm | 756 | 1814 | [Excel](../../outputs/evaluations/gc_llm_full_as_generated_20261106_v2/full_results.xlsx) | [JSONL](../../outputs/evaluations/gc_llm_full_as_generated_20261106_v2/all_results.jsonl) · [CSV](../../outputs/evaluations/gc_llm_full_as_generated_20261106_v2/all_results.csv) |
| apertus | 756 | 1814 | [Excel](../../outputs/evaluations/apertus_full_as_generated_c4_20261107_v2/full_results.xlsx) | [JSONL](../../outputs/evaluations/apertus_full_as_generated_c4_20261107_v2/all_results.jsonl) · [CSV](../../outputs/evaluations/apertus_full_as_generated_c4_20261107_v2/all_results.csv) |

## Metric means (0–1)

| Model | Metric | Evaluations | Mean |
|---|---|---:|---:|
| llama | M1 | 76 | 0.9053 |
| llama | M2 | 234 | 0.6735 |
| llama | M3 | 327 | 0.6661 |
| llama | M4 | 112 | 0.8634 |
| llama | M5 | 174 | 0.6897 |
| llama | M6 | 253 | 0.6561 |
| llama | M7 | 638 | 0.6989 |
| gc_llm | M1 | 76 | 0.6421 |
| gc_llm | M2 | 234 | 0.4491 |
| gc_llm | M3 | 327 | 0.4303 |
| gc_llm | M4 | 112 | 0.6000 |
| gc_llm | M5 | 174 | 0.4638 |
| gc_llm | M6 | 253 | 0.4091 |
| gc_llm | M7 | 638 | 0.4766 |
| apertus | M1 | 76 | 0.8539 |
| apertus | M2 | 234 | 0.6158 |
| apertus | M3 | 327 | 0.5786 |
| apertus | M4 | 112 | 0.7982 |
| apertus | M5 | 174 | 0.6690 |
| apertus | M6 | 253 | 0.5870 |
| apertus | M7 | 638 | 0.6199 |

Each run folder also contains reference/context-enriched question records, language breakdowns, execution manifests, failure/retry accounting and immutable per-metric checkpoints.

## Source answers

- [Llama](../../data/incoming/Canadian-ness_Llama_756_Generations.jsonl)
- [GC LLM](../../data/incoming/gc_llm_as_generated/)
- [Apertus](../../data/incoming/apertus_as_generated/)

Original temperature labels are user-supplied; generation controls and underlying checkpoint identity are not fully independently attested. Length-limited and repeated answers were retained.

[Three-condition model comparisons](../../outputs/comparisons/)

[Exact seven-metric rubric](../../config/final/2026-11-03-v1/metrics_final.json)
