# Llama temperature-labelled run comparison

AI-provisional, pending calibration

Both runs completed 1,814/1,814 metric judgments over the same 756 questions. The new run has zero final failed or missing tasks. No additional scoring requests were made for this comparison. Temperature 0 and 0.7 labels follow the user identification; the supplied Llama generation sources do not independently document those temperatures.

| Metric | Tasks | Temp 0 mean | Temp 0.7 mean | Difference |
|---|---:|---:|---:|---:|
| M1 | 76 | 0.9053 | 0.9158 | +0.0105 |
| M2 | 234 | 0.6735 | 0.6714 | -0.0021 |
| M3 | 327 | 0.6661 | 0.6624 | -0.0037 |
| M4 | 112 | 0.8634 | 0.8759 | +0.0125 |
| M5 | 174 | 0.6897 | 0.6713 | -0.0184 |
| M6 | 253 | 0.6561 | 0.6455 | -0.0107 |
| M7 | 638 | 0.6989 | 0.6886 | -0.0103 |

## Interpretation

Differences are small and mixed: the new run is higher on M1 and M4 and lower on the other five metrics. The largest descriptive decline is M5 (about 0.0184 on the 0–1 scale). This is not evidence of a consistent improvement or decline, statistical equivalence, or a causal temperature effect. All individual pairs and reasons are retained; English/French and primary/secondary comparisons are exported separately.

The answer strings are identical for 10 questions, covering 18 metric pairs. 4 of those identical-answer metric pairs have different scores on repeat judging. This demonstrates observed repeat-judgment variation; the small control subset cannot establish an uncertainty bound for all changed answers.

## top_p and inference provenance

Neither supplied Llama source records top_p. The value 0.95 is retained as a retrospective user report, not independently verified per-run generation metadata. The earlier temperature-zero value cannot be recovered from these files, and the current workbook does not establish the temperature-0.7 top_p either. No library/provider default was assumed. The original generation command, configuration or generation manifest is needed to establish whether both runs used 0.95.

These are answer-generation settings. The gpt-oss-120b judge still used omitted temperature/server-default sampling in both scoring runs. Its effective temperature/top_p were not recorded and should not be confused with the tested Llama generation parameters.

## Comparability limits

The rubric, fixed 42 steps, 35 bands, v2 template, judge deployment and question/reference/context/assignment alignment match. The earlier run used one worker and the new run four; execution load, timing and caching differed. Seeds, exact generation prompts, model checkpoint revisions and other generation controls were not supplied for both runs. Therefore isolate neither temperature nor top_p as the sole explanation. No arbitrary overall Canadian-ness score, scientific calibration or team approval is claimed.

Rubric SHA-256: `bb9889807b7babc8feed6a97ddd0c12c0fa334627e5d295017167fbd0a767cb2`

Evaluator-template SHA-256: `ecb714aa746f7bdce82d86fd9bcc288d4e26ffd15cfa210bbd19a356e095793f`

## Files

`llama_temperature_0_vs_07.xlsx`, `question_metric_comparisons.csv`/`.jsonl`, `metric_language_role_comparisons.csv`/`.jsonl`, `generation_settings_annotation.json`, `comparison_manifest.json`. Existing frozen run artifacts were not modified.
