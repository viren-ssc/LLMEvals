# Local evaluation preparation — observed 2026-11-06 UTC

Connectivity status: **READY**. Verified HTTPS base:
`https://litellm.dsai-sdia.ssc-spc.cloud-nuage.canada.ca/v1`.
Authenticated `/models` resolved the exact deployed ID `gpt-oss-120b`;
the completion metadata also identified `gpt-oss-120b`. DNS resolved and TLS
verification remained enabled. Existing private credentials worked.

The restricted agent network failed initially. An unrestricted check authenticated
successfully; its first completion timed out at 15 seconds. A subsequent adapter
check with a 90-second timeout returned `READY` in 0.338 seconds; native JSON-schema
output returned `answer=READY` in 0.457 seconds. Installed DeepEval GEval then
successfully scored one synthetic flag example through the unchanged supplied M1
metric (2.010 seconds, one discovery plus one scoring HTTP request). These are
smoke observations, not throughput, determinism, or scientific-validity estimates.
No benchmark questions were submitted. No HPC access occurred.

## Environment and configuration

Reused `.venv`: Python 3.13.1, DeepEval 4.3.2. No dependencies installed or upgraded.
The existing `RemoteJudge` implements sync/async/schema calls and model identity.
The existing gateway enforces TLS, disables redirects, bounds retries and validates
schema responses; it has an explicit prompted-JSON fallback for schema rejection.
Gateway sampling defaults remain recorded as defaults: no fixed seed or temperature
support was verified. Timeout defaults to 180 seconds.

Private `.env` uses **LLM_KEY**, **LLM_BASE**, **LLM_MODEL**, and
**LLM_TIMEOUT_SECONDS**, as documented in `.env.example`. Existing values suffice;
no credential changes are required. `LLM_MODEL=auto` currently resolves uniquely;
`LLM_MODEL=gpt-oss-120b` pins the routing identifier, not immutable model weights.
Secrets and outputs remain ignored. For future model-listing failures the existing
client stops; operator confirmation/adaptation is required rather than guessing.

## Incoming dataset contract

Added `canadianness_eval.hpc_ingestion`, separate from the historical JSONL loader.
It validates the seven requested benchmark columns, unique string question IDs,
nonblank questions/reference answers, language labels, and explicit M1-M7
applicability including the primary metric. Question, answer and context text are
preserved. Excel reads the active worksheet; IDs must be stored as text. Metrics
can be a JSON array or comma/semicolon-separated labels (without spaces).

Wide results must include `gc_llm_answer`, `apertus_answer`, `llama_answer`.
Normalized results use `question_id`, `evaluated_model` (`gc_llm`, `apertus`,
`llama`), `answer`, and `status` (`success` for usable generations).
Extra generation metadata/settings are retained. Failed, absent and blank answers
are reported, never filled. Joins use identifiers; duplicate and unknown IDs/model
labels fail. Agree these field names with the HPC export owner before transfer.

Excel and JSONL use installed dependencies. Parquet loading is implemented through
pandas but requires optional `pyarrow` (not installed/verified in this task).
Parquet execution remains untested; install an engine only if this format is chosen.

Offline preparation commands (PowerShell, from project root):

```powershell
.\.venv\Scripts\python.exe -m canadianness_eval.hpc_ingestion data/incoming/benchmark.xlsx
.\.venv\Scripts\python.exe -m canadianness_eval.hpc_ingestion data/incoming/results.xlsx --wide
.\.venv\Scripts\python.exe -m canadianness_eval.hpc_ingestion data/incoming/benchmark.xlsx --generations data/incoming/generations.jsonl
```

Default count is 756. Use `--expected-count 2` only for the synthetic fixtures in
`tests/fixtures/preparation/`. Before generations arrive, all answer slots are
reported missing; this does not invalidate the benchmark itself. Confirm 404
English/352 French distribution on the actual final artifact.

## Rubrics, results and execution boundary

All seven supplied metric definitions load: 42 fixed steps. Source
`Canadianness_Final_GEVAL_Metrics.json` and versioned
`config/final/2026-11-03-v1/metrics_final.json` have matching SHA-256 hashes.
No rubric/step artifacts were modified. Their recorded status is
`ready_for_team_review_and_calibration_not_empirically_frozen`.
The newer `v1_20261103.json` was preserved; confirm which artifact is authoritative
before production integration. The existing final-metric factory wires supplied
steps and native rubric bands to GEval; scores remain native 0–1 without a second
division. The new `EvaluationResult` schema includes requested IDs, language,
metric, versions, run/time, score/reason, status and error fields; non-success
records cannot carry scores.

The import CLI only validates and plans; it does not execute evaluations. Existing
legacy evaluator/calibration runners already persist individual attempts and
resume using configuration/dataset/judge manifests. They have different input
schemas and approval gates. Do not pass the new wide/normalized export directly
to the legacy `evaluate` command. A production bridge must be reviewed once the
final benchmark and authoritative rubric are confirmed. It must retain language,
primary metric, original metadata and run/version identifiers, and use the existing
checkpoint safeguards. No automatic scientific approval was introduced.

Context is supporting evidence, not an infallible verbatim source. Production
integration must preserve the finalized rules for alternative correct answers,
M6 uncertainty, required evidence and metric applicability. No replacement
methodology was created in this preparation.

Workload planning counts only usable answer/metric pairs. With all generations,
there are 2,268 answers and at most 15,876 metric evaluations; fixed steps imply
one baseline scoring request each, with additional schema/validation/network
retries possible. Existing gateway nesting permits up to nine HTTP attempts per
logical generation; stop/review repeated failures. Actual context limits, output
token budget, rate limits and deployment revision require operator confirmation.
Keep requests sequential initially; synthetic latency is insufficient for capacity
planning. A production bridge must check token budgets and checkpoint every result.

## Verification and remaining inputs

Offline suite: **117 passed, 1 live test deselected**; after adding result-schema checks, the focused ingestion suite passed **10/10**. Initial sandbox runs hit
Windows temp-directory access errors; the successful full run used an unrestricted
process with `--basetemp=.tmp/preparation-20261106-b`. Ruff passed for new Python
files. Both wide and reordered normalized fixture imports report six answer slots,
one failed/missing generation and five metric evaluations.

Required next: finalized 756-question spreadsheet, HPC export and metadata contract,
authoritative finalized rubric/version and its approval decision, deployment limits,
and explicit authorization before any full evaluation. Live judge access is ready;
full production dataset-to-evaluation wiring is intentionally pending those inputs.

