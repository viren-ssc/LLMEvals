# GC LLM: previous versus new mixed-temperature run

AI-provisional, pending calibration

Both runs completed 1,814/1,814 unique question-model-metric evaluations over the same 756 questions: 756 primary and 1,058 secondary. The new run has no final failed/missing tasks; all 1,814 scoring HTTP calls returned 200, with one model-discovery call. Its API-reported usage was 4,176,342 tokens. No new judge calls were used for this comparison.

| Metric | Tasks | Previous mean | New mean | New minus previous |
|---|---:|---:|---:|---:|
| M1 | 76 | 0.6421 | 0.6724 | +0.0303 |
| M2 | 234 | 0.4491 | 0.4239 | -0.0252 |
| M3 | 327 | 0.4303 | 0.4199 | -0.0104 |
| M4 | 112 | 0.6000 | 0.5366 | -0.0634 |
| M5 | 174 | 0.4638 | 0.4546 | -0.0092 |
| M6 | 253 | 0.4091 | 0.3858 | -0.0233 |
| M7 | 638 | 0.4766 | 0.4412 | -0.0354 |

## language comparison

| Metric | language | Tasks | Previous mean | New mean | Change |
|---|---|---:|---:|---:|---:|
| M1 | en | 39 | 0.6667 | 0.7564 | +0.0897 |
| M1 | fr | 37 | 0.6162 | 0.5838 | -0.0324 |
| M2 | en | 130 | 0.4877 | 0.4608 | -0.0269 |
| M2 | fr | 104 | 0.4010 | 0.3779 | -0.0231 |
| M3 | en | 177 | 0.4678 | 0.4960 | +0.0282 |
| M3 | fr | 150 | 0.3860 | 0.3300 | -0.0560 |
| M4 | en | 50 | 0.6180 | 0.6100 | -0.0080 |
| M4 | fr | 62 | 0.5855 | 0.4774 | -0.1081 |
| M5 | en | 95 | 0.4474 | 0.4916 | +0.0442 |
| M5 | fr | 79 | 0.4835 | 0.4101 | -0.0734 |
| M6 | en | 137 | 0.4307 | 0.4358 | +0.0051 |
| M6 | fr | 116 | 0.3836 | 0.3267 | -0.0569 |
| M7 | en | 349 | 0.5000 | 0.4980 | -0.0020 |
| M7 | fr | 289 | 0.4484 | 0.3727 | -0.0758 |

## metric_role comparison

| Metric | metric_role | Tasks | Previous mean | New mean | Change |
|---|---|---:|---:|---:|---:|
| M1 | primary | 59 | 0.6746 | 0.6898 | +0.0153 |
| M1 | secondary | 17 | 0.5294 | 0.6118 | +0.0824 |
| M2 | primary | 161 | 0.4559 | 0.4280 | -0.0280 |
| M2 | secondary | 73 | 0.4342 | 0.4151 | -0.0192 |
| M3 | primary | 233 | 0.4386 | 0.4210 | -0.0176 |
| M3 | secondary | 94 | 0.4096 | 0.4170 | +0.0074 |
| M4 | primary | 61 | 0.5607 | 0.4918 | -0.0689 |
| M4 | secondary | 51 | 0.6471 | 0.5902 | -0.0569 |
| M5 | primary | 72 | 0.4792 | 0.4569 | -0.0222 |
| M5 | secondary | 102 | 0.4529 | 0.4529 | +0.0000 |
| M6 | primary | 95 | 0.4000 | 0.4074 | +0.0074 |
| M6 | secondary | 158 | 0.4146 | 0.3728 | -0.0418 |
| M7 | primary | 75 | 0.4800 | 0.4600 | -0.0200 |
| M7 | secondary | 563 | 0.4762 | 0.4387 | -0.0375 |

## Findings and interpretation

The new run is higher on M1 and lower on M2-M7. The largest descriptive decline is M4 (-0.0634 on the 0-1 scale); M7 declines about 0.0354. These are paired observed differences, not calibrated scientific rankings or proof of a temperature effect.

The new workbook explicitly labels 755 GC LLM answers as temperature 0.7, and one reused response (CA-EXP2-152) as temperature 0.0. This is a mixed-condition run, not a pure temperature-0.7 benchmark. That reused answer covers two metric tasks: M5 changes from 0.4 to 0.1 despite identical response text, while M7 remains 0.2. This illustrates repeat-judgment variation; one question is insufficient to estimate the uncertainty of the full comparison.

The earlier raw/provenance files did not directly record temperature or top_p. The later workbook replacement-provenance sheet identifies its reused source run as temperature 0.0; this is retrospective source attribution, not an original complete per-response inference manifest. top_p remains unavailable for GC LLM; no value is inferred from the Llama discussion.

Exploratory repetition flags: previous 350/756, new 244/756. These use the same derived four-gram heuristic; flags are analysis only and were never judge instructions or exclusion rules. Subgroup means are exported but are confounded by question mix. Previous truncation flags are retained as previous-response metadata only; new termination flags/output-token counts/revision were not supplied by the workbook and are not inferred.

## Scoring and comparability

Question IDs, benchmark evidence, assignments, rubric checksum and v2 evaluator-template checksum match across all 1,814 pairs. The same gpt-oss-120b scoring protocol was used; judge temperature was omitted and the numeric server default is unknown. Earlier execution was sequential; the new execution used four workers. Server load, caching and timing differed. Generation seeds, full prompts, revisions and all decoding controls were not supplied for both conditions, so temperature cannot be isolated as the sole cause. No extra normalization, rubric changes, arbitrary combined Canadian-ness score, scientific calibration or team approval is claimed.

Rubric SHA-256: `bb9889807b7babc8feed6a97ddd0c12c0fa334627e5d295017167fbd0a767cb2`

Evaluator-template SHA-256: `ecb714aa746f7bdce82d86fd9bcc288d4e26ffd15cfa210bbd19a356e095793f`

## Files

`gc_llm_previous_vs_mixed_temperature.xlsx`: all pairs, original/new answers and reasons, metric/language/role summaries, mixed-temperature and repetition groups, and reused-answer control. `question_metric_comparisons.*` and `metric_language_role_comparisons.*` provide CSV/JSONL exports. `comparison_manifest.json` records source hashes and settings limitations. The new run itself retains its full independent results at `outputs/evaluations/gc_llm_mixed_temperature_workbook_c4_20261107_v2/`.
