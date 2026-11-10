# Architecture and version compatibility

The project runs locally on Windows/Python 3.13. Filesystem paths use pathlib. `settings.py` loads `.env`, allowing environment-variable overrides, and wraps the key in Pydantic SecretStr. `api_client.py` is the sole model transport; it uses httpx against the configured HTTPS gateway with verification enabled, redirects disabled, bounded transient retries, sequential requests and schema validation. No OpenAI SDK defaults or other LLM provider are involved.

`model_discovery.py` normalizes punctuation, prefixes and deployment names before matching GPT-OSS-120B; multiple matches and no matches are errors. Arbitrary aliases that do not identify their underlying model require an explicit accessible ID override. Metadata preserves the actual deployed ID, but an ID alone cannot establish immutable model weights; ask the gateway operator for deployment revision provenance in a publication.

`RemoteJudge` subclasses the installed `DeepEvalBaseLLM` and implements load_model, generate, a_generate, and get_model_name. Schema requests return validated Pydantic instances; plain requests return strings. Async generation uses a worker thread; orchestration intentionally remains sequential.

Inspected DeepEval **4.3.2**, official docs accessed **2026-11-03**:

- [GEval and custom template extension](https://deepeval.com/docs/metrics-llm-evals)
- [Custom LLM contract including schema](https://deepeval.com/guides/guides-using-custom-llms)
- Installed `deepeval/metrics/g_eval/g_eval.py`, `utils.py`, `schema.py`, and `metrics/utils/decision.py`.

Current GEvalTemplate is generated dynamically and its official method accepts **keyword arguments**. `ResearchTemplate` calls the documented `generate_evaluation_steps(parameters=...,criteria=...)` extension point, retaining the installed prompt and changing its default 3–4 step instruction to 5–8. Every proposal has a new GEval instance and an independent adapter invocation with the same criteria; earlier responses never enter later prompts. Steps are validated as 5–8 nonempty strings, preserving original text and raw response payloads.

This uses the explicitly permitted version-compatible GEval template invocation, rather than private `_generate_evaluation_steps` methods or a full measure call. **No illustrative scoring call is needed to obtain steps**, so there are 28 logical proposal requests plus the connection probes (more HTTP requests only on retries). Original prompts, raw response objects, request-attempt count, timing, signature and settings are persisted. Cache resumption reads already successful files; it is never reported as a new generation. Existing attempts are archived before explicit regeneration or failed-attempt replacement.

Actual scoring calls public GEval.measure with the custom adapter, native Rubric objects, frozen evaluation steps and rubric guidance. DeepEval normalizes the 0–10 result using the rubric's full span; we validate the resulting score, without applying a second normalization. No adapter logprob capability is exposed, so DeepEval's documented custom-model schema fallback is used. Sampling is recorded honestly as gateway default; temperature and seed are not assumed supported or silently advertised as fixed.

The evidence test exercises real installed GEval with a mocked HTTP boundary and asserts independent context and expected-answer sentinels reach the judge prompt. `CONTEXT` is explicitly included in evaluation parameters for M2/M3/M5/M6/M7; only INPUT and ACTUAL_OUTPUT are populated for M1/M4. Required evidence fields map to approved parameters and missing values fail the applicable metric.

Review modules keep proposals separate from human decisions. Workbook formulas are convenience indicators; freezing reads actual selections and approvals, validates definition provenance, creates an exclusive versioned file and hashes the canonical payload. Evaluation rechecks that hash. This is integrity checking, not cryptographic identity verification of the human reviewer.

No evaluation framework reporting helper is invoked. Environment privacy switches are set before DeepEval import: `DEEPEVAL_TELEMETRY_OPT_OUT=YES`, `CONFIDENT_TRACE_FLUSH=NO`, and update warnings opt out. Model traffic goes only through the explicit httpx gateway client. The read-only watcher polls local result files and displays complete responses, not streamed tokens.
