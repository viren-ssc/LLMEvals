# gc_llm: general correctness and completeness

AI-provisional, pending calibration

Successful 1512/1512; failed 0; pending 0.

| Metric | Successful | Mean score | Evidence review flags |
|---|---:|---:|---:|
| completeness | 756 | 0.4636 | 114 |
| correctness | 756 | 0.4821 | 73 |

The user-supplied six steps and five bands for each metric are fixed across all models. Scoring uses the existing G-Eval factory, question, selected cleaned response, reference answer and judge-side supporting context. Other model responses and prior scores are excluded. Every score, explanation, evidence-review flag, raw response, attempt and retry is retained. No additional cleaning, answer generation, dynamic step generation or second normalization occurred. There is no combined overall score.

Judge sampling uses the gateway default and is not established deterministic. Imported benchmark evidence is not new independent verification. User execution permission is not empirical calibration or scientific/team approval.

Definition SHA-256: `22acc150ba9d6d5f75b223bbfe5ac1bce0178168bb301dc01ae139199a8ab8cc`

Source Markdown SHA-256: `4d4c49fcba9666b22676bc36f408dd71676621873c148c038d49eb0d72d88294`

Files: full_results.xlsx, all_results.*, correctness_results.*, completeness_results.*, metric_summaries.*, evidence_review_required.*, failures.*, missing_tasks.*, attempts.*, retry_report.*, raw/, records/, sessions/.
