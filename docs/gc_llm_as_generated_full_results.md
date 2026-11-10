# GC LLM as-generated full evaluation

AI-provisional, pending calibration

Run: `gc_llm_full_as_generated_20261106_v2`. Completed 1,814/1,814 unique question?model?metric evaluations: zero final failures or missing tasks. 756 questions (404 EN / 352 FR), 756 primary and 1,058 secondary assignments. All 756 response strings match the original JSONL and Excel; no filtering, rewriting, shortening, deduplication or regeneration.

## Per-metric comparison

| Metric | Tasks | GC LLM mean | Llama mean | GC minus Llama |
|---|---:|---:|---:|---:|
| M1 | 76 | 0.6421 | 0.9053 | -0.2632 |
| M2 | 234 | 0.4491 | 0.6735 | -0.2244 |
| M3 | 327 | 0.4303 | 0.6661 | -0.2358 |
| M4 | 112 | 0.6000 | 0.8634 | -0.2634 |
| M5 | 174 | 0.4638 | 0.6897 | -0.2259 |
| M6 | 253 | 0.4091 | 0.6561 | -0.2470 |
| M7 | 638 | 0.4766 | 0.6989 | -0.2223 |

## language breakdown

| Metric | language | Tasks | GC mean | Llama mean |
|---|---|---:|---:|---:|
| M1 | en | 39 | 0.6667 | 0.8897 |
| M1 | fr | 37 | 0.6162 | 0.9216 |
| M2 | en | 130 | 0.4877 | 0.7077 |
| M2 | fr | 104 | 0.4010 | 0.6308 |
| M3 | en | 177 | 0.4678 | 0.7056 |
| M3 | fr | 150 | 0.3860 | 0.6193 |
| M4 | en | 50 | 0.6180 | 0.8720 |
| M4 | fr | 62 | 0.5855 | 0.8565 |
| M5 | en | 95 | 0.4474 | 0.7263 |
| M5 | fr | 79 | 0.4835 | 0.6456 |
| M6 | en | 137 | 0.4307 | 0.6781 |
| M6 | fr | 116 | 0.3836 | 0.6302 |
| M7 | en | 349 | 0.5000 | 0.7301 |
| M7 | fr | 289 | 0.4484 | 0.6612 |

## metric_role breakdown

| Metric | metric_role | Tasks | GC mean | Llama mean |
|---|---|---:|---:|---:|
| M1 | primary | 59 | 0.6746 | 0.9017 |
| M1 | secondary | 17 | 0.5294 | 0.9176 |
| M2 | primary | 161 | 0.4559 | 0.6665 |
| M2 | secondary | 73 | 0.4342 | 0.6890 |
| M3 | primary | 233 | 0.4386 | 0.6639 |
| M3 | secondary | 94 | 0.4096 | 0.6713 |
| M4 | primary | 61 | 0.5607 | 0.8557 |
| M4 | secondary | 51 | 0.6471 | 0.8725 |
| M5 | primary | 72 | 0.4792 | 0.7222 |
| M5 | secondary | 102 | 0.4529 | 0.6667 |
| M6 | primary | 95 | 0.4000 | 0.6821 |
| M6 | secondary | 158 | 0.4146 | 0.6405 |
| M7 | primary | 75 | 0.4800 | 0.7440 |
| M7 | secondary | 563 | 0.4762 | 0.6929 |

## truncated analysis

| Metric | truncated | Tasks | GC mean |
|---|---|---:|---:|
| M1 | False | 46 | 0.7217 |
| M1 | True | 30 | 0.5200 |
| M2 | False | 131 | 0.5137 |
| M2 | True | 103 | 0.3670 |
| M3 | False | 171 | 0.5105 |
| M3 | True | 156 | 0.3423 |
| M4 | False | 81 | 0.6877 |
| M4 | True | 31 | 0.3710 |
| M5 | False | 135 | 0.4800 |
| M5 | True | 39 | 0.4077 |
| M6 | False | 141 | 0.4929 |
| M6 | True | 112 | 0.3036 |
| M7 | False | 367 | 0.5343 |
| M7 | True | 271 | 0.3985 |

## analysis_repetition_flag analysis

| Metric | analysis_repetition_flag | Tasks | GC mean |
|---|---|---:|---:|
| M1 | False | 44 | 0.7182 |
| M1 | True | 32 | 0.5375 |
| M2 | False | 122 | 0.5213 |
| M2 | True | 112 | 0.3705 |
| M3 | False | 155 | 0.5135 |
| M3 | True | 172 | 0.3552 |
| M4 | False | 71 | 0.7014 |
| M4 | True | 41 | 0.4244 |
| M5 | False | 120 | 0.5008 |
| M5 | True | 54 | 0.3815 |
| M6 | False | 119 | 0.5017 |
| M6 | True | 134 | 0.3269 |
| M7 | False | 329 | 0.5468 |
| M7 | True | 309 | 0.4019 |

All 305 length-limited outputs were retained (742 metric tasks), alongside 451 stop-terminated outputs (1,072 tasks). The exploratory repetition proxy flags 350/756 responses: at least 40 Unicode word tokens and at least 30% repeated four-grams. Original repetition-audit flags were not supplied. These derived labels are analysis-only, never judge instructions, exclusions or claims of a validated audit. Subgroup differences are descriptive and confounded by question/metric/language mix; they do not establish causal effects.

## Execution and failures

Recorded scoring HTTP attempts: 1831; discovery requests: 4. HTTP event counts: {'200': 1814, '500': 15, '403': 2}. Reported scoring usage: {'completion_tokens': 976122, 'prompt_tokens': 3238136, 'total_tokens': 4214258}. Seven logical failed attempts were recovered through identical-configuration checkpoint resumption. Failed responses with no reported usage are unknown consumption, not zero. Separate model-metadata diagnostics and the 98-token temperature-support test are outside scoring counts.

Observed successful/failed logical-attempt latency statistics: {"evaluations": 1814, "successes": 1814, "errors": 0, "error_rate": 0.0, "scoring_http_attempts": 1831, "saved_evaluation_attempts": 1821, "failed_evaluation_attempts": 7, "mean_evaluation_latency_seconds": 3.7242010639766785, "median_evaluation_latency_seconds": 3.4195957001065835, "min_evaluation_latency_seconds": 1.3266431998927146, "max_evaluation_latency_seconds": 215.82011990004685, "projected_sequential_seconds_1814": 6755.700730053695, "projection_note": "Pilot sample conditional on current gateway load and short selected answers; not measured full-run throughput. No arbitrary overall score.", "provisional": true}

## Comparability and limitations

The same fixed evaluator, judge request configuration, benchmark evidence, 42 steps and 35 rubric bands were used for both models. Each metric was independently scored. Scores already use the evaluator scale; no second normalization or combined Canadian-ness score was calculated. Question/metric paired records include both answers and explanations. Supporting context is evaluation evidence, not a claim about the model generation input or a verified verbatim quotation.

GC generation: max_new_tokens=1024, revision `58277e94d16ccf486c1702c0aac8115c69448585`, generation run `20261106T144233Z-f941260c`. Temperature, decoding controls, seed and generation prompt template were not supplied. Llama revision and generation settings were unavailable, so strict generation-condition parity cannot be established. The as-generated comparison includes observed truncation and repetition.

Judge temperature was omitted in every scoring request, matching Llama. The numeric server default is unknown; model metadata did not disclose it and detailed model-info access was denied. A separate temperature=0 test returned HTTP 200, establishing parameter acceptance only; no scoring configuration was changed. Server defaults and judge nondeterminism remain reproducibility limitations.

- Booster-seat M3 conditional-guidance credit and M6 extra-detail deductions remain inconsistent.
- Optional reference enrichment and scoring-band justification are not consistently handled.
- Institutional duty timing versus factual recall and exact within-band scores are human calibration decisions.
- Some ancillary factual claims and reference dates remain unverified by the supplied summaries.
- Evidence verification is the imported user benchmark attestation, not new local independent verification.
- Gateway-default sampling is not proven deterministic; weights/revision and deployment limits are not independently attested.
- No human calibration, team approval, overall weighting policy or scientific-validity approval is implied.

## Frozen provenance

Experiment SHA-256: `200ad4198f01bf640b9897e0b5894c28105b8870f5d080b88e09764981f1222d`

Rubric SHA-256 unchanged: `bb9889807b7babc8feed6a97ddd0c12c0fa334627e5d295017167fbd0a767cb2`

Evaluator-template SHA-256 unchanged: `ecb714aa746f7bdce82d86fd9bcc288d4e26ffd15cfa210bbd19a356e095793f`

Existing execution authorization is recorded separately; scientific approval, team approval and empirical calibration remain false. Original Llama results and both pilots passed protected-file checksum verification.

## Files

- `as_generated_comparison.xlsx`: complete workbook with original responses, provenance, all scores/reasons, subgroups and 1,814 matched Llama pairs.
- `as_generated_results.jsonl` / `.csv`: 1,814 results with generation metadata.
- `all_results.jsonl` / `.csv`, `primary_results.*`, `secondary_results.*`, `all_metric_summaries.*`: standard compatible exports.
- `completion_repetition_subgroups.*`, `gc_llm_vs_llama_question_metric_pairs.*`, `gc_llm_vs_llama_metric_comparisons.*`: complete subgroup and paired analysis.
- `attempts.*`, `retry_report.*`, `sessions/`, `raw/`, `records/`: all attempts, failures/retries and judge responses.
- `completion_verification.json`, `locked_experiment.json`, and the run-specific config directory: integrity and authorization records.

## Observed scoring patterns

GC LLM has a lower descriptive mean than Llama on every metric (paired differences approximately -0.222 to -0.263). Length-limited outputs and exploratory repetition-flagged outputs each have lower means than their respective comparison groups across all seven metrics. The largest complete/truncated gap appears in M4 (0.688 versus 0.371). These are observed associations, not causal estimates or calibrated model rankings. All problematic outputs remain included. No score-driven exclusions or post-hoc response corrections were applied.

The latency statistics above are measured across full-run logical attempts, including recovered failures; any inherited projection-note wording referring to a pilot is a legacy exporter label and is not evidence of production throughput.
