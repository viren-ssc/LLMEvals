# Final Llama pilot scoring review

**Technical data, request and checkpoint checks pass. Scoring-quality clearance is conditional: four metric judgments need targeted interpretation/adjudication. The full 1,814-evaluation run has not started.**

No Llama answers, authoritative rubrics, fixed steps, saved judge scores or production gates were changed. No new judge calls were made. This is a Codex qualitative review, not human-approved rubric calibration.

## Four flagged cases: all nine metric judgments

The complete questions, Llama answers, reference answers, supporting summaries, original reasons, and applicable fixed rubrics were inspected. The self-contained [detailed review](../outputs/evaluations/llama_pilot_20261106_v1/scoring_review/detailed_review.json) retains all of them; [review CSV](../outputs/evaluations/llama_pilot_20261106_v1/scoring_review/review_summary.csv) provides the decision table.

| Question | Metric | Score | Assessment | Recommended action |
|---|---|---:|---|---|
| CA-XP-20261103-192 | M2 | 0.4 | Insufficiently justified: factual deadline error is not automatically a jurisdictional error. | Review institutional anchor fit; exclude unasked declaration details. |
| CA-XP-20261103-192 | M7 | 0.1 | Justified against supplied reference: the central requested deadline is incorrect. | Retain provisionally. |
| CA-XP-20261103-151 | M5 | 0.5 | Broadly justified: generic reflection omits the specific treaty relationship. | Retain; explain cultural omission rather than just a date error. |
| CA-XP-20261103-151 | M7 | 0.8 | Defensible, but claim that all required facts are present is too strong. | Retain provisionally; clarify required chronology versus event distinction. |
| CA-EXP-037 | M3 | 1.0 | Justified: refuses guarantee and applies conditions with practical guidance. | Retain; accept equivalent correct wording. |
| CA-EXP-037 | M6 | 0.8 | Saved rationale does not justify a reliability deduction for style. | Review uncertainty claims under M6, excluding style. |
| CA-EXP2-059 | M1 | 0.9 | Justified: explicit jurisdictional awareness and conditional guidance. | Retain. |
| CA-EXP2-059 | M3 | 0.8 | Score plausible, rationale defective: a numbered list is present. | Assess actual belt-fit completeness; exclude verbosity/list-format preference. |
| CA-EXP2-059 | M6 | 0.8 | Insufficiently justified: province/territory dependence is explicitly covered. | Credit conditional guidance; identify a genuine reliability weakness or reconsider band. |

## Evidence limits and exact verification needs

- Recusal: the supplied reference identifies subsection 25(1) and 60 days. If disputed, verify the applicable-version statutory subsection, duty timing and declaration content. No fresh legal verification is claimed here.
- Treaty Day: if disputed, verify Nova Scotia?s October 1, 2024 observance and the exact dates of the particular 2024 Truth and Reconciliation Week referenced (including which organizer/event). The reference?s September 23?30 and Llama?s September 24?30 must not be reconciled by assumption. The significance of the Mi?kmaq treaty relationship is established only to the extent of the supplied evidence in this review.
- Canal: supplied evidence establishes weather dependence and no guaranteed opening, but not a probability of opening in mid-February, the narrower typical opening interval, or newsletter availability. Verify historical NCC season information and communications options only if those ancillary claims materially affect adjudication. Classify absent support as unverified rather than false.
- Booster seat: supplied evidence supports jurisdiction, child characteristics, manufacturer limits and actual belt fit. If material, verify whether the extra seated-height/seat-category descriptions or residence-versus-place-of-use wording are accurate against the relevant official guidance. No current threshold or personal safety ruling is inferred.

## Independent metric application and proposed interpretation correction

All 22 saved request bodies were rechecked. Each uses its own metric?s exact six steps, five bands, criteria and exclusions, with score/reason output schemas. Raw 0?10 scores match native 0?1 outputs exactly once. There were no step-generation requests. Separate metric instances and question/model/metric checkpoint keys prevent reuse of another metric?s score. Different scores are legitimate: M5 cultural meaning and M7 factual chronology, or M3 practical application and M6 reliability, need not agree.

Metric boundaries remain: M1 contextual/jurisdictional recognition; M2 institutional roles/relationships; M3 scenario reasoning/application; M4 requested language/terminology; M5 task-relevant cultural meaning; M6 evidence and uncertainty calibration; M7 factual correctness/completeness. M4 may assess language naturalness where requested; that does not authorize generic style penalties in other metrics. Mechanical prompt fidelity does not establish semantic scoring consistency: the issues above are examples of cross-metric leakage.

**Proposed, not applied:** a versioned evaluator interpretation reminder should require the judge to identify the concrete metric-relevant error/omission and explain its selected existing band; avoid generic verbosity/list-format penalties outside a rubric requirement; credit semantically equivalent conditional guidance; separate missing support from contradiction; and distinguish requested facts from optional reference enrichment. For M2, explain the institutional responsibility/relationship impact rather than copying a factual-recall deduction. Preserve all 42 steps and 35 bands verbatim.

If adopted, record a new evaluator-template/factory version and run manifest, then adjudicate or narrowly rejudge the four disputed metric pairs (recusal M2, canal M6, booster M3 and M6). Keep original scores/reasons intact alongside the new attempts. This review assigns no replacement scores and no team approval. No extensive redevelopment or new benchmark questions are needed.

## Production readiness

Fresh offline validation passed: 756 unique questions, 756 nonempty answers, Excel/JSONL ID and answer equality, 404 EN/352 FR, and exactly 1,814 unique question?Llama?metric keys. The task set exactly equals applicability labels, preserving 756 primary/1,058 secondary assignments. Prepared question/answer text and plan hashes match the previous readiness manifest.

All 22 completed exports have valid scores, nonempty explanations, roles, language, versions, checksum, judge configuration, run ID, timestamp and status. Planned tasks deliberately have no fabricated scores. Individual metric checkpoints and existing resume/no-op logs were inspected; prior retry/torn-log tests support safe metric-level resumption. This review makes no fresh claim of a deliberately induced live failure.

Rubric: `config/final/2026-11-03-v1/metrics_final.json`, version `2026-11-03-v1`.
SHA-256 unchanged: `bb9889807b7babc8feed6a97ddd0c12c0fa334627e5d295017167fbd0a767cb2`. Source JSON matches.

Configured endpoint matches the successful pilot: `https://litellm.dsai-sdia.ssc-spc.cloud-nuage.canada.ca/v1`; the existing `auto` setting resolves uniquely to `gpt-oss-120b` in the saved accessible identity. All 22 saved response metadata model IDs agree. Credentials are present and were not displayed. No new connectivity call was needed or made.

The generic generation/result schema and checkpoint keys support GC LLM/Apertus later. Their incoming files will need independently validated case sets/run manifests; the current preparation command is specifically configured for Llama. No wait for paired model answers is necessary.

**Status:** technically functional and data/task-ready, but not an unconditional scoring-quality clearance. The existing production gate remains unsatisfied: `config/frozen/` contains no approved configuration. The HPC pilot entry point is intentionally capped at 20 questions/60 metric assignments; the prepared 1,814-task plan is not a runnable full-job authorization. Approved production wiring must retain the reviewed fixed-rubric factory and checkpoint engine, rather than routing unchanged through the legacy factory that appends rubric guidance to its step list.

Full execution requires: resolve the focused scoring interpretation issues, user review/explicit execution authorization, and the existing frozen-configuration approval. Technical success does not constitute empirical rubric calibration or human approval. No full evaluations were started.

Machine-readable checks: [scoring-review readiness](../data/processed/llama_756_v1/scoring_review_readiness.json). Previous technical pilot results and the full-run task plan remain unchanged.
