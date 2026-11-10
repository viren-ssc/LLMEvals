# Llama-only provisional pilot ? 2026-11-06

**Technical pilot passed. Full 1,814-evaluation run has not started and awaits user review and the existing production approval gate.**

## Validated incoming data

Existing `hpc_ingestion` validated 756 unique questions and 756 nonempty Llama answers. Excel and normalized JSONL have identical question-ID sets and answer strings. Distribution: 404 EN / 352 FR. There are 756 primary assignments, 1,058 secondary assignments, and **1,814 total metric evaluations**. No answers were regenerated. The locally generated validation manifest records file SHA-256 hashes and all checks. A separate final benchmark file was not supplied for independent text comparison; the verified match here is between the two incoming artifacts.

Files: [validation manifest](../data/incoming/Canadian-ness_Llama_Validation_Manifest.json), [prepared 756 cases](../data/processed/llama_756_v1/all_cases.jsonl), [full 1,814-task plan](../data/processed/llama_756_v1/full_run_plan.jsonl).

| Metric | Primary | Secondary | Total |
|---|---:|---:|---:|
| M1 | 59 | 17 | 76 |
| M2 | 161 | 73 | 234 |
| M3 | 233 | 94 | 327 |
| M4 | 61 | 51 | 112 |
| M5 | 72 | 102 | 174 |
| M6 | 95 | 158 | 253 |
| M7 | 75 | 563 | 638 |

## Exact rubric and methodology

Artifact: `config/final/2026-11-03-v1/metrics_final.json`; version `2026-11-03-v1`.
SHA-256: `bb9889807b7babc8feed6a97ddd0c12c0fa334627e5d295017167fbd0a767cb2`. Source JSON has the same checksum. All seven metrics contain six steps each (42 total) and five bands each (35 total). No definitions, steps, scoring anchors or source artifacts were changed. The root `v1_20261103.json` is a separate newer review proposal and was not silently selected.

Original status: `ready_for_team_review_and_calibration_not_empirically_frozen`. Every exported score is **provisional**. Native DeepEval normalization was retained exactly once. No overall Canadian-ness score or unapproved weighting was computed.

The existing fixed-rubric factory and calibration checkpoint engine are reached through `evaluation_runner.evaluate_hpc_pilot`. The existing gateway/adapter, retry policy and production frozen-configuration gate remain in place. A kernel process lock prevents concurrent writers. No new inference client or metric definitions were created.

Evidence readiness imports the user-provided verified-benchmark attestation recorded in the project task. This is explicit in every prepared case and run metadata; it is not a new independent source verification. Original verification dates and source URLs were not supplied and were not invented. `context_text` is retained as supporting summary text, not a verbatim quotation or infallible authority. M1/M4 receive only question and Llama output; evidence-dependent metrics additionally receive the reference answer and context. The question alone occupies the test-case input field.

## Pilot design and request audit

14 real questions: one primary-metric example per metric and language. All applicable secondary metrics were retained, giving 22 evaluations: 14 primary / 8 secondary and 11 EN / 11 FR. Most examples minimize applicable-metric count and answer length to contain pilot cost. Two explicit M6 cases test the inability to guarantee Ottawa canal skating conditions and missing provincial/child details for a booster-seat decision. The selection is for integration coverage, not a representative accuracy estimate.

The saved-request audit checked all 22 payloads: exact question/answer, fixed six steps, rubric bands, criteria/exclusions, correct evidence inclusion/exclusion, judge identity, and score/reason response schemas. Every request was a scoring request; none requested evaluation-step generation. Offline tests also make dynamic step-template invocation fail explicitly.

Judge: `gpt-oss-120b` via `https://litellm.dsai-sdia.ssc-spc.cloud-nuage.canada.ca/v1`, DeepEval 4.3.2 / Python 3.13.1. TLS verification enabled, no redirects. Sequential concurrency=1; 180-second request timeout, gateway-default sampling/output budget, native JSON-schema mode; no seed/determinism claim.

## Observed results

- Successes: **22/22**; failures **0**, error rate **0%**; no HTTP or schema retries.
- HTTP requests: **23 total** = one authenticated discovery + **22 scoring requests**.
- Mean evaluation latency **2.716s**, median **2.513s**, range **1.622?4.344s**.
- API-reported tokens: **21,634 prompt + 9,902 completion = 31,536 total**. Completion counts include provider-accounted generation, not just visible explanation text.
- All 22 completion metadata model fields identified `gpt-oss-120b`; all finish reasons were `stop`.
- Same-run resume issued **zero** additional judge requests; checkpoint filenames and hashes were unchanged. Failed-call retry and interrupted/torn-log recovery passed mocked HTTP tests; no live fault was deliberately induced.
- Regression suite: **121 passed, 1 live test deselected**. After final workbook/request-accounting changes, three focused workflow tests passed. Ruff passed for changed code.

Provisional pilot means below describe only this small selected set, not benchmark-wide model quality.

| Metric | n | Mean score | EN mean (n) | FR mean (n) | Primary mean (n) | Secondary mean (n) |
|---|---:|---:|---|---|---|---|
| M1 | 3 | 0.967 | 1.000 (1) | 0.950 (2) | 1.000 (2) | 0.900 (1) |
| M2 | 2 | 0.500 | 0.400 (1) | 0.600 (1) | 0.500 (2) | ? |
| M3 | 4 | 0.875 | 1.000 (2) | 0.750 (2) | 0.850 (2) | 0.900 (2) |
| M4 | 2 | 0.850 | 0.700 (1) | 1.000 (1) | 0.850 (2) | ? |
| M5 | 2 | 0.650 | 0.500 (1) | 0.800 (1) | 0.650 (2) | ? |
| M6 | 2 | 0.800 | 0.800 (1) | 0.800 (1) | 0.800 (2) | ? |
| M7 | 7 | 0.757 | 0.700 (4) | 0.833 (3) | 0.900 (2) | 0.700 (5) |

## Items for human review

- `CA-XP-20261103-192`: M2=0.4, M7=0.1. Judge flags the generated seven-day recusal deadline as conflicting with the supplied 60-day reference. Inspect the evidence and rubric-specific severity; this report does not independently verify the legal claim.
- `CA-XP-20261103-151`: M5=0.5, M7=0.8. Judge flags the Truth and Reconciliation Week dates and absence of specific Mi?kmaq context; review cultural completeness separately from factual accuracy.
- `CA-EXP-037`: M6=0.8, M3=1.0. The M6 explanation describes appropriate uncertainty and no factual errors but mentions minor stylistic excess. Review whether that score deduction follows the supplied M6 rubric; technical success does not establish scientific calibration.
- `CA-EXP2-059`: M6=0.8, M3=0.8, M1=0.9. Judge notes local-regulation awareness but an insufficiently explicit province request. Full answer/reference and explanations are retained.

## Review artifacts and workload

- [Review workbook](../outputs/evaluations/llama_pilot_20261106_v1/pilot_review.xlsx): every individual score/reason, original question/Llama answer/reference/context, blank human-review fields, metric/language/role summaries, and verbatim 42 steps plus 35 rubric bands.
- [Individual JSONL](../outputs/evaluations/llama_pilot_20261106_v1/question_scores.jsonl) and [CSV](../outputs/evaluations/llama_pilot_20261106_v1/question_scores.csv).
- [Per-metric/language/role CSV](../outputs/evaluations/llama_pilot_20261106_v1/metric_summaries.csv).
- [Request audit](../outputs/evaluations/llama_pilot_20261106_v1/request_audit.json), [resume check](../outputs/evaluations/llama_pilot_20261106_v1/resume_check.json), [acceptance](../outputs/evaluations/llama_pilot_20261106_v1/pilot_acceptance.json), and immutable `records/` plus `raw/` request/response files in the same run directory. No authorization headers or keys were recorded.

Full run is staged as 756 immutable prepared cases and exactly 1,814 planned tasks. Baseline: 1,814 scoring requests plus discovery; retries add requests (up to nine HTTP attempts per logical generation under the existing nested bounds). Simple extrapolation from this real pilot is **82.1 minutes** sequentially. This is conditional and likely optimistic: selected pilot answers average **502 characters**, versus **1436** across the full dataset. Rate limits, context-window/output-token limits and changing gateway load remain unverified. No production throughput guarantee or statistical confidence claim is made.

The full run would score all 1,814 tasks under a separate run manifest; the pilot remains separately preserved. Pilot results are not silently counted as completed full-run results. The evaluated-model identifier, task keys and summaries permit later GC LLM and Apertus records without requiring paired answers now. Missing HPC inference provenance must be obtained from the HPC owner for research reproducibility.

**Remaining gates:** user review of this real pilot, resolution of flagged rubric/calibration concerns, and the existing human-approved frozen production configuration. None was fabricated or automatically approved. The new CLI exposes preparation, bounded provisional pilot, and report-only export; it cannot start the full dataset through the pilot path.

## Commands

```powershell
.\.venv\Scripts\python.exe -m canadianness_eval.hpc_workflow prepare
# No-op resume of this completed pilot; no new scoring calls:
.\.venv\Scripts\python.exe -m canadianness_eval.hpc_workflow pilot --resume
# Retry only failed evaluations if a future interruption/failure occurs:
.\.venv\Scripts\python.exe -m canadianness_eval.hpc_workflow pilot --resume --retry-failures
# Rebuild derived reports without network access:
.\.venv\Scripts\python.exe -m canadianness_eval.hpc_workflow report
```
