# Interpret results and provenance

All four experiments are **AI-provisional, pending calibration**. They are rubric-based assessments by gpt-oss-120b, not human-adjudicated truth or team approval.

## What the comparisons hold constant

The first three experiments use the seven-metric research rubric `2026-11-03-v1` and evaluator `final-json-factory-v2`, preserving all 42 steps and 35 bands. Per model/condition, 756 answers yield 1,814 independent metric tasks (756 primary, 1,058 secondary). The fourth experiment adds correctness and completeness to all 756 cleaned answers per model, yielding 1,512 tasks per model under one shared two-metric definition artifact.

No arbitrary overall Canadian-ness score is justified. Correctness, completeness and M1–M7 remain separate measurements. Mean scores are on 0–1; they are not percentages of independently verified facts.

## What is not independently established

- **Generation temperature:** original and workbook conditions are user-labelled temperature 0 and 0.7. Not every source captures these settings. GC LLM's workbook explicitly contains 755 temperature-0.7 answers plus one reused temperature-0 answer. Do not infer another model's top_p from Llama's reported setting.
- **Model identity:** original GC LLM rows record the generic ID `gc_llm` and revision `58277e94d16ccf486c1702c0aac8115c69448585`; Apertus records `apertus` and revision `0f2767662a013c0fb631079cea883155252bc3b6`. Those labels/hashes do not identify a repository, size, weights or served deployment without upstream generation logs. The cleaned source has no model-identity fields. No conclusion that a random model was substituted follows from these gaps; identity is not independently proven.
- **Cleaning effects:** cleaned strings are user-supplied edits, not fresh generations. Edited content can differ in meaning or coverage. Unchanged answers also receive different scores when judged again; observed changes are not a clean causal estimate of repetition bias.
- **Judge sampling:** temperature/top_p were omitted/server-default. Determinism and deployment weight identity were not independently attested.
- **Evidence:** reference/context was imported from the benchmark. Context is supporting judge evidence, not necessarily input seen by the tested model, a verified verbatim quotation, or infallible truth. Unsupported claims are not automatically false.
- **Language:** English/French comparisons involve 404/352 questions and potentially different topic/difficulty distributions, not necessarily matched translations.
- **Rubric consistency:** technical success does not guarantee every explanation follows the intended band. Human review should check material contradictions, optional-detail deductions, unsupported-versus-false distinctions and required-element coverage.

Preserve every answer and reasoning record. Evidence-review flags identify cases for inspection, not automatic model errors. Unknown model identity or inference metadata should be reported as missing, not guessed from answer style.
