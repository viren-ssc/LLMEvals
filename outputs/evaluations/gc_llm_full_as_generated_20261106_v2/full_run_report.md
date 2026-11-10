# gc_llm provisional research run: gc_llm_full_as_generated_20261106_v2

**AI-provisional, pending calibration**. Scientific/team approval and empirical calibration have not been conferred.

Successful: 1814/1814; failed/skipped: 0; pending: 0.

| Metric | Planned | Scored | Mean |
|---|---:|---:|---:|
| M1 | 76 | 76 | 0.6421 |
| M2 | 234 | 234 | 0.4491 |
| M3 | 327 | 327 | 0.4303 |
| M4 | 112 | 112 | 0.6000 |
| M5 | 174 | 174 | 0.4638 |
| M6 | 253 | 253 | 0.4091 |
| M7 | 638 | 638 | 0.4766 |

Language and assignment breakdowns are in all_metric_summaries.csv and full_results.xlsx. Failed/pending records never count as zero scores. No combined Canadian-ness score is calculated.

## Known limitations

- Booster-seat M3 conditional-guidance credit and M6 extra-detail deductions remain inconsistent.
- Optional reference enrichment and scoring-band justification are not consistently handled.
- Institutional duty timing versus factual recall and exact within-band scores are human calibration decisions.
- Some ancillary factual claims and reference dates remain unverified by the supplied summaries.
- Evidence verification is the imported user benchmark attestation, not new local independent verification.
- Gateway-default sampling is not proven deterministic; weights/revision and deployment limits are not independently attested.
- No human calibration, team approval, overall weighting policy or scientific-validity approval is implied.

Individual questions, unchanged model responses, reference answers, supporting summaries, scores and reasons are in all_results.jsonl/CSV and full_results.xlsx. Primary-only/secondary-only files, failure/missing/retry reports, raw responses, session accounting and the locked experiment manifest are retained alongside them.
