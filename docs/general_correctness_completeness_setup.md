# Next test: general correctness and completeness

Status: **WAITING_FOR_USER_STEPS_AND_RUBRIC**. No judge calls, scoring runs or queue entries have been created for this test. The existing authorized Canadian-ness queue continues independently.

The cleaned JSONL is the sole response source. Its SHA-256 is `c5490703a827764f63e0ce436f098365fcec8c7981c362a7062bb32022344610`. Preparation preserves every selected answer string, all 756 question IDs, question language, reference answers and supporting summaries. Each independent case contains only its selected model's response; other models' responses and previous scores/explanations are excluded.

Planned workload:

| Model | Questions | Correctness | Completeness | Total |
|---|---:|---:|---:|---:|
| Llama | 756 | 756 | 756 | 1,512 |
| GC LLM | 756 | 756 | 756 | 1,512 |
| Apertus | 756 | 756 | 756 | 1,512 |
| Total | 2,268 model-question cases | 2,268 | 2,268 | 4,536 |

Both new metrics are planned for every question-model pair. The original Canadian-ness primary/secondary assignments are retained as provenance; they do not limit applicability of these new general metrics. No overall combined score or scientific approval is implied. All future results must remain **AI-provisional, pending calibration**.

## What DeepEval 4.3.2 supplies

The installed public metrics module was inspected directly. It provides `GEval`, `ConversationCompletenessMetric`, `FaithfulnessMetric`, `AnswerRelevancyMetric`, `JsonCorrectnessMetric`, `ToolCorrectnessMetric` and related metrics. It does not export dedicated general single-answer `AnswerCorrectnessMetric` or `AnswerCompletenessMetric` classes.

- `GEval` is the built-in framework suitable for the two user-defined single-answer metrics.
- `ConversationCompletenessMetric` measures satisfaction of user intentions over a conversation, not required-information coverage of one answer against this benchmark.
- JSON/tool correctness assess structure/tool use, not factual answer correctness.
- Faithfulness concerns consistency with retrieval context. These are closed-book model responses with reference evidence reserved for the evaluator, so retrieval faithfulness is not a direct substitute for answer correctness.

G-Eval's API accepts criteria or explicit evaluation steps. Inspection of the installed `_generate_evaluation_steps` confirms that it returns supplied steps unchanged when present and otherwise calls a judge to generate them. Explicit fixed steps avoid that dynamic generation. A rubric is optional in the API, but fixed supplied bands make the intended scoring anchors explicit and common to all three models. Built-in metrics have their own prompts and calculations; using one would not automatically implement the requested definitions of correctness and completeness.

Official references:

- [G-Eval](https://deepeval.com/docs/metrics-llm-evals)
- [Answer correctness guide](https://deepeval.com/guides/guides-answer-correctness-metric)
- [Conversation completeness](https://deepeval.com/docs/metrics-conversation-completeness)

Current online documentation may describe versions newer than the pinned local 4.3.2 environment; the installed code is authoritative for this setup.

## User-controlled definitions and execution boundary

`config/general_answer_quality/v1/metrics_user_supplied.json` contains two empty definition slots. Both `evaluation_steps` and `rubric` are deliberately null. No steps, rubric bands or scoring criteria were invented or auto-generated. The user will supply them.

Before scoring, both metrics must use the same versioned steps, bands and question/reference evidence for all models, with recorded checksums. Required-answer coverage must be distinguished from optional reference enrichment according to those supplied definitions. Judge configuration must also be identical across the three runs and recorded before execution. Preferred concurrency remains four; inference settings are not silently changed by this offline setup.

This setup module exposes only `prepare` and `check`; it has no scoring or queue command. `check` returns NO-GO while either metric lacks user definitions, and does not grant execution permission even once definitions are populated. Existing M1-M7 definitions, their 42 steps, 35 bands, frozen manifests and ongoing runs are unchanged.

Prepared files:

- `config/general_answer_quality/v1/setup_manifest.json`
- `config/general_answer_quality/v1/metrics_user_supplied.json`
- `data/processed/general_answer_quality_cleaned_v1/shared_question_evidence.jsonl`
- `data/processed/general_answer_quality_cleaned_v1/{model}/cases.jsonl`
- `data/processed/general_answer_quality_cleaned_v1/planned_tasks.jsonl`
- `data/processed/general_answer_quality_cleaned_v1/validation_manifest.json`

Readiness check, without any judge requests:

```powershell
.\.venv\Scripts\python.exe -m canadianness_eval.general_quality_setup check
```
