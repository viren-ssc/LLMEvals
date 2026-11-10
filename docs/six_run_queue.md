# Six-run original and cleaned response experiment

All results are **AI-provisional, pending calibration**. User execution permission does not constitute scientific, team or empirical calibration approval.

The additive queue preserves the active three-run queue and its frozen manifests. The execution order is:

1. Llama, original mixed-temperature workbook.
2. GC LLM, original mixed-temperature workbook.
3. Apertus, original mixed-temperature workbook.
4. Llama, user-provided cleaned JSONL.
5. GC LLM, user-provided cleaned JSONL.
6. Apertus, user-provided cleaned JSONL.

Each run contains 756 questions and 1,814 independent metric judgments: 756 primary and 1,058 secondary. The six-run total is **10,884**. Models and response variants have distinct immutable manifests, authorization records, checkpoints and output directories. Four workers are shared within the single active run; different runs never execute simultaneously.

The original source workbook SHA-256 is `2c28b3a8aadda242394e047b092a2c25913844ea498f2207a72a869710e6dd15`. The cleaned JSONL SHA-256 is `c5490703a827764f63e0ce436f098365fcec8c7981c362a7062bb32022344610`.

The cleaned source changes 8 Llama, 269 GC LLM and 140 Apertus answers relative to the original workbook. Every changed string is shorter. This is a user-edited-response experiment: score improvements or declines do not by themselves establish judge bias. Unchanged responses are scored afresh and analyzed separately to expose repeat-judging variation. Generation settings and cleaning-method metadata are not supplied in the cleaned JSONL and are not inferred from earlier datasets. No extra cleaning or answer generation is performed. Original line endings are preserved.

Both phases use the unchanged final-json-factory-v2 scorer, gpt-oss-120b judge, 42 evaluation steps and 35 rubric bands. Judge temperature remains omitted. Each request contains only its selected model/variant answer, question, metric-permitted reference evidence and fixed rubric. Other models' answers, prior judgments, cleaning flags and comparison scores are excluded. Comparisons are computed only after independent scoring completes.

The original phase uses `config/research/mixed_temperature_three_model_queue_v1/queue.json`. The appended phase uses `config/research/cleaned_three_model_queue_v1/queue.json`. The latter waits for all three original runs to finish before starting. Both supervisors check every ten minutes using local Python, with no chat-model monitoring calls. Routine failures resume only missing/failed tasks. Integrity failures or three consecutive no-progress restart attempts stop the affected supervisor for investigation.

Watch both phases with the existing monitor:

```powershell
Get-Content "C:\Users\BhanderV\Desktop\LLMEvals\outputs\queues\mixed_temperature_three_model_queue_v1\supervision.jsonl" -Tail 10 -Wait
```

The appended supervisor mirrors its events into that log. Each phase also keeps its own logs under `outputs/queues/`. Closing the monitor does not stop the runs. Temporary per-process Windows sleep-prevention requests cover the overnight queue without changing power-plan settings.

Individual cleaned run outputs use `outputs/evaluations/{model}_cleaned_responses_c4_20261107_v2/`. They include Excel, CSV, JSONL, primary/secondary and English/French summaries, raw judge responses, attempts, failures/retries and input provenance.

After all six finish, `outputs/queues/cleaned_three_model_queue_v1/final_results/` receives:

- `six_run_original_vs_cleaned_results.xlsx`
- `all_six_run_results.csv` and `.jsonl`
- `original_vs_cleaned_metric_pairs.csv` and `.jsonl`
- `original_vs_cleaned_summaries.csv` and `.jsonl`
- `final_report.md`

The paired analysis preserves every answer, score and explanation, with separate metric, language, role and changed/unchanged-answer breakdowns. No arbitrary overall Canadian-ness score is calculated.
