# Completed Llama experiment: llama_full_20261106_v2

**AI-provisional, pending calibration. 1,814/1,814 successful evaluations; zero failed or missing tasks.** Execution permission was recorded; no scientific validity, team approval or empirical calibration is claimed.

## Scope and integrity

756 unchanged Llama answers were evaluated against every applicable metric: 756 primary and 1,058 secondary assignments. The dataset contains 404 English and 352 French questions, producing 977 EN and 837 FR metric scores. Each question/model/metric key is unique. No answers were regenerated and no overall Canadian-ness score was calculated.

Judge: `gpt-oss-120b`; evaluator: `final-json-factory-v2`; rubric: `2026-11-03-v1`.
Authorized experiment SHA-256: `e77d107fc034465d373df8356be26d6cced4fb0d38debe4d2090fd8f357e45df`.
Rubric SHA-256: `bb9889807b7babc8feed6a97ddd0c12c0fa334627e5d295017167fbd0a767cb2`.
Evaluator-template SHA-256: `ecb714aa746f7bdce82d86fd9bcc288d4e26ffd15cfa210bbd19a356e095793f`.

Final checks verified every result against its original question, Llama answer, reference, supporting summary and role assignment. All 1,818 recorded scoring payloads used the unchanged six metric-specific steps, five bands, v2 guidance and score/reason schema. Every successful response identified the intended judge; raw/native normalized scores agree exactly once. All 63 metric/language/role summaries were recomputed, Excel row counts checked, and both pilot artifact ledgers verified unchanged.

## Per-metric results

All means are native normalized 0-1 scores. Values in parentheses are evaluation counts. Language refers to benchmark-question language, not necessarily the language requested for the model answer.

| Metric | All mean (n) | EN mean (n) | FR mean (n) | Primary mean (n) | Secondary mean (n) |
|---|---|---|---|---|---|
| M1 | 0.9053 (76) | 0.8897 (39) | 0.9216 (37) | 0.9017 (59) | 0.9176 (17) |
| M2 | 0.6735 (234) | 0.7077 (130) | 0.6308 (104) | 0.6665 (161) | 0.6890 (73) |
| M3 | 0.6661 (327) | 0.7056 (177) | 0.6193 (150) | 0.6639 (233) | 0.6713 (94) |
| M4 | 0.8634 (112) | 0.8720 (50) | 0.8565 (62) | 0.8557 (61) | 0.8725 (51) |
| M5 | 0.6897 (174) | 0.7263 (95) | 0.6456 (79) | 0.7222 (72) | 0.6667 (102) |
| M6 | 0.6561 (253) | 0.6781 (137) | 0.6302 (116) | 0.6821 (95) | 0.6405 (158) |
| M7 | 0.6989 (638) | 0.7301 (349) | 0.6612 (289) | 0.7440 (75) | 0.6929 (563) |

Comparisons are descriptive. EN/FR and primary/secondary groups contain different questions, applicability patterns and difficulties; differences are not controlled estimates of language ability or training effects. No weighted or unweighted across-metric score is provided.

## Operational completion and resumption

- First session began **2026-11-06T14:38:58.228383+00:00**; the last evaluation session ended **2026-11-06T16:38:25.726150+00:00**, about **119.5 minutes** wall time including interruptions/restarts.
- A Windows PermissionError interrupted progress-file updating after 771 successful metric checkpoints. The same locked command resumed without duplicating those successes.
- A later task (`CA-XP-20261103-310`, M7) hit two network/timeouts followed by HTTP 403. At that point 1,725 tasks had succeeded, one failed, and 88 were unattempted. One read-only discovery check succeeded with existing credentials; the unchanged command then retried the failed task and completed the 88 unattempted tasks.
- There are **1,815 historical metric attempts**: 1,814 successes and one preserved failed attempt. Final per-task failures are zero. One additional transient HTTP 500 was recovered within the existing bounded request retries.
- Recorded run HTTP accounting: **1,818 scoring attempts + 3 session-discovery attempts = 1,821**. The separate diagnostic discovery is outside those recorded session totals; its precise transport-attempt count was not retained.
- API-reported usage: **2,892,134 prompt tokens + 1,007,842 completion tokens = 3,899,976 total**. Four failed/timeout scoring HTTP events supplied no usage; their possible usage is unknown rather than asserted zero.
- No completed success was re-scored during restart. Raw responses, failed attempts, retries, timestamps, latency and permission/session manifests are preserved.

## Observed patterns and calibration limitations

- M1 and M4 have the highest observed metric means (0.9053 and 0.8634); M6 and M3 are lower (0.6561 and 0.6661). Different constructs/question cohorts prevent treating these as a common calibrated scale.
- EN means exceed FR for M2-M7; M1 is higher in FR. Largest EN-FR differences are M3 (~0.0863), M5 (~0.0807) and M2 (~0.0769). These are descriptive cohort differences, not causal language-performance findings.
- Top-band concentration differs substantially: M1 has 61/76 scores at 0.9-1.0; M4 76/112; M5 16/174; M6 26/253. This is a review signal, not proof that either the model or rubric is valid/invalid.
- On the 22 overlapping v2 pilot tasks, **16 scores were unchanged, 2 higher, and 4 lower**, with maximum absolute change **0.3**. Same configuration does not imply deterministic judging. This overlap is not a formal repeatability/calibration study.
- Known interpretation limitations persist. Booster-seat M6 still receives 0.8 with a reason citing minor non-essential additions despite appropriate uncertainty handling. Recusal M2 still includes declaration-content detail beyond the narrow deadline question. Original reasons are retained; no post-hoc score adjustment was made.
- A keyword screen found **18** M3/M6/M7 reasons mentioning style/verbosity terms ({'M6': 15, 'M3': 2, 'M7': 1}). Some explicitly say style does not affect correctness. `review_flags.csv` is a manual-review queue, not a declaration that all these scores are wrong.
- Optional reference enrichment, band selection and institutional-duty/factual-recall boundaries still require human calibration. Evidence remains the supplied benchmark attestation and supporting summaries, not an independent source audit. Ancillary claims absent from summaries must not automatically be classified as false. Event dates, legal deadlines and specific cultural/safety claims require source verification if disputed.
- Judge deployment revision/weights and missing original HPC inference provenance were not invented. The scientific frozen-configuration/production-release gate remains unchanged.

## Result locations

All files are in `outputs/evaluations/llama_full_20261106_v2/`:

- `full_results.xlsx`: all 1,814 individual metric records, primary-only and secondary-only sheets, metric/language/role summaries, failures/missing tasks, all attempts and manifests.
- `all_results.jsonl` and `all_results.csv`: scores and full explanations with original question, model response, reference, supporting context, role and evaluator/run metadata.
- `primary_results.*` (756 rows), `secondary_results.*` (1,058 rows), `all_metric_summaries.*` (63 aggregate groups).
- `attempts.*`, `retry_report.*`, `failures.*`, `missing_tasks.*`, `full_run_summary.json`; final failure/missing files are empty because all tasks succeeded.
- `records/` and `raw/`: immutable individual attempts and original judge requests/responses; `sessions/`: stop/restart and HTTP accounting.
- `locked_experiment.json`, `manifest.json`, `completion_verification.json`, `review_flags.csv`, and `pilot_overlap_comparison.json`.
- The execution permission remains in `config/research/llama_full_20261106_v2/execution_approval.json`, bound to the authorized experiment hash.

The same pinned evaluator and model-aware result keys are reusable for GC LLM/Apertus when their independently validated answers arrive. They require distinct model/run identifiers and execution permissions, not overwriting or mixing these Llama results.
