# Full Llama provisional research run: readiness and execution permission

**Execution decision: NO-GO pending explicit user execution permission. Technical readiness is complete; no full-run scoring or new pilot was started.**

This follows the user's request to stop prompt refinement and run a full-size provisional experiment with recorded limitations. The new separately authorized research pathway uses the existing gateway, v2 fixed-rubric factory and metric-checkpoint engine. It does not call or modify freeze-review/load_frozen, create a scientific FROZEN artifact, or authorize production release. Historical pilot hold decisions and both pilot result directories remain unchanged.

## Locked experiment

- Run ID: `llama_full_20261106_v2`; model `llama`; judge `gpt-oss-120b`.
- Evaluator: `final-json-factory-v2`; rubric version: `2026-11-03-v1`.
- Rubric SHA-256: `bb9889807b7babc8feed6a97ddd0c12c0fa334627e5d295017167fbd0a767cb2`.
- Evaluator-template SHA-256: `ecb714aa746f7bdce82d86fd9bcc288d4e26ffd15cfa210bbd19a356e095793f`.
- Experiment manifest SHA-256: `e77d107fc034465d373df8356be26d6cced4fb0d38debe4d2090fd8f357e45df`.
- Exactly 756 unique questions and successful nonempty Llama answers; 404 EN / 352 FR; 1,814 unique assignments, 756 primary and 1,058 secondary. All applicable metrics and original answers/reference text are preserved; every evidence gate passes under the existing user-attested benchmark provenance.
- All 42 steps and 35 rubric bands are unchanged. Neither pilot is re-scored or counted as completed full-run work.
- The experiment manifest locks input-file hashes, software hashes, package/Python versions, endpoint, timeout, output policy, all task keys and both protected pilot artifact ledgers. Changes are rejected on restart; software/configuration drift stops execution before the next task.
- Results will be labelled **AI-provisional, pending calibration**. Scientific validity, team approval and empirical rubric calibration remain explicitly false.

Files: [locked experiment](../config/research/llama_full_20261106_v2/experiment.json), [pending permission request](../config/research/llama_full_20261106_v2/approval_request.json), [machine-readable readiness](../config/research/llama_full_20261106_v2/readiness_report.json).

## One explicit execution approval action

Reply in this chat with the following confirmation (or run the authorize command yourself as the authorizing user):

> I authorize run llama_full_20261106_v2: 1,814 llama metric evaluations using the locked v2 configuration, labelled AI-provisional, pending calibration. This is execution permission only, not scientific or team approval.

This approval covers one full experiment and same-configuration resumption of missing/failed tasks. It acknowledges the limitations recorded in the manifest; it does not approve scientific validity or grant team approval. No additional rubric adjudication is required by the provisional execution gate. The production-release frozen gate remains separate and unchanged.

Only after that explicit permission is actually given, Codex can record it and execute without routine approval checkpoints. The permission record is exclusive, tied to the exact experiment SHA-256, and may not be invented from this pending request. Local JSON integrity binds configuration; it is not a cryptographic identity-signature system.

PowerShell commands, from the project directory:

```powershell
.\.venv\Scripts\python.exe -m canadianness_eval.research_run check
# Authorizing user action only; do not run before deciding to grant permission:
.\.venv\Scripts\python.exe -m canadianness_eval.research_run authorize --approved-by "YOUR NAME" --statement "I authorize run llama_full_20261106_v2: 1,814 llama metric evaluations using the locked v2 configuration, labelled AI-provisional, pending calibration. This is execution permission only, not scientific or team approval."
# Executes the full experiment once a valid permission record exists:
.\.venv\Scripts\python.exe -m canadianness_eval.research_run run
```

No permission record exists yet. Calling run now fails before a gateway is constructed or a network request is made.

## Independent progress monitoring

In a separate PowerShell terminal:

```powershell
.\.venv\Scripts\python.exe -m canadianness_eval.research_run watch
# One snapshot:
.\.venv\Scripts\python.exe -m canadianness_eval.research_run status
```

The monitor only reads files, refreshing every five seconds. It shows successful, failed/skipped, pending and last-task status. Ctrl+C stops the monitor, not the evaluation. A stale last-task timestamp can mean the evaluation process is stopped; the monitor does not claim liveness solely from checkpoint presence.

## Persistence, retries and exports

- Requests remain sequential with a 180-second request timeout. Existing bounded transient/validation retries remain (at most nine scoring HTTP attempts per logical metric call). HTTP 429 Retry-After values up to 60 seconds are respected; a longer wait or sustained rate limiting stops safely after preserving work for later resumption.
- An exclusive process lock prevents concurrent writers. Every metric raw response and attempt checkpoint is published immediately; the JSONL stream is recoverable from checkpoints if interrupted. The run command automatically resumes only missing and failed tasks, retaining prior attempts and skipping successful scores.
- Authentication failure, sustained rate limiting, five consecutive failed tasks or changed software/configuration causes a safe stop. These are operational failures, not routine human approval checkpoints. Restore access/the unchanged configuration and use the same run command to resume.
- API-reported token usage includes failed/retried attempts when supplied. Missing usage and interrupted/in-flight requests are reported as unknown rather than fabricated zero counts. Request timestamps, latency, responses and status codes are retained; credentials are excluded.
- Completion or interruption rebuilds detailed JSONL/CSV and an Excel workbook. Files include all tasks with explicit pending/failure states, primary-only/secondary-only results, original questions/answers/reference summaries, per-metric/language/role means, attempt/retry/failure/missing reports, session/token accounting and manifests. Failed/missing scores remain null and never enter means as zero.
- The generated full_run_report.md contains success/failure totals and per-metric means. No arbitrary overall Canadian-ness score is computed.

Expected results directory: `outputs/evaluations/llama_full_20261106_v2/`. Core files after execution: `all_results.jsonl`, `all_results.csv`, `primary_results.*`, `secondary_results.*`, `all_metric_summaries.*`, `full_results.xlsx`, `full_run_summary.json`, `full_run_report.md`, `attempts.*`, `retry_report.*`, `failures.*`, `missing_tasks.*`, `records/`, `raw/`, `sessions/`.

Future GC LLM/Apertus experiments use the same pinned evaluator/rubric and generic model-aware result/checkpoint keys, with independently validated generation files, cases, distinct run IDs, separate manifests and explicit execution permissions.

## Known limitations accepted for experiment scope, not erased

- Booster-seat M3 conditional-guidance credit and M6 extra-detail deductions remain inconsistent.
- Optional reference enrichment and scoring-band justification are not consistently handled.
- Institutional duty timing versus factual recall and exact within-band scores are human calibration decisions.
- Some ancillary factual claims and reference dates remain unverified by the supplied summaries.
- Evidence verification is the imported user benchmark attestation, not new local independent verification.
- Gateway-default sampling is not proven deterministic; weights/revision and deployment limits are not independently attested.
- No human calibration, team approval, overall weighting policy or scientific-validity approval is implied.

Offline verification: 128 regression tests passed, one explicit live test was deselected. Following final run-isolation/task-binding safeguards, all six focused research-run tests passed again. Tests used temporary synthetic permissions and mocked HTTP only; no real user/team approval was generated. The real pending package was then validated with zero live requests.
