# Apertus as-generated evaluation analysis

**AI-provisional, pending calibration**

Completed **1,814/1,814** unique metric tasks for **756 questions**: **756 primary**, **1,058 secondary**, no final failures or missing tasks. All original answer strings are unchanged. All 324 length-limited outputs and 432 complete outputs were retained. Four-worker scheduling reused the unchanged scorer, rubric and independent per-metric checkpoint engine.

## Per-metric comparison

| Metric | Tasks | Apertus | Llama | GC LLM |
|---|---:|---:|---:|---:|
| M1 | 76 | 0.8539 | 0.9053 | 0.6421 |
| M2 | 234 | 0.6158 | 0.6735 | 0.4491 |
| M3 | 327 | 0.5786 | 0.6661 | 0.4303 |
| M4 | 112 | 0.7982 | 0.8634 | 0.6000 |
| M5 | 174 | 0.6690 | 0.6897 | 0.4638 |
| M6 | 253 | 0.5870 | 0.6561 | 0.4091 |
| M7 | 638 | 0.6199 | 0.6989 | 0.4766 |

## language breakdown

| Metric | language | Tasks | Apertus mean |
|---|---|---:|---:|
| M1 | en | 39 | 0.8821 |
| M1 | fr | 37 | 0.8243 |
| M2 | en | 130 | 0.6308 |
| M2 | fr | 104 | 0.5971 |
| M3 | en | 177 | 0.6056 |
| M3 | fr | 150 | 0.5467 |
| M4 | en | 50 | 0.8120 |
| M4 | fr | 62 | 0.7871 |
| M5 | en | 95 | 0.6926 |
| M5 | fr | 79 | 0.6405 |
| M6 | en | 137 | 0.6058 |
| M6 | fr | 116 | 0.5647 |
| M7 | en | 349 | 0.6341 |
| M7 | fr | 289 | 0.6028 |

## metric_role breakdown

| Metric | metric_role | Tasks | Apertus mean |
|---|---|---:|---:|
| M1 | primary | 59 | 0.8593 |
| M1 | secondary | 17 | 0.8353 |
| M2 | primary | 161 | 0.6217 |
| M2 | secondary | 73 | 0.6027 |
| M3 | primary | 233 | 0.5708 |
| M3 | secondary | 94 | 0.5979 |
| M4 | primary | 61 | 0.7770 |
| M4 | secondary | 51 | 0.8235 |
| M5 | primary | 72 | 0.6931 |
| M5 | secondary | 102 | 0.6520 |
| M6 | primary | 95 | 0.6074 |
| M6 | secondary | 158 | 0.5747 |
| M7 | primary | 75 | 0.6400 |
| M7 | secondary | 563 | 0.6172 |

## truncated analysis

| Metric | truncated | Tasks | Mean |
|---|---|---:|---:|
| M1 | False | 41 | 0.8488 |
| M1 | True | 35 | 0.8600 |
| M2 | False | 150 | 0.6020 |
| M2 | True | 84 | 0.6405 |
| M3 | False | 193 | 0.5383 |
| M3 | True | 134 | 0.6366 |
| M4 | False | 59 | 0.8356 |
| M4 | True | 53 | 0.7566 |
| M5 | False | 99 | 0.6677 |
| M5 | True | 75 | 0.6707 |
| M6 | False | 135 | 0.5770 |
| M6 | True | 118 | 0.5983 |
| M7 | False | 382 | 0.5979 |
| M7 | True | 256 | 0.6527 |

## analysis_repetition_flag analysis

| Metric | analysis_repetition_flag | Tasks | Mean |
|---|---|---:|---:|
| M1 | False | 55 | 0.8636 |
| M1 | True | 21 | 0.8286 |
| M2 | False | 200 | 0.6170 |
| M2 | True | 34 | 0.6088 |
| M3 | False | 267 | 0.5670 |
| M3 | True | 60 | 0.6300 |
| M4 | False | 80 | 0.8225 |
| M4 | True | 32 | 0.7375 |
| M5 | False | 146 | 0.6829 |
| M5 | True | 28 | 0.5964 |
| M6 | False | 209 | 0.5871 |
| M6 | True | 44 | 0.5864 |
| M7 | False | 526 | 0.6152 |
| M7 | True | 112 | 0.6420 |

## Interpretation

Apertus has a descriptive mean between Llama and GC LLM for all seven metrics. These are observed AI-judge results, not calibrated scientific rankings. Completion/repetition groups are exploratory associations with different question mixes; no causal interpretation is justified. Repetition labels are derived four-gram heuristics rather than supplied original audit flags. No output was excluded and no combined Canadian-ness score was calculated.

Length-limited questions cover 755 metric tasks; complete questions cover 1059. English/French task counts are {'fr': 837, 'en': 977}; question counts remain 404 EN / 352 FR.

## Execution accounting

Scoring HTTP attempts: 1818; discovery requests: 2; recorded HTTP outcomes: {'200': 1814, '403': 2, 'network_or_timeout': 2}. API-reported usage: {'completion_tokens': 1017200, 'prompt_tokens': 3388214, 'total_tokens': 4405414}. Four failed logical attempts were recovered by identical-configuration resumption. Usage not reported on error responses is unknown, not zero.

## Configuration and limitations

Rubric SHA-256 unchanged: `bb9889807b7babc8feed6a97ddd0c12c0fa334627e5d295017167fbd0a767cb2`

Evaluator-template SHA-256 unchanged: `ecb714aa746f7bdce82d86fd9bcc288d4e26ffd15cfa210bbd19a356e095793f`

Judge gpt-oss-120b uses the same omitted-temperature scoring protocol as Llama and GC LLM; the numeric server default remains unknown. Apertus uses four-worker execution, whereas earlier runs were sequential, so timing/load/cache conditions differ. Generation max_new_tokens=1024; revision and generation run ID are preserved in metadata. Other generation inference controls were not supplied. Strict generation-condition parity and deterministic judgments cannot be established. Supporting context is evaluation evidence, not the tested model input or a verified verbatim quotation.

- Booster-seat M3 conditional-guidance credit and M6 extra-detail deductions remain inconsistent.
- Optional reference enrichment and scoring-band justification are not consistently handled.
- Institutional duty timing versus factual recall and exact within-band scores are human calibration decisions.
- Some ancillary factual claims and reference dates remain unverified by the supplied summaries.
- Evidence verification is the imported user benchmark attestation, not new local independent verification.
- Gateway-default sampling is not proven deterministic; weights/revision and deployment limits are not independently attested.
- No human calibration, team approval, overall weighting policy or scientific-validity approval is implied.

## Files

- `as_generated_comparison.xlsx`: comprehensive workbook including original responses, all judgments/explanations, generation metadata, subgroup analyses, matched Llama and GC LLM pairs.
- `as_generated_results.jsonl` / `.csv`: full individual results with generation provenance.
- `all_metric_summaries.csv`: per-metric, English/French and role summaries.
- `primary_results.*` and `secondary_results.*`: separate assignment-role exports.
- `completion_repetition_subgroups.*`: retained length-limited and exploratory repetition analyses.
- `apertus_model_comparison_pairs.*`, `apertus_model_comparison_summaries.*`: question-level and aggregate comparisons.
- `attempts.*`, `retry_report.*`, `sessions/`, `raw/`, `records/`: immutable raw judgments and failure/retry accounting.
- `completion_verification.json`: exact source preservation, inventory, payload and configuration checks.
