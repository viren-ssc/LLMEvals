# gc_llm: previous, workbook and cleaned responses

AI-provisional, pending calibration

All three runs completed 1,814/1,814 evaluations over the same 756 questions: 756 primary and 1,058 secondary tasks per run. This analysis aligns all 1,814 question-metric triples and retains every one of the 5,442 scores and explanations. No new judge calls were made and no source answer, previous judgment or frozen run manifest was modified.

| Metric | Tasks | Previous | Workbook | Cleaned | Cleaned minus workbook |
|---|---:|---:|---:|---:|---:|
| M1 | 76 | 0.6421 | 0.6724 | 0.6829 | +0.0105 |
| M2 | 234 | 0.4491 | 0.4239 | 0.4346 | +0.0107 |
| M3 | 327 | 0.4303 | 0.4199 | 0.4095 | -0.0104 |
| M4 | 112 | 0.6000 | 0.5366 | 0.5339 | -0.0027 |
| M5 | 174 | 0.4638 | 0.4546 | 0.4483 | -0.0063 |
| M6 | 253 | 0.4091 | 0.3858 | 0.3897 | +0.0040 |
| M7 | 638 | 0.4766 | 0.4412 | 0.4473 | +0.0061 |

## Cleaning and repeat-judgment variation

Cleaning changes 269 answers, covering 669 metric judgments. Of the 1145 judgments with identical answer text, 550 (48.0%) have different scores on repeat judging. Thus full-set differences include changes on unedited responses and cannot be attributed solely to cleaning or interpreted as proof of judge repetition bias. The changed/unchanged decomposition exports each subset contribution to every metric mean shift. Edited answers may also differ in factual coverage or meaning; no cleaning algorithm or full edit provenance was supplied. The unchanged subset is descriptive evidence of repeatability limits, not a calibrated causal correction for edited-response scores.

For GC LLM, cleaned means rise on M1, M2, M6 and M7 relative to the workbook and fall on M3-M5. Against the previous run, cleaned means are higher only on M1. Effects are mixed; no uniform improvement is established. The original workbook explicitly has 755 temperature-0.7 answers and one reused temperature-0 answer. The earlier source did not directly capture temperature; later replacement provenance retrospectively attributes its source run to temperature 0. This is not a pure controlled temperature comparison. top_p is not supplied for GC LLM and is not inferred from the Llama discussion. Cleaned responses are user-edited workbook strings, not new generations at a third temperature.

## language breakdown

| Metric | language | Tasks | Previous | Workbook | Cleaned |
|---|---|---:|---:|---:|---:|
| M1 | en | 39 | 0.6667 | 0.7564 | 0.8026 |
| M1 | fr | 37 | 0.6162 | 0.5838 | 0.5568 |
| M2 | en | 130 | 0.4877 | 0.4608 | 0.4738 |
| M2 | fr | 104 | 0.4010 | 0.3779 | 0.3856 |
| M3 | en | 177 | 0.4678 | 0.4960 | 0.4927 |
| M3 | fr | 150 | 0.3860 | 0.3300 | 0.3113 |
| M4 | en | 50 | 0.6180 | 0.6100 | 0.5860 |
| M4 | fr | 62 | 0.5855 | 0.4774 | 0.4919 |
| M5 | en | 95 | 0.4474 | 0.4916 | 0.4842 |
| M5 | fr | 79 | 0.4835 | 0.4101 | 0.4051 |
| M6 | en | 137 | 0.4307 | 0.4358 | 0.4380 |
| M6 | fr | 116 | 0.3836 | 0.3267 | 0.3328 |
| M7 | en | 349 | 0.5000 | 0.4980 | 0.5026 |
| M7 | fr | 289 | 0.4484 | 0.3727 | 0.3806 |

## metric_role breakdown

| Metric | metric_role | Tasks | Previous | Workbook | Cleaned |
|---|---|---:|---:|---:|---:|
| M1 | primary | 59 | 0.6746 | 0.6898 | 0.7186 |
| M1 | secondary | 17 | 0.5294 | 0.6118 | 0.5588 |
| M2 | primary | 161 | 0.4559 | 0.4280 | 0.4348 |
| M2 | secondary | 73 | 0.4342 | 0.4151 | 0.4342 |
| M3 | primary | 233 | 0.4386 | 0.4210 | 0.4146 |
| M3 | secondary | 94 | 0.4096 | 0.4170 | 0.3968 |
| M4 | primary | 61 | 0.5607 | 0.4918 | 0.4885 |
| M4 | secondary | 51 | 0.6471 | 0.5902 | 0.5882 |
| M5 | primary | 72 | 0.4792 | 0.4569 | 0.4708 |
| M5 | secondary | 102 | 0.4529 | 0.4529 | 0.4324 |
| M6 | primary | 95 | 0.4000 | 0.4074 | 0.4274 |
| M6 | secondary | 158 | 0.4146 | 0.3728 | 0.3671 |
| M7 | primary | 75 | 0.4800 | 0.4600 | 0.4560 |
| M7 | secondary | 563 | 0.4762 | 0.4387 | 0.4462 |

## cleaning_changed_answer breakdown

| Metric | cleaning_changed_answer | Tasks | Previous | Workbook | Cleaned |
|---|---|---:|---:|---:|---:|
| M1 | False | 55 | 0.6673 | 0.7273 | 0.7455 |
| M1 | True | 21 | 0.5762 | 0.5286 | 0.5190 |
| M2 | False | 125 | 0.4856 | 0.4640 | 0.4728 |
| M2 | True | 109 | 0.4073 | 0.3780 | 0.3908 |
| M3 | False | 199 | 0.4518 | 0.4628 | 0.4432 |
| M3 | True | 128 | 0.3969 | 0.3531 | 0.3570 |
| M4 | False | 83 | 0.6096 | 0.5940 | 0.5928 |
| M4 | True | 29 | 0.5724 | 0.3724 | 0.3655 |
| M5 | False | 129 | 0.4651 | 0.4930 | 0.4876 |
| M5 | True | 45 | 0.4600 | 0.3444 | 0.3356 |
| M6 | False | 157 | 0.4153 | 0.4357 | 0.4363 |
| M6 | True | 96 | 0.3990 | 0.3042 | 0.3135 |
| M7 | False | 397 | 0.4773 | 0.4668 | 0.4693 |
| M7 | True | 241 | 0.4755 | 0.3992 | 0.4112 |

## Configuration and execution limits

All pairs match question, reference, supporting context, language, assignment role, judge deployment and fixed rubric/template checksums. The judge used omitted-temperature/server-default sampling across all conditions. Determinism is not established, and timing/load/cache conditions vary. Earlier GC LLM/Llama runs were sequential while workbook and cleaned runs used four workers. Generation prompts, seeds, exact revisions and all inference controls were not supplied for both original conditions. Missing source metadata is not borrowed from other models or changed responses. No extra normalization or arbitrary overall score is computed. Known rubric interpretation limitations and pending human calibration remain in force.

Cleaned-run scoring HTTP attempts: 1814; discovery calls: 1; HTTP outcomes: {'200': 1814}; API-reported tokens: {'completion_tokens': 1018196, 'prompt_tokens': 2938004, 'total_tokens': 3956200}.

Rubric SHA-256: `bb9889807b7babc8feed6a97ddd0c12c0fa334627e5d295017167fbd0a767cb2`

Evaluator-template SHA-256: `ecb714aa746f7bdce82d86fd9bcc288d4e26ffd15cfa210bbd19a356e095793f`

## Files

`gc_llm_three_run_comparison.xlsx`: side-by-side scores, all three paired contrasts, full answers/reasons, language/role groups, cleaning-affected cases, changed/unchanged decomposition and question-level score mappings. Each table is also exported as CSV/JSONL. `all_5442_individual_judgments.*` retains the full original evaluation metadata. `comparison_manifest.json` records source hashes and counts. All outputs remain AI-provisional, pending calibration.
