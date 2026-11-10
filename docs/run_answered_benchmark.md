# Run an answered benchmark: desktop to icelab

Run commands in PowerShell from the repository root after [desktop setup](../README.md#desktop-setup--powershell). No tested-model answer generation occurs here.

| Need | Existing execution path |
|---|---|
| Check/resume a recorded CORE experiment | Locked provisional research workflow: section A |
| Evaluate new M1–M7 questions/answered datasets | Generic approved-frozen workflow: sections 1–5 |
| Arbitrary new dataset with the two additional metrics | Not currently a generic CLI; `general_quality_run` is tied to its recorded dataset |

Do not replace inputs or reuse historical run IDs for new data. A changed dataset/configuration needs a new version and genuine authorization. The generic approved-frozen factory differs from the fixed-JSON research v2 factory; do not mix scores across these protocols as if identical.

## 1. Transfer and preserve supplied answers

HPC cannot reach this project's icelab judge. Generate on HPC, transfer Excel/UTF-8 JSONL using your approved transfer method, then judge on a normal desktop with network authorization. Credentials remain in the desktop `.env`.

```powershell
New-Item -ItemType Directory -Force data\incoming\my_benchmark | Out-Null
# Place your supplied file in that folder first.
Get-FileHash data\incoming\my_benchmark\answered.jsonl -Algorithm SHA256
```

Keep responses unchanged, including repetition/truncation. Retain actual model repository/checkpoint, revision, generation run ID, prompt, temperature, top_p, token limits and completion metadata if available. Labels such as `apertus_answer` alone do not prove model identity.

## 2. Convert one selected model and validate

Source columns: `question_id`, `question`, `applicable_metrics` (unique explicit M1–M7 labels), selected answer column, and independent `reference_answer` plus `context_text` or `reference_context` as required by the metrics. Excel uses the active sheet and its header row. Applicability may be a JSON list or comma/semicolon-separated labels.

```powershell
.\.venv\Scripts\python.exe scripts\prepare_answered_dataset.py `
  --input data\incoming\my_benchmark\answered.jsonl `
  --output data\processed\my_benchmark_v1\cases.jsonl `
  --answer-column model_answer --model-variant my_model `
  --provenance "Actual generation source, model checkpoint and evidence provenance"
.\.venv\Scripts\python.exe -m canadianness_eval.cli validate-dataset `
  --input data\processed\my_benchmark_v1\cases.jsonl
```

Use `--answer-column gc_llm_answer --model-variant gc_llm` for that column in a wide source. Repeat separately for other models with distinct output files. The converter makes no judge requests and refuses to overwrite existing output. Other model answers and old scores are excluded. Generation metadata stays in the untouched source file rather than being copied into judge input.

You can also author the generic [JSONL schema](dataset_format.md) directly. To compare variants in one run, concatenate their converted JSONL files and validate that combined file: paired questions must share text, references and applicability. Generic paired-bootstrap exports recognize the special variant names `base` and `fine_tuned` only; other labels still receive per-model summaries.

The generic schema does not preserve CORE primary/secondary role fields. Retain the source for provenance; use section A for the recorded CORE role-aware protocol.

## 3. Supply genuine approved frozen definitions

**No human-approved frozen YAML is bundled in `config/frozen/`.** Existing provisional execution records do not satisfy this generic production gate.

If the team provides an approved frozen YAML, place it unchanged in `config/frozen/` and use its actual filename below. Otherwise a human must review selected steps, ordering, definitions and all rubric approvals in the existing review workbook before freezing. Do not regenerate steps or fill approvals automatically to pass the gate.

```powershell
# Only after this named human actually reviewed and approved the workbook:
.\.venv\Scripts\python.exe -m canadianness_eval.cli freeze-review `
  --workbook review\Canadian_Ness_GEVAL_Review.xlsx `
  --reviewer "Actual reviewer name" --version my_approved_v1
```

Output: `config/frozen/canadianness_geval_my_approved_v1.yaml`. Incomplete decisions are rejected and existing versions cannot be overwritten. This operation is not proof of empirical calibration. The historical research rubric and its checksums must remain unchanged.

## 4. Pilot, review, then evaluate

Prepare `pilot.jsonl` as a small genuine subset in the same generic schema. Include both languages, all applicable metrics, multi-metric cases and factual uncertainty where relevant. Check question/answer/evidence mappings and actual score explanations.

```powershell
.\.venv\Scripts\python.exe -m canadianness_eval.cli pilot `
  --input data\processed\my_benchmark_v1\pilot.jsonl `
  --frozen config\frozen\canadianness_geval_my_approved_v1.yaml `
  --output outputs\evaluations\my_benchmark_pilot_v1\results.jsonl

# After pilot review and actual permission to execute the full study:
.\.venv\Scripts\python.exe -m canadianness_eval.cli evaluate `
  --input data\processed\my_benchmark_v1\cases.jsonl `
  --frozen config\frozen\canadianness_geval_my_approved_v1.yaml `
  --output outputs\evaluations\my_benchmark_full_v1\results.jsonl
```

This generic runner is sequential; historical four-worker research settings do not change it. References/context are only populated according to the approved rubric parameters. Fixed evaluation steps/bands are supplied, without dynamic step generation during scoring.

## 5. Resume, monitor and export

Rerun the **identical evaluate command**. Its manifest must match dataset, frozen configuration, judge identity and package versions. Successful/N/A tasks are reused and failed/missing tasks can resume. A different experiment requires a different output path.

The command automatically writes `results.csv`, `summary.csv`, `status_counts.csv` and `paired_comparison.csv` beside the JSONL. This generic CLI does not produce the full CORE workbook. For a simple Excel review file:

```powershell
.\.venv\Scripts\python.exe -c "import pandas as pd; p='outputs/evaluations/my_benchmark_full_v1/'; pd.read_csv(p+'results.csv').to_excel(p+'results.xlsx', index=False)"
# In a separate terminal, read saved results without calling the judge:
Get-Content outputs\evaluations\my_benchmark_full_v1\results.jsonl -Tail 2 -Wait
```

Ctrl+C stops that watcher only. Check failure counts: a finished process is not proof every score succeeded. Failed/missing scores are excluded, not converted to zero.

## A. Recorded CORE provisional research workflow

These runners require 756 questions, 404 EN/352 FR, 756 primary and 1,058 secondary assignments. They are **not arbitrary-dataset importers**. Use [the run index](../results/run_index.csv) to select the exact model/condition.

Example: check/resume/export the completed cleaned GC LLM experiment:

```powershell
$plan = 'config/research/gc_llm_cleaned_responses_c4_20261107_v2/experiment.json'
$approval = 'config/research/gc_llm_cleaned_responses_c4_20261107_v2/execution_approval.json'
.\.venv\Scripts\python.exe -m canadianness_eval.research_run check --plan $plan --approval $approval
.\.venv\Scripts\python.exe -m canadianness_eval.research_run status --plan $plan --approval $approval
# Resume only if needed and the unchanged experiment remains authorized:
.\.venv\Scripts\python.exe -m canadianness_eval.concurrent_research --plan $plan --approval $approval
.\.venv\Scripts\python.exe -m canadianness_eval.research_run report --plan $plan --approval $approval
```

Use `research_run run --plan ... --approval ...` for historical sequential manifests. The concurrent command requires a manifest already prepared for concurrency; it does not upgrade a sequential run. CORE exports include full Excel/CSV/JSONL, enriched answers/references, independent primary/secondary scores and language/role/failure/retry summaries.

### Prepare a separately authorized repeat of the original Llama CORE input

The existing original workbook, normalized generations and prepared CORE cases must already exist; arbitrary replacement data will fail the strict matching checks.

```powershell
$newPlan = 'config/research/my_core_repeat_v1/experiment.json'
$newApproval = 'config/research/my_core_repeat_v1/execution_approval.json'
.\.venv\Scripts\python.exe -m canadianness_eval.research_run prepare `
  --plan $newPlan --run-id my_core_repeat_v1 --model llama `
  --cases data\processed\llama_756_v1\all_cases.jsonl `
  --generations data\incoming\Canadian-ness_Llama_756_Generations.jsonl
Get-FileHash $newPlan -Algorithm SHA256
```

Preparation prints the exact required statement. Obtain actual execution permission for the manifest hash, then record the real approver and verbatim authorized statement:

```powershell
.\.venv\Scripts\python.exe -m canadianness_eval.research_run authorize `
  --plan $newPlan --approval $newApproval --approved-by 'Actual authorizing person' `
  --statement 'Exact statement genuinely authorized for this run'
.\.venv\Scripts\python.exe -m canadianness_eval.research_run check --plan $newPlan --approval $newApproval
.\.venv\Scripts\python.exe -m canadianness_eval.research_run run --plan $newPlan --approval $newApproval
.\.venv\Scripts\python.exe -m canadianness_eval.research_run report --plan $newPlan --approval $newApproval
```

The placeholder statement is not approval and will not satisfy the exact-statement check. Execution permission is distinct from scientific or team approval. New answer sets require their own validated preparation contract rather than editing historical manifests.

### Recorded correctness/completeness queue

```powershell
.\.venv\Scripts\python.exe -m canadianness_eval.general_quality_run check
.\.venv\Scripts\python.exe -m canadianness_eval.general_quality_run status
# Only if the recorded authorized queue needs resuming:
.\.venv\Scripts\python.exe -m canadianness_eval.general_quality_run supervise
```

All 4,536 tasks are already complete. Combined outputs are in `outputs/queues/general_quality_cleaned_20261107_v1/`. The local supervisor checks every ten minutes and resumes routine failures; it cannot run while the desktop is shut down and does not send chat notifications.

## Report responsibly

Keep supplied answers/hashes, model-generation provenance, reference evidence, individual explanations, exact rubrics/manifests and failure accounting. State sampling uncertainty, evidence limitations, editing differences and human calibration status. A rubric score is not a percentage of factually correct claims. Do not invent an overall weighting policy.
