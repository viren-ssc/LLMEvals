# Cleaned three-model correctness and completeness queue

All results are **AI-provisional, pending calibration**. The user's supplied definitions and explicit execution instruction authorize this research experiment; they do not establish scientific calibration or team approval.

The source is `Canadianness_General_Correctness_Completeness_Proposed_v1.md`. Its six evaluation steps and five raw scoring bands per metric were extracted verbatim, together with the common rules and metric boundaries. All three models use those same definitions and existing fixed-step G-Eval scoring. No dynamic step generation is permitted.

- Source Markdown SHA-256: `4d4c49fcba9666b22676bc36f408dd71676621873c148c038d49eb0d72d88294`
- Extracted definitions SHA-256: `22acc150ba9d6d5f75b223bbfe5ac1bce0178168bb301dc01ae139199a8ab8cc`
- Authorized experiment SHA-256: `b1797408a95cf0871fdd5df781d210bb174174ce6a899d6aa3855fe3104ad0ce`

The definition checksum printed in the source is retained as provenance; the original serialized payload needed to reproduce that checksum was not supplied. The hashes above independently bind the actual source bytes and extraction.

The frozen configuration and execution authorization are in `config/general_answer_quality/2026-11-07-user-v1/`. Each model has 756 cleaned answers and 1,512 tasks, for 4,536 tasks overall. Llama, GC LLM and Apertus run sequentially with four concurrent metric tasks per model, using gpt-oss-120b and the existing gateway, timeout and retry protections. Sampling parameters remain omitted, as in the existing evaluator configuration.

The supervisor waits for the existing cleaned M1–M7 queue's successful completion marker before starting. It checks every 600 seconds and resumes missing or failed metric tasks without rescoring completed tasks. Integrity failures stop execution. Selected-model responses are isolated from other model answers and previous judgments. Context remains judge-side evidence. Existing M1–M7 rubrics and results are preserved.

Offline verification passed three tests covering exact extraction, fixed-step scoring, normalization, model isolation, evidence flags, bounded concurrency and checkpoint recovery. A separate 24-capture prompt audit covered both metrics, English/French and all three models without live judge calls.

From the project directory, inspect progress without judge calls:

```powershell
.\.venv\Scripts\python.exe -m canadianness_eval.general_quality_run status
Get-Content .\outputs\queues\general_quality_cleaned_20261107_v1\supervision.jsonl -Tail 10 -Wait
```

Individual records and exports are written under `outputs/evaluations/{model}_general_quality_cleaned_20261107_v1/`. Combined workbooks, matched comparisons and summaries are written under `outputs/queues/general_quality_cleaned_20261107_v1/` after completion. Scores, explanations, reference evidence, evidence-review flags, retry reports and configuration metadata are retained. No arbitrary combined quality score is calculated.
