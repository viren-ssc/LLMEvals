# Synthetic final-metric calibration suite

`final_v1_cases.jsonl` is version `synthetic-calibration-2026-11-03-v1`, authored by `canadianness_eval.calibration.pilot_cases`. It contains **51 synthetic/development cases**, not a verified 510-question benchmark. The first 21 reuse every original field from `data/examples/pilot.jsonl` unchanged; only explicit calibration/readiness metadata was added in this separate copy.

There are **54 applicable case–metric pairs**: 47 ready for scoring and seven not ready. Three repeats imply **141 intended judge scores**, 21 evidence-not-ready slots and 909 inapplicable slots, across 1071 total status records. Status records do not imply 1071 model requests. No call is made for a skip or N/A slot.

New controls cover concise/long equivalent wording, paraphrases, material added errors, partial coverage, ambiguity and unnecessary clarification, Canadian French variants, institutional relationships and misapplied jurisdictions, application versus recitation, Indigenous distinctions, excessive refusal, invented verification and true/unknown extra claims. Intended ranges and directional comparisons are synthetic diagnostic hypotheses, never fabricated human ground truth.

The question-scoped official references were independently consulted on **2026-11-03**:

- [Canadian Heritage: Manitoba symbols](https://www.canada.ca/en/canadian-heritage/services/provincial-territorial-symbols-canada/manitoba.html): Winnipeg and entry into Confederation on July 15, 1870. Contexts retain only relevant paraphrased facts, not dated population values.
- [Manitoba curriculum](https://www.edu.gov.mb.ca/k12/cur/index.html) and [BC curriculum](https://curriculum.gov.bc.ca/): separate provincial curriculum resources. No teacher licensing or transfer entitlement is inferred.
- [Crown-Indigenous Relations: Indigenous peoples and communities](https://www.cirnac.gc.ca/eng/1100100013785/1529102490303): distinct First Nations, Inuit and Métis peoples and cultural/historical differences. This short source is not comprehensive community-specific cultural evidence.

M1/M4 are question/response framing and language tasks; source passages are not required or secretly passed to the judge. French wording controls are synthetic linguistic contrasts requiring human review, not a claim of independent linguistic validation. The unknown benefit case asks only whether a geography reference establishes eligibility; no health/legal entitlement claim is made or scored.

In `CAL-M6-UNESTABLISHED-EXTRA`, judge-visible evidence establishes only Winnipeg. The added Victoria claim is intentionally outside that evidence; the judge must treat it as unestablished rather than false. This tests classification of evidence limits; the judge cannot independently verify the extra assertion. No evaluation claims that its absence from an excerpt disproves it.

Each new case records evidence-review identity/date/source IDs and per-metric sufficiency. That is transparent Codex source review, **not a team-member human score** or final scientific approval. The old M3/M6 assumption examples remain unverified and are skipped for factual scoring. No benchmark question, response or reference in the original example dataset was modified.

The initial *week-end* control is linguistically debatable; its high-score interval is an unconfirmed author hypothesis. A separate two-case `french_supplement_v1.jsonl` retains *fin de semaine* and varies only *pendant/durant*. Neither the original suite nor its results were changed. See [control review](../../docs/calibration_control_review.md).
