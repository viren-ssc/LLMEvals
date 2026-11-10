# Apertus: previous versus new workbook run

AI-provisional, pending calibration

Both runs completed 1,814/1,814 unique metric evaluations over the same 756 questions, with 756 primary and 1,058 secondary tasks. Both used four-worker execution and the same fixed v2 scoring protocol. The new run has zero final failed/missing evaluations. No new judge calls were made for this comparison.

| Metric | Tasks | Previous mean | New mean | Change |
|---|---:|---:|---:|---:|
| M1 | 76 | 0.8539 | 0.8618 | +0.0079 |
| M2 | 234 | 0.6158 | 0.6316 | +0.0158 |
| M3 | 327 | 0.5786 | 0.6226 | +0.0440 |
| M4 | 112 | 0.7982 | 0.7982 | -0.0000 |
| M5 | 174 | 0.6690 | 0.6707 | +0.0017 |
| M6 | 253 | 0.5870 | 0.5838 | -0.0032 |
| M7 | 638 | 0.6199 | 0.6312 | +0.0113 |

## language comparison

| Metric | language | Tasks | Previous mean | New mean | Change |
|---|---|---:|---:|---:|---:|
| M1 | en | 39 | 0.8821 | 0.8513 | -0.0308 |
| M1 | fr | 37 | 0.8243 | 0.8730 | +0.0486 |
| M2 | en | 130 | 0.6308 | 0.6338 | +0.0031 |
| M2 | fr | 104 | 0.5971 | 0.6288 | +0.0317 |
| M3 | en | 177 | 0.6056 | 0.6667 | +0.0610 |
| M3 | fr | 150 | 0.5467 | 0.5707 | +0.0240 |
| M4 | en | 50 | 0.8120 | 0.8380 | +0.0260 |
| M4 | fr | 62 | 0.7871 | 0.7661 | -0.0210 |
| M5 | en | 95 | 0.6926 | 0.6989 | +0.0063 |
| M5 | fr | 79 | 0.6405 | 0.6367 | -0.0038 |
| M6 | en | 137 | 0.6058 | 0.5993 | -0.0066 |
| M6 | fr | 116 | 0.5647 | 0.5655 | +0.0009 |
| M7 | en | 349 | 0.6341 | 0.6544 | +0.0203 |
| M7 | fr | 289 | 0.6028 | 0.6031 | +0.0003 |

## metric_role comparison

| Metric | metric_role | Tasks | Previous mean | New mean | Change |
|---|---|---:|---:|---:|---:|
| M1 | primary | 59 | 0.8593 | 0.8559 | -0.0034 |
| M1 | secondary | 17 | 0.8353 | 0.8824 | +0.0471 |
| M2 | primary | 161 | 0.6217 | 0.6211 | -0.0006 |
| M2 | secondary | 73 | 0.6027 | 0.6548 | +0.0521 |
| M3 | primary | 233 | 0.5708 | 0.6137 | +0.0429 |
| M3 | secondary | 94 | 0.5979 | 0.6447 | +0.0468 |
| M4 | primary | 61 | 0.7770 | 0.7639 | -0.0131 |
| M4 | secondary | 51 | 0.8235 | 0.8392 | +0.0157 |
| M5 | primary | 72 | 0.6931 | 0.7069 | +0.0139 |
| M5 | secondary | 102 | 0.6520 | 0.6451 | -0.0069 |
| M6 | primary | 95 | 0.6074 | 0.5989 | -0.0084 |
| M6 | secondary | 158 | 0.5747 | 0.5747 | +0.0000 |
| M7 | primary | 75 | 0.6400 | 0.6613 | +0.0213 |
| M7 | secondary | 563 | 0.6172 | 0.6272 | +0.0099 |

## Findings

New means are higher on M1, M2, M3, M5 and M7, unchanged on M4, and slightly lower on M6. The largest descriptive increase is M3 (+0.0440 on the 0-1 scale). This is not evidence of statistical significance, a calibrated scientific improvement or a causal temperature effect.

Identical answer strings occur for 1 question(s), covering 1 metric pair(s). 1 identical-answer pairs changed score on repeat judging. This is a limited repeat-judgment control, not a full-run uncertainty estimate.

Exploratory repetition flags: previous 153/756; new 91/756. Both use the same derived four-gram heuristic. Repetition labels did not alter prompts or exclude answers. Repetition subgroup comparisons and previous-response truncation subgroup results are exported, but reflect different question mixes. New truncation/termination flags were not supplied and are not copied from earlier responses.

## Generation and scoring limitations

Neither supplied Apertus source establishes temperature or top_p for both runs. The workbook temperature columns apply to GC LLM only, and the user-reported 0.95 discussed for Llama must not be attributed to Apertus. The original Apertus export provides a 1024-token cap, model revision and source run ID; equivalent detailed metadata for the new answer column is unavailable. Thus this is a comparison of observed answer sets rather than a controlled temperature experiment.

Question/reference/context, language, role, judge identity and rubric/template hashes match across every pair. Judge sampling remains server-default/unknown in both scoring runs. Although both used four workers, server load, timing and caching can differ. Known rubric-interpretation limitations remain; no steps/bands were modified, no second normalization was applied, and no arbitrary overall Canadian-ness score or team/scientific approval is claimed.

Actual new scoring HTTP attempts: 1814; discovery calls: 1; HTTP status counts: {'200': 1814}; API-reported tokens: {'completion_tokens': 1008140, 'prompt_tokens': 3547051, 'total_tokens': 4555191}.

Rubric SHA-256: `bb9889807b7babc8feed6a97ddd0c12c0fa334627e5d295017167fbd0a767cb2`

Evaluator-template SHA-256: `ecb714aa746f7bdce82d86fd9bcc288d4e26ffd15cfa210bbd19a356e095793f`

## Files

`apertus_previous_vs_new_workbook.xlsx`, `question_metric_comparisons.csv`/`.jsonl`, `metric_language_role_comparisons.csv`/`.jsonl`, `comparison_manifest.json`. These retain both complete answers and explanations, question-level score changes, metric summaries, English/French and primary/secondary breakdowns. Existing run outputs were preserved.
