# Final proposed Canadianness metrics: observed calibration findings

Date: **2026-11-03**. Metric version: **2026-11-03-v1**. Authoritative JSON SHA-256: `bb9889807b7babc8feed6a97ddd0c12c0fa334627e5d295017167fbd0a767cb2`.

## What ran

Local verification passed **65 automated tests**, with the explicitly opt-in legacy live test deselected from that offline run. Ruff lint/formatting, imports/compile checks and dependency consistency also passed. Tests include missing evidence, N/A exclusion, exact-step preservation, score normalization, failed-judge isolation, secret handling, independent repeat persistence, interrupted JSONL recovery, human-label blanks, default CLI IDs and report generation during gateway outages. These software checks do not establish scientific validity.

The main run, `final_v1_calibration_20261103_01`, used all 51 development/synthetic cases, with three repetitions and the same hosted `gpt-oss-120b` judge and exact supplied metric definitions. **141 of 141 eligible scoring calls succeeded**, with no failed scoring calls or additional scoring retries. The 1071 saved status records comprise 141 successes, 21 evidence-not-ready records and 909 inapplicable records. Those statuses represent 51 cases × seven possible metrics × three repeats, not 1071 inference calls. Connection probes are additional small calls and are stored separately.

The original 21 examples were preserved and imported unchanged. Fifteen had eligible case–metric pairs; the original three M3 and three M6 assumption-only cases lack sufficient independently verified factual evidence and were explicitly skipped. A new deliberate missing-evidence control was also skipped. No nonexistent evidence or substitute judge-memory answer was invented.

A separately versioned two-case French supplement ran six further judgments successfully. **Total designated calibration scores: 147**, plus connectivity probes. No selected evaluation step or rubric description was regenerated or substantively edited. All 64 protected historical artifacts matched their before/after hashes. No human score was entered or generated, no frozen metric file was created, and no full benchmark or training was run.

## Repeated-score consistency

Statistics below describe within-case three-repeat variation; they are not inter-rater agreement or confidence intervals for a population.

| Metric | Eligible case–metric pairs | Mean within-case sample SD | Largest within-case spread |
|---|---:|---:|---:|
| M1 | 9 | 0.032 | 0.10 |
| M2 | 9 | 0.064 | 0.20 |
| M3 | 3 | 0.058 | 0.10 |
| M4 | 7 | 0.082 | 0.30 |
| M5 | 5 | 0.035 | 0.10 |
| M6 | 6 | 0.062 | 0.20 |
| M7 | 8 | 0.027 | 0.20 |

M4's largest spread was **0.3**. Gateway-default sampling was kept constant, but a deterministic seed/temperature contract and immutable deployment revision have not been established. These repeats are repeated measurements, not independent additional questions.

## Useful separation observed

- M1 penalized unnecessary jurisdiction clarification and incompatible foreign framing; genuine ambiguity received high scores.
- M2 preferred correct jurisdictional relationships over wrong-jurisdiction assertions and institution-name lists.
- M3 explanatory application outscored bare fact recitation in all three matched comparisons. The same responses were also scored for M2; legitimate overlap was retained rather than forcing numerical independence.
- M5 substantive Indigenous distinctions outscored generic homogenizing language in all three contrasts.
- M6 a supported concise answer outscored unnecessary refusal in all three contrasts.
- M7 concise, faithful paraphrase and longer equivalent correct answers all scored **1.0 on every repeat**. Partial answers scored **0.5 on every repeat**; materially incorrect additions scored 0.6, 0.4 and 0.4. These controls showed sensible direction and no observed verbosity bonus for those M7 answers.

These are small synthetic checks, not evidence of general cultural validity, bilingual fairness, independent human agreement or fine-tuning improvement.

## Exact cases requiring human review

**M1 — possible name-dropping/verbosity penalty.** `CAL-M1-CONCISE` scored **0.9, 0.8, 0.9**; the equivalent longer response scored **0.9, 1.0, 1.0**. Repeat 2 justified the concise penalty as a need to name the exact agency, although the question asks only the responsible level of government and the selected M1 steps discourage unnecessary institutional naming. This is evidence of a possible task-boundary error, not proof of a systematic length effect across questions. The matched-equivalence tolerance check failed on one of three repeats.

**M4 — factual accuracy leaked into a language-only judgment.** `CAL-M4-FACTUAL-BOUNDARY` scored **0.8, 0.5, 0.8**. The sentence was grammatical but factually wrong; the prompt explicitly limited the task to language. Repeat 2's explanation deducted credit for the geographic error. This conflicts with the supplied M4 exclusion of general factual correctness and merits correction during team calibration. Retest a reviewed M4 boundary instruction in a new version rather than silently altering the current six steps.

**M4 — French controls need linguistic adjudication.** The initial *fin de semaine* versus *week-end* contrast differed by 0.2 on two repeats, but the author expectation itself is debatable: OQLF describes the coexistence of both forms while noting reservations about *week-end* in Quebec usage. That contrast alone does not establish unfairness. A separate unambiguous *pendant la fin de semaine* / *durant la fin de semaine* supplement produced **0.8, 0.8, 1.0** versus **1.0, 0.9, 1.0**. Human review should inspect both the language judgments and the explanations. See [control review](calibration_control_review.md) for source attribution and the reason for adding a separate dataset without changing the original.

**M5 — possible unnecessary repetition requirement.** `CAL-M5-DISTINCTIONS` scored **0.8, 0.9, 0.9**. Repeat 1 described the response as accurate and relevant but deducted credit for not explicitly naming each group, even though the question already supplies First Nations, Inuit and Métis and the answer refers to them collectively. Human reviewers should decide whether any material information is actually missing.

**M6 — valid extra information sometimes lost points.** `CAL-M6-CORRECT-EXTRA` scored **0.8, 1.0, 0.9**, while the concise supported answer scored 1.0 throughout. Repeat 1 acknowledged the added year was directly supported by context, then treated unnecessary detail as a weakness. This is a potential shift from reliability toward relevance/verbosity. The limited-evidence extra-claim case scored **0.8, 0.8, 0.7**; the judge did not call the extra claim false, but invoked its own knowledge to call it true despite its absence from supplied evidence. That explanation should not be treated as independent source verification.

**M6 — fabricated verification received variable partial credit.** `CAL-M6-FABRICATED-VERIFICATION` scored **0.4, 0.5, 0.6** although each explanation recognized the fabricated source-check claim. Two repeats exceeded the synthetic diagnostic ceiling of 0.4. The team should decide an explicit materiality/score-cap policy for fabricated verification, if desired; the existing rubric is preserved pending that decision. Calling the unsupported browsing claim fabricated is grounded here in the synthetic test design, not a claim that the judge can observe arbitrary model browsing histories.

**M3 — check explanatory-task boundaries.** `CAL-M3-EXPLANATION` scored 0.8, 0.9 and 0.8 for M3. It consistently beat fact recitation, but the rubric's practical-guidance anchors may still encourage demanding extra actions on explanation-only tasks. Inspect explanations before proposing any anchor revision. M2 scored the same explanatory response 0.8 throughout, which is documented construct overlap rather than forced independence.

## Reports and analysis correction

The initial machine-generated reports are preserved. A report-only update added numerical tolerance for floating-point comparisons: a 0.1 difference represented as `0.10000000000000009` is now correctly treated as within the 0.1 diagnostic tolerance, and a mathematically 0.2 spread is not missed because of binary representation. **No scores, judge outputs, dataset records, selected steps or rubrics changed.**

Use the corrected detailed [report](../outputs/calibration/final_v1_calibration_20261103_01/reports/analysis_v2/metric_calibration_report.md) and [summary workbook](../outputs/calibration/final_v1_calibration_20261103_01/reports/analysis_v2/calibration_summary.xlsx). It contains **24 diagnostic flags** across synthetic range misses and repeated-spread checks. These flags are review prompts, not 24 proven scoring errors. All individual raw outputs and interpreted scores remain in the main run directory. The original report's one false tolerance-boundary failure is retained for auditability; it should not be used as evidence of judge inconsistency.

The [human-review workbook](../outputs/calibration/final_v1_calibration_20261103_01/human_calibration_review.xlsx) contains all applicable pairs, references, evidence statuses, rubric descriptions and all repeat explanations. Human identity, score and comment cells are blank. Judge score/reason/difference columns and revealing synthetic IDs are hidden initially to reduce anchoring. Reviewers should score independently before revealing those columns. Actual labels can be analyzed with `compare-human`; no human agreement has yet been measured.

## Readiness conclusion

The implementation is ready for **team human calibration and documented rubric decisions**. It is not ready to be declared a fully validated or frozen scientific standard. Review the exact M1/M4/M5/M6 cases above, adjudicate ambiguous synthetic language controls, decide any explicit materiality policies, and rerun a separately versioned held-out calibration after approved changes. Verify the real benchmark's question-specific sources and applicability before running the eventual paired base-versus-fine-tuned comparison. The software provides the factory, evidence gate, result metadata and resumable calibration infrastructure; the proposed JSON remains unapproved for production scientific inference.
