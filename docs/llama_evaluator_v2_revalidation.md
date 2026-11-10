# Evaluator v2: focused Llama pilot revalidation

**Decision: hold the unattended 1,814-task production run pending human adjudication and the existing frozen-configuration approval.** The one requested revalidation is complete; no further automatic scoring/refinement cycle is scheduled.

## Implementation and technical verification

The generic clarification in `config/evaluator/scoring_interpretation_v2.txt` enforces current-metric scope, concrete band justification, task-relevant style requirements, semantic equivalence, qualified guidance, evidence limits and mandatory-versus-optional reference information. It contains no disputed question IDs, previous judgments or desired score direction, and adds no evaluation steps or scoring criteria.

Factory version: `final-json-factory-v2`. All 42 supplied steps and 35 band descriptions are unchanged. DeepEval still performs its native normalization once. Judge remains `gpt-oss-120b` at the same authenticated HTTPS gateway, DeepEval 4.3.2, concurrency 1, timeout 180 seconds, gateway-default sampling and no requested seed/logprobs. Those defaults do not establish determinism.

- Evaluator-template checksum: `ecb714aa746f7bdce82d86fd9bcc288d4e26ffd15cfa210bbd19a356e095793f`.
- Interpretation text checksum: `b55383b2393ce69bf67cbb27afa5270a9cedd89026862f730845d63d9733308c`.
- Unchanged rubric checksum: `bb9889807b7babc8feed6a97ddd0c12c0fa334627e5d295017167fbd0a767cb2`.
- The evaluator-template checksum hashes a canonical specification of the factory source checksum, interpretation-file checksum and installed DeepEval version. It identifies the evaluator wrapper/configuration separately from the scientific rubric; actual rendered requests are retained individually.
- Version/checksum metadata is included in run and result judge configurations. Resume rejects a changed interpretation; an older v1 run cannot silently resume using v2.
- Original run `llama_pilot_20261106_v1` was hashed before revalidation and remains byte-identical across every file. Factory v1 source and the v2 factory/interpretation are snapshotted in the new run.
- New run `llama_pilot_20261106_v2` uses exactly the same 14 questions and 22 primary/secondary tasks and identical original answers/evidence. Requests were built only from the test-case fields, fixed metric and generic interpretation; the post-run audit found no old judge explanations, scoring-history fields or dynamic step-generation requests.
- **22/22 successful evaluations**, no failures or retries; **23 HTTP requests** (one discovery + 22 scoring). Mean evaluation latency **3.07s**, median **2.76s**, range **1.65-6.18s**. These are pilot observations, not full-run throughput guarantees.
- A real no-op resume left checkpoints unchanged and issued zero further judge requests. Offline regression: **122 passed, 1 live test deselected**; Ruff passed. Mocked failure recovery and metric-level retry tests continue to pass.
- Fresh validation retained 756 nonempty Llama answers and 1,814 unique planned tasks (756 primary/1,058 secondary). Model-aware task keys, checkpointing and exports remain compatible with later independent GC LLM/Apertus imports. All new scores retain reasons, roles and evaluator/run metadata. No overall Canadian-ness score was computed.

## Old versus new: all 22 judgments

P = primary, S = secondary. There were five increases, five decreases and 12 unchanged scores. Changes alone do not establish improvement; this single gateway-default run cannot separate prompt effects from judge variation.

| Question ID | Metric | Role | Old | New | Explanation review |
|---|---|---|---:|---:|---|
| CA-EXP-007 | M7 | P | 0.8 | 0.8 | Lower band still lacks a concrete error/required omission. |
| CA-EXP-037 | M3 | S | 1.0 | 0.9 | Rubric-relevant explanation. |
| CA-EXP-037 | M6 | P | 0.8 | 0.9 | Explanation now links to this metric and its existing band. |
| CA-EXP-042 | M5 | P | 0.8 | 0.7 | Cultural band plausible; extra disclaimer and factual support need care. |
| CA-EXP-090 | M4 | P | 1.0 | 1.0 | Rubric-relevant explanation. |
| CA-EXP2-059 | M1 | S | 0.9 | 0.9 | Rubric-relevant explanation. |
| CA-EXP2-059 | M3 | S | 0.8 | 0.8 | Identified interpretation concern remains. |
| CA-EXP2-059 | M6 | P | 0.8 | 0.8 | Identified interpretation concern remains. |
| CA-EXP2-180 | M3 | P | 1.0 | 1.0 | Requested practical classification is correct. |
| CA-EXP2-180 | M7 | S | 0.9 | 1.0 | Additional moderate range is asserted correct without supplied support. |
| CA-EXP2-312 | M4 | P | 0.7 | 0.9 | Requested language judged appropriate; within-scope variation. |
| CA-M1-20261104-001 | M1 | P | 1.0 | 1.0 | Rubric-relevant explanation. |
| CA-M1-20261104-050 | M1 | P | 1.0 | 1.0 | Rubric-relevant explanation. |
| CA-XP-20261103-151 | M5 | P | 0.5 | 0.5 | Rubric-relevant explanation. |
| CA-XP-20261103-151 | M7 | S | 0.8 | 0.8 | Mostly correct; supplied reference supports minor date discrepancy. |
| CA-XP-20261103-190 | M2 | P | 0.6 | 0.5 | Unasked reference enrichment still treated as material. |
| CA-XP-20261103-190 | M7 | S | 0.8 | 0.9 | Rubric-relevant explanation. |
| CA-XP-20261103-192 | M2 | P | 0.4 | 0.1 | Explanation now links to this metric and its existing band. |
| CA-XP-20261103-192 | M7 | S | 0.1 | 0.1 | Rubric-relevant explanation. |
| CA-XP-20261103-279 | M3 | P | 0.7 | 0.8 | Timing trigger relevant; exception details may be optional. |
| CA-XP-20261103-279 | M7 | S | 0.9 | 0.8 | Lower band still lacks a concrete error/required omission. |
| GC-HQ-0157 | M7 | P | 1.0 | 1.0 | Rubric-relevant explanation. |

## Disputed judgments and retained controls

- **Recusal M2: 0.4 -> 0.1.** Addressed at explanation level, not an assumed improvement from the decrease. The judge now says the wrong deadline misrepresents the office holder's core responsibility, fitting the 0-2 governmental-responsibility anchor, and stops requiring unasked declaration-content details. Whether a deadline error warrants that severe M2 band is still a human calibration decision; this is a defensible interpretation, not independent validation of the exact score.
- **Canal M6: 0.8 -> 0.9.** The style deduction disappears. The reason now credits qualification, refusal to guarantee, NCC checks and absence of fabricated certainty, matching the 9-10 band. The original style concern is addressed; ancillary opening-window/probability/newsletter claims are not independently verified by the short supplied summary.
- **Booster-seat M3: 0.8 -> 0.8.** Not resolved. It no longer invents absence of a numbered list, but deducts for not explicitly asking the province even while acknowledging that the answer already addresses it. M3 permits useful conditional guidance. No concrete practical omission supporting the deduction is identified.
- **Booster-seat M6: 0.8 -> 0.8.** Not resolved. The new reason accepts uncertainty handling and no fabricated facts, then cites reasonable extra detail. Extra detail is not a reliability weakness; manufacturer/seat-limit information also appears in the reference. This still fails to justify the lower band.
- **Recusal M7: 0.1 -> 0.1** remains appropriately justified against the supplied central deadline contradiction. **Treaty Day M5: 0.5 -> 0.5** continues to identify the specific missing treaty relationship and distinction from national remembrance, which is culturally relevant rather than generic name-dropping. These previously defensible judgments were retained.
- Equal M2/M7 recusal scores are not evidence of leakage: each was independently requested. Conversely, merely using separate requests does not prove perfect semantic separation.

## Remaining inconsistencies and evidence limits

The hold recommendation is based on remaining interpretation problems, not on scores moving in an undesired direction:
- `CA-EXP-007` M7 stays 0.8 while its reason says the required fact is correct, extras are unnecessary, and then calls the answer incomplete. `CA-XP-20261103-279` M7 moves 0.9 -> 0.8 despite a reason saying no factual errors and sufficient completeness. Neither identifies the minor inaccuracy needed to justify the 7-8 band.
- `CA-XP-20261103-190` M2 still penalizes omitted examples/designated subgroups without explaining why the narrow elected-versus-appointed question requires them. `CA-EXP-042` M5 asks for an explicit non-universality disclaimer without identifying actual conflation; any such deduction must be task-relevant.
- `CA-EXP2-180` M7 calls the added 10-15% moderate range correct even though the supplied evidence establishes only the <=5% and >=15% thresholds. The inclusive 15% boundary also needs examination. This is unverified/ambiguous from the current evidence, not automatically false and not automatically grounds to change the score.
- Treaty Day week dates need event/organizer-specific 2024 verification if disputed. The recusal statutory subsection/date should be verified if the supplied reference is questioned. No independent legal fact-checking occurred in this run.
- Canal ancillary seasonal/probability/newsletter assertions and the M?tis example's added sash/clothing-material descriptions are not established by the short context summaries. Verification would require the relevant historical NCC information and authoritative cultural resources, respectively. Do not automatically treat them as false or assert independent correctness.
- Booster-seat data and belt-fit requirements should be assessed semantically against the supplied reference. If a genuine safety-guidance uncertainty becomes material, consult the relevant official guidance; no new thresholds or personal safety decision are inferred here.
- Evidence provenance remains the user-supplied verified-benchmark attestation. This clarification neither creates new evidence nor elevates summaries to verbatim authoritative source excerpts.

## Production decision and artifacts

**Recommendation: do not proceed with unattended production yet.** The v2 implementation is technically validated, but the two booster judgments and optional-detail/band-justification problems show that the clarification is not consistently followed. Resolve the named band/scope decisions through a bounded human adjudication/sign-off, not an automatic score increase or another open-ended prompt iteration. No additional revalidation or benchmark development was started.
`config/frozen/` still has no approved frozen metric configuration. User execution authorization and the existing human/frozen gate are required. The pilot path remains capped at 20 questions/60 metric assignments and cannot execute the 1,814-task plan. Final production wiring must use the reviewed fixed-rubric factory/checkpoint engine and preserve this gate; a prepared plan is not full-job authorization.

- [Side-by-side workbook](../outputs/evaluations/llama_pilot_20261106_v2/pilot_review.xlsx), including both explanations and qualitative assessments on the Old vs new judgments sheet.
- [Reviewed comparison CSV](../outputs/evaluations/llama_pilot_20261106_v2/reviewed_comparison.csv) and [JSON](../outputs/evaluations/llama_pilot_20261106_v2/reviewed_comparison.json): all 22 old/new scores, full reasons, roles and review findings.
- [Configuration/technical acceptance](../outputs/evaluations/llama_pilot_20261106_v2/revalidation_acceptance.json) and [production decision](../outputs/evaluations/llama_pilot_20261106_v2/production_decision.json).
- New run also retains individual `records/`, raw payloads, request audit, baseline integrity ledger, resume proof, per-metric/language/role summaries and template snapshots.

For audit-only reuse, `python scripts/revalidate_llama_pilot.py --resume` validates the v2 manifest and resumes the completed v2 run; it performs discovery but no new scoring. Do not resume the old v1 run with the new factory: the configuration mismatch is intentionally rejected. The original pilot documentation describes its historical v1 runtime.
