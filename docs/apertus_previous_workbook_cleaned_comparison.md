# apertus: previous, workbook and cleaned responses

AI-provisional, pending calibration

All three runs completed 1,814/1,814 evaluations over the same 756 questions: 756 primary and 1,058 secondary tasks per run. This analysis aligns all 1,814 question-metric triples and retains every one of the 5,442 scores and explanations. No new judge calls were made and no source answer, previous judgment or frozen run manifest was modified.

| Metric | Tasks | Previous | Workbook | Cleaned | Cleaned minus workbook |
|---|---:|---:|---:|---:|---:|
| M1 | 76 | 0.8539 | 0.8618 | 0.8605 | -0.0013 |
| M2 | 234 | 0.6158 | 0.6316 | 0.6282 | -0.0034 |
| M3 | 327 | 0.5786 | 0.6226 | 0.6141 | -0.0086 |
| M4 | 112 | 0.7982 | 0.7982 | 0.7920 | -0.0062 |
| M5 | 174 | 0.6690 | 0.6707 | 0.6701 | -0.0006 |
| M6 | 253 | 0.5870 | 0.5838 | 0.5798 | -0.0040 |
| M7 | 638 | 0.6199 | 0.6312 | 0.6359 | +0.0047 |

## Cleaning and repeat-judgment variation

Cleaning changes 140 answers, covering 312 metric judgments. Of the 1502 judgments with identical answer text, 748 (49.8%) have different scores on repeat judging. Thus full-set differences include changes on unedited responses and cannot be attributed solely to cleaning or interpreted as proof of judge repetition bias. The changed/unchanged decomposition exports each subset contribution to every metric mean shift. Edited answers may also differ in factual coverage or meaning; no cleaning algorithm or full edit provenance was supplied. The unchanged subset is descriptive evidence of repeatability limits, not a calibrated causal correction for edited-response scores.

## language breakdown

| Metric | language | Tasks | Previous | Workbook | Cleaned |
|---|---|---:|---:|---:|---:|
| M1 | en | 39 | 0.8821 | 0.8513 | 0.8590 |
| M1 | fr | 37 | 0.8243 | 0.8730 | 0.8622 |
| M2 | en | 130 | 0.6308 | 0.6338 | 0.6446 |
| M2 | fr | 104 | 0.5971 | 0.6288 | 0.6077 |
| M3 | en | 177 | 0.6056 | 0.6667 | 0.6514 |
| M3 | fr | 150 | 0.5467 | 0.5707 | 0.5700 |
| M4 | en | 50 | 0.8120 | 0.8380 | 0.8200 |
| M4 | fr | 62 | 0.7871 | 0.7661 | 0.7694 |
| M5 | en | 95 | 0.6926 | 0.6989 | 0.6958 |
| M5 | fr | 79 | 0.6405 | 0.6367 | 0.6392 |
| M6 | en | 137 | 0.6058 | 0.5993 | 0.6146 |
| M6 | fr | 116 | 0.5647 | 0.5655 | 0.5388 |
| M7 | en | 349 | 0.6341 | 0.6544 | 0.6645 |
| M7 | fr | 289 | 0.6028 | 0.6031 | 0.6014 |

## metric_role breakdown

| Metric | metric_role | Tasks | Previous | Workbook | Cleaned |
|---|---|---:|---:|---:|---:|
| M1 | primary | 59 | 0.8593 | 0.8559 | 0.8508 |
| M1 | secondary | 17 | 0.8353 | 0.8824 | 0.8941 |
| M2 | primary | 161 | 0.6217 | 0.6211 | 0.6155 |
| M2 | secondary | 73 | 0.6027 | 0.6548 | 0.6562 |
| M3 | primary | 233 | 0.5708 | 0.6137 | 0.5961 |
| M3 | secondary | 94 | 0.5979 | 0.6447 | 0.6585 |
| M4 | primary | 61 | 0.7770 | 0.7639 | 0.7672 |
| M4 | secondary | 51 | 0.8235 | 0.8392 | 0.8216 |
| M5 | primary | 72 | 0.6931 | 0.7069 | 0.6986 |
| M5 | secondary | 102 | 0.6520 | 0.6451 | 0.6500 |
| M6 | primary | 95 | 0.6074 | 0.5989 | 0.6084 |
| M6 | secondary | 158 | 0.5747 | 0.5747 | 0.5627 |
| M7 | primary | 75 | 0.6400 | 0.6613 | 0.6733 |
| M7 | secondary | 563 | 0.6172 | 0.6272 | 0.6309 |

## cleaning_changed_answer breakdown

| Metric | cleaning_changed_answer | Tasks | Previous | Workbook | Cleaned |
|---|---|---:|---:|---:|---:|
| M1 | False | 59 | 0.8559 | 0.8525 | 0.8576 |
| M1 | True | 17 | 0.8471 | 0.8941 | 0.8706 |
| M2 | False | 199 | 0.6131 | 0.6307 | 0.6231 |
| M2 | True | 35 | 0.6314 | 0.6371 | 0.6571 |
| M3 | False | 270 | 0.5748 | 0.6174 | 0.6081 |
| M3 | True | 57 | 0.5965 | 0.6474 | 0.6421 |
| M4 | False | 90 | 0.8056 | 0.8111 | 0.8022 |
| M4 | True | 22 | 0.7682 | 0.7455 | 0.7500 |
| M5 | False | 152 | 0.6612 | 0.6671 | 0.6678 |
| M5 | True | 22 | 0.7227 | 0.6955 | 0.6864 |
| M6 | False | 206 | 0.5801 | 0.5932 | 0.5869 |
| M6 | True | 47 | 0.6170 | 0.5426 | 0.5489 |
| M7 | False | 526 | 0.6122 | 0.6321 | 0.6359 |
| M7 | True | 112 | 0.6562 | 0.6268 | 0.6357 |

## Configuration and execution limits

All pairs match question, reference, supporting context, language, assignment role, judge deployment and fixed rubric/template checksums. The judge used omitted-temperature/server-default sampling across all conditions. Determinism is not established, and timing/load/cache conditions vary. Earlier GC LLM/Llama runs were sequential while workbook and cleaned runs used four workers. Generation prompts, seeds, exact revisions and all inference controls were not supplied for both original conditions. Missing source metadata is not borrowed from other models or changed responses. No extra normalization or arbitrary overall score is computed. Known rubric interpretation limitations and pending human calibration remain in force.

Cleaned-run scoring HTTP attempts: 1814; discovery calls: 1; HTTP outcomes: {'200': 1814}; API-reported tokens: {'completion_tokens': 1017204, 'prompt_tokens': 3498650, 'total_tokens': 4515854}.

Rubric SHA-256: `bb9889807b7babc8feed6a97ddd0c12c0fa334627e5d295017167fbd0a767cb2`

Evaluator-template SHA-256: `ecb714aa746f7bdce82d86fd9bcc288d4e26ffd15cfa210bbd19a356e095793f`

## Files

`apertus_three_run_comparison.xlsx`: side-by-side scores, all three paired contrasts, full answers/reasons, language/role groups, cleaning-affected cases, changed/unchanged decomposition and question-level score mappings. Each table is also exported as CSV/JSONL. `all_5442_individual_judgments.*` retains the full original evaluation metadata. `comparison_manifest.json` records source hashes and counts. All outputs remain AI-provisional, pending calibration.
