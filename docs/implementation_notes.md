# Final proposed metric implementation and calibration

This addition reuses the existing settings, `.env` loading, gateway client, model discovery, DeepEval adapter, storage and CLI. It does not regenerate selected steps, change model weights, train models or execute the approximately 510-question benchmark. Existing generation, pilot and review artifacts are hash-checked before/after calibration.

## Authoritative configuration

`Canadianness_Final_GEVAL_Metrics.json` is authoritative. A **byte-identical**, versioned copy lives at `config/final/2026-11-03-v1/metrics_final.json`. Its SHA-256 is recorded in every calibration record and manifest. This copy retains the supplied proposed/not-frozen status and provenance. It is not placed in `config/frozen/`.

`validate-metrics` checks seven ordered metrics, six nonblank steps each, 42 ordered unique step IDs, five complete nonoverlapping rubric bands, exact required/optional inputs, workbook wording/order/criteria/exclusions/rubrics/source traces, and source candidate existence in the preserved raw generations. Excel's `S01` versus JSON's `S1` is a documented display-ID difference only. Neither original source file is edited. Additional document notes are review context, not permission to alter metric meaning or bypass the user's restrictions.

The single `make_final_metric` factory constructs installed DeepEval **4.3.2** GEval instances with **exactly the six supplied steps**, native Rubric objects, the existing RemoteJudge, explicit SingleTurnParams and synchronous execution. `LLMTestCaseParams` in this release is a deprecated alias for SingleTurnParams; we use the current name. The documented GEvalTemplate results extension adds the supplied criteria/exclusions as interpretation, alongside a fixed instruction to treat evaluated text as data; it does not append new evaluation steps. All scoring prompts and raw completions are retained in separate raw-response artifacts.

Official APIs inspected on 2026-11-03: [GEval](https://deepeval.com/docs/metrics-llm-evals), [custom judge models](https://deepeval.com/guides/guides-using-custom-llms), and installed GEval.measure, test-case parameter mapping, Rubric and custom-model schema-scoring source. Six-step equality and context delivery are covered by mocked tests using the real installed GEval implementation.

## Closed-book and judge inputs

The tested model is **not called** by calibration; supplied synthetic or stored model answers are scored. `closed_book_messages(case)` is a pure builder that contains only system prompt and question for a future tested-model client. It excludes answer, reference, context and rubric. Tests assert this separation. Do not attach reference evidence to tested-model inference later.

M1/M4 receive INPUT and ACTUAL_OUTPUT. Their optional reference parameters remain disabled by default, consistently for all cases. M2/M3/M5/M6/M7 additionally receive EXPECTED_OUTPUT and CONTEXT. `judge_case` populates exactly these approved parameters; CONTEXT is verified evaluator evidence, never `retrieval_context`. A source URL is metadata, not a substitute for source text. The hosted judge is not assumed to browse.

## Evidence readiness and applicability

The new `CalibrationCase` extends the legacy schema with primary/secondary metric labels, dataset version, synthetic diagnostic intent and an explicit evidence review. `applicable_metrics` must equal primary plus secondary labels. The schema preserves the original benchmark-style question, answer and reference fields.

Evidence-dependent scoring requires a nonempty reference answer/context, `status=verified`, explicit reference-answer verification, a per-metric sufficiency attestation, reviewer identity, review date and source IDs. Presence of text alone never establishes verification. Missing requirements produce `NOT_READY_FOR_FACTUAL_EVALUATION`, null score and a recorded reason, without judge inference. An inapplicable metric produces `NOT_APPLICABLE`; this differs from an evidence skip and from `FAILED`. Neither enters score averages.

The seven unready case–metric pairs in the bundled suite are the original three M3 and three M6 assumption-based pilot examples and a deliberate missing-evidence control. Their original records are unchanged. Source-reviewed historical M2/M5/M7 examples remain development examples, not human labels. New readiness annotations record Codex source review explicitly; they do not impersonate team review or independent human calibration.

## Scores and raw output

With native bands spanning 0–10, DeepEval 4.3.2 measure returns `(raw_score-0)/(10-0)` itself. This custom adapter has no logprob response method, so DeepEval uses schema-based scoring. Each record retains `deepeval_score` and `normalized_score` (also `score` for existing viewers), scoring method, exact applicable rubric and explanation. **The DeepEval result is not divided by ten a second time.**

The standalone normalization helper also supports an explicitly declared integer raw-score mode, dividing that value by ten. This is for explicit imports/tests, not the native GEval scoring path. Nonfinite or out-of-range values are failures, never silently clipped. Failed attempts preserve their original raw payload separately from interpreted score fields.

## Repeats and reproducibility

`calibrate` uses sequential conservative requests and three repetitions by default. The same final JSON and gateway-default sampling settings apply to all repeats. No temperature/seed support or deterministic model revision has been established, so identical-output guarantees are not claimed. A manifest records full dataset hash, original metric-file SHA-256, package versions, model ID, endpoint/timeout, run ID, input labels and factory version.

Every case/metric/repeat has its own immutable attempt checkpoint and separate raw-response file. JSONL includes individual status/score records. Explicit `--resume --run-id ...` validates the same manifest and skips already saved slots. By default even saved failures are not retried; `--retry-failures` explicitly authorizes another bounded attempt, preserving prior attempts. JSONL keeps all attempts; reports use the latest checkpoint for each repeat. A different experiment requires a new run ID. Interrupted output is recovered from checkpoints; incomplete JSONL tails are not used as authoritative data.

Reports never overwrite human workbooks. A separate `calibration-report` export defaults to a fresh report directory. Source JSON, original Excel, previous generation outputs, previous pilot results and review artifacts are checked by a baseline SHA-256 ledger. Concurrent edits to protected historical artifacts make that check fail visibly; new calibration outputs are separate.

## Human calibration

`human_calibration_review.xlsx` includes anonymous response IDs, question/response, reference, context, metric rubric, empty reviewer/score/comments, mean G-Eval score, all repeat explanations, difference formula and repeated-score SD. Judge scores/explanations/differences and revealing synthetic question IDs are hidden initially to reduce anchoring. Reviewers score on 0–1 independently, then reveal judge columns. Duplicate an item row for another reviewer with a distinct identity; their scores are retained separately.

`compare-human` validates actual labels and calculates per-metric/per-reviewer MAE, agreement within a chosen tolerance, Spearman rank correlation where at least three nonconstant paired scores exist, disagreement examples, and within-item human disagreement. Empty fields produce a pending-label report, not fictional scores. Workbook formulas are convenience displays; comparison uses actual entered score values. No automatic result constitutes approval or scientific validation.

## Known research limitations

The 51-case suite contains 21 original development examples and 30 new synthetic controls. It supplies 47 eligible case–metric pairs and seven unready pairs; M3/M2 controls intentionally overlap. Numerical independence is not forced. Diagnostic ranges are author expectations, not human ratings. Explanations are saved verbatim for review; semantic consistency is not inferred from a word-count or keyword test.

Potential M6 tension between rubric language about unsupported claims and steps distinguishing unestablished from false, and M3 practical-guidance anchors versus explanatory tasks, are reported explicitly without silently rewriting either. Controlled length, paraphrase, language, clarification, evidence and boundary contrasts provide limited developmental evidence. Broader domain coverage, reviewed benchmark sources, bilingual/domain-specialist judgment, actual base/fine-tuned paired outputs, and final team approval remain necessary before freezing a scientific standard.
