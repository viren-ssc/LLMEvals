# Canadian-ness GEval research framework

For **local reference-answer verification** with Excel/JSONL inputs, SQLite resume, actual source retrieval, and proposed-update exports, see [the verification guide](docs/local_verification.md). Run `python -m canadianness_eval.verification.cli --help`. This workflow is separate from G-Eval response scoring and requires no Google credentials.

The improved engine uses [evidence IDs, soft-failure detection, source discovery, and explicit needs-more-evidence statuses](docs/verification_evidence_ids.md). That guide also contains the commands to resume the repeated ten-question pilot and generate its comparison report.

This project uses the supplied Canadian government LiteLLM gateway and GPT-OSS-120B to propose and score seven distinct Canadian-ness dimensions. Researchers select and edit proposals before freezing a version for experiments. No overall Canadian-ness score is calculated.

**Before transmitting nonpublic or sensitive material, the team must confirm dataset-sharing authorization for this gateway.** Credentials belong only in `.env`, which is excluded from Git. TLS verification stays enabled. DeepEval telemetry and trace flushing are disabled before import; the code never uses Confident reporting, `evaluate()` uploads, or a default provider model.

## Use the installed environment (PowerShell)

The virtual environment is already created and dependencies installed. Work from this folder:

```powershell
.\.venv\Scripts\Activate.ps1
python -m canadianness_eval.cli check-connection
python -m canadianness_eval.cli prepare-review
```

If PowerShell blocks activation, use `.\.venv\Scripts\python.exe` instead of `python`; no execution-policy change is necessary. Only `LLM_KEY` in `.env` needs manual configuration. The default URL, model discovery, four runs, and timeout are preconfigured. An explicit `LLM_MODEL` override is optional for ambiguous deployment aliases; an unrelated model is never silently substituted.

The preparation command checks discovery and plain/structured responses, runs four independent proposals for each metric, saves original completions and failures, groups candidates, and creates `review/Canadian_Ness_GEVAL_Review.xlsx`. Run progress is printed immediately. For a read-only viewer in another terminal:

```powershell
python -m canadianness_eval.cli watch
```

The viewer displays saved steps and pilot scores/reasons as each request finishes. It does not stream individual tokens. Ctrl+C stops only the viewer. `watch --once` prints a snapshot. The run just prepared may already have completed; its responses remain viewable.

Existing successful generations are resumed without model calls. An existing workbook is protected to preserve reviewer edits: choose a different `--workbook` filename for a new preparation. A changed metric/model/template signature is rejected on resume. `--force` explicitly regenerates proposals and archives previous run JSON under `history/`. This never changes frozen definitions.

```powershell
python -m canadianness_eval.cli prepare-review --runs 3 --workbook review/Three_Run_Review.xlsx
python -m canadianness_eval.cli prepare-review --offline --workbook review/Offline_Review.xlsx
```

Offline preparation uses only existing generations (or produces a blank candidate sheet if none exist); it never invents judge outputs. Generation files live at `outputs/generations/M1/run_01.json` through M7. Consolidated CSV, coverage proxies and the run report live in `outputs/consolidated/`.

## Review, approve, and freeze

The workbook contains four sheets:

1. **Step Candidates:** preserve original text and provenance; choose Keep, Reject, Revise or Undecided. Decisions start blank. For every chosen step enter a unique positive integer `final_order` within its metric. Revise requires `edited_final_wording`; Keep can also carry an explicit edit. Unselected rows remain unselected.
2. **Metric Coverage:** inspect lexical coverage proxies, redundant groups, and possible omissions alongside definitions, boundaries and evidence parameters. Keyword hits are not semantic proof of coverage.
3. **Rubric Review:** edit each behavioral description and guidance as needed. Guidance must remain the same across the five bands for a metric. Set all five `approved` cells to Yes only after reviewing them. Score bands must cover native integers 0–10 without overlap: 0–2, 3–4, 5–6, 7–8, 9–10.
4. **Review Summary:** generation counts and live Excel formulas for chosen steps and rubric approvals. Excel recalculates these formulas; the freeze command independently validates actual cell values.

Review definitions and evidence requirements in `config/metric_definitions.yaml` and [metric boundaries](docs/metric_boundaries.md). If definitions change after workbook creation, create a new workbook; freezing checks the definition hash. YAML rubric drafts can be edited **before** workbook creation; once reviewing a workbook, its editable rubric cells are authoritative for that freeze.

The named reviewer must check semantic contradictions, construct overlap, omissions, and ordering. Automated validation detects obvious opposite-polarity instructions, malformed ranges, empty selections, duplicate orders, missing approvals and altered definition provenance; it cannot prove semantic consistency of arbitrary natural language.

```powershell
python -m canadianness_eval.cli freeze-review --reviewer "Your Name" --version v1
```

Issuing this command attests that the named human approves the selected steps, rubrics, definitions and evidence requirements. It never fills missing decisions. All seven metrics must be ready. Identical final steps are deduplicated in chosen order. `config/frozen/canadianness_geval_v1.yaml` records reviewer, date, full definitions, parameters, steps, rubrics and a canonical SHA-256 configuration hash. Existing frozen versions cannot be overwritten. A hash detects accidental modification, not malicious reapproval; retain reviewed versions in your controlled repository.

**No actual research configuration is automatically approved or frozen by this project.** Tests create temporary mock approvals only inside pytest temporary directories.

## Pilot and final evaluation

```powershell
# Optional exploratory calibration of first-run proposals; explicitly DRAFT_UNAPPROVED
python -m canadianness_eval.cli draft-pilot

# Pilot with a human-approved frozen version
python -m canadianness_eval.cli pilot

# Import and evaluate your independent dataset
python -m canadianness_eval.cli validate-dataset --input data/evaluation_cases.jsonl
python -m canadianness_eval.cli evaluate --input data/evaluation_cases.jsonl
```

`evaluate` and `pilot` reject execution without an intact frozen configuration. `draft-pilot` is an explicitly separate exploratory path; it never writes a frozen file and its outputs are marked unapproved. Its 21 small synthetic responses are examples, not the eventual 510-question research dataset. See [dataset format](docs/dataset_format.md) for independent reference evidence and pairing rules. Factual pilot references include official source URLs and retrieval provenance; hypothetical examples are labeled assumptions.

Scores are returned by native GEval normalization in [0,1]. Our adapter does not implement logprobs, so DeepEval uses its supported schema-based scoring fallback; there is no probability-weighted score claim. Missing applicability produces `score=null,status=not_applicable`. Missing required evidence or a failed judge call produces `score=null,status=failed`. Failures never count as zero.

Outputs include append-only JSONL, CSV, status counts, per-metric count/mean/standard deviation/median, and paired comparison CSV. Use variant names `base` and `fine_tuned` for paired summaries. Pairing holds question, evidence and applicability constant; missing variants are retained as unmatched. A question-paired bootstrap interval is reported only for at least ten valid pairs, with its limitations documented in [methodology](docs/research_methodology.md).

Successful evaluations resume only when dataset, frozen config, judge identity and package versions match the saved manifest. Failed attempts remain in JSONL; the latest attempt per question/variant/metric is used in resumed exports. To deliberately repeat judging, choose a new `--output` path; do not treat repeated scores as independent questions.

```powershell
python -m canadianness_eval.cli evaluate --input data/evaluation_cases.jsonl --frozen config/frozen/canadianness_geval_v2.yaml --output outputs/evaluations/repeat_02/results.jsonl
```

## Reproduce installation and verification

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Or reproduce all exact installed dependencies in a fresh environment:
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check src scripts tests
.\.venv\Scripts\ruff.exe format --check src scripts tests
.\.venv\Scripts\python.exe -m compileall -q src scripts tests
```

Mocked tests never call the gateway. Real smoke tests require explicit opt-in and a configured key:

```powershell
$env:RUN_LIVE_TESTS="1"
.\.venv\Scripts\python.exe -m pytest -q -m integration
Remove-Item Env:RUN_LIVE_TESTS
```

The implementation pins DeepEval 4.3.2. [Architecture](docs/architecture.md) records the inspected API and [official GEval documentation](https://deepeval.com/docs/metrics-llm-evals). Upgrade only after running the compatibility/evidence-inclusion tests. Run metadata records installed package versions. Credentials and result artifacts are excluded from Git by default; curate approved, authorized research artifacts deliberately.

401/403 errors stop authentication retries. Transient 429/5xx/network/timeout errors get at most three attempts with exponential delays. Requests are sequential. Structured support is tested against the actual gateway; an explicit schema/format rejection switches to prompted JSON with Pydantic validation. JSON/schema failures get bounded retries. Redirects are disabled to prevent forwarding credentials to another host. Remote error bodies are never printed.

## Final selected metrics and stronger calibration (2026-11-03)

The selected **42 final steps** are implemented from your authoritative `Canadianness_Final_GEVAL_Metrics.json`, with a byte-identical versioned copy at `config/final/2026-11-03-v1/metrics_final.json`. The supplied JSON/Excel and all earlier experiments are preserved. This path does **not** regenerate steps or freeze the proposed scientific standard. Earlier generation/review commands remain available for historical reproducibility; use these commands for the selected final proposals.

```powershell
.\.venv\Scripts\python.exe -m canadianness_eval.cli validate-metrics
.\.venv\Scripts\python.exe -m canadianness_eval.cli test-metrics
.\.venv\Scripts\python.exe -m canadianness_eval.cli calibrate

# Or choose a unique, memorable run ID
.\.venv\Scripts\python.exe -m canadianness_eval.cli calibrate --run-id my_final_v1_calibration --repeats 3

# Separate terminal: watch saved responses and scores
.\.venv\Scripts\python.exe -m canadianness_eval.cli watch
```

Only the existing `.env` key is needed. Calibration uses the same hosted GPT-OSS-120B gateway, without tested-model inference, training, or the complete benchmark. It retains exactly six steps per metric and supplies criteria/exclusions as judge interpretation, not additional generated steps.

The bundled suite has **51 cases** (21 original development examples plus 30 new controls), **47 eligible case–metric pairs**, and seven evidence-not-ready pairs. Three repeats produce **141 planned scores**, plus explicit null-score skipped/N/A records. Legacy assumption-only M3/M6 pilot cases are preserved but skipped for factual scoring. M1/M4 receive only question/response; verified reference answers and evidence for other metrics go only to the judge. A URL or unreviewed text alone does not establish readiness.

Each experiment gets a new directory under `outputs/calibration/`. The implementation run is `final_v1_calibration_20261103_01`. Each run includes:

- `manifest.json`: original JSON SHA-256, dataset hash/version, package versions, settings, applicability and run ID.
- `calibration_results.jsonl` and `records/`: every repeat/attempt, score, reason and status; reports use the latest attempt per repeat.
- `raw/`: separate original judge responses and request bodies, with no authorization headers.
- `calibration_summary.xlsx`: results, means/min/max/SD, matched controls, flags and cross-metric overlap.
- `human_calibration_review.xlsx`: blank reviewer fields, questions, anonymous response IDs, references/evidence, rubrics, judge scores/reasons and differences. Judge columns are hidden initially for independent review.
- `metric_calibration_report.md` and `analysis.json`: variability, exact diagnostic cases and pending human work.
- `prior_artifact_integrity.json`: verification that earlier generation, pilot, review and supplied source artifacts are unchanged.

Native DeepEval scores are retained as `deepeval_score` and `normalized_score`; they are **not divided twice**. Invalid scores fail rather than being clipped. `NOT_APPLICABLE`, `NOT_READY_FOR_FACTUAL_EVALUATION`, `FAILED`, and `SKIPPED_GATEWAY_UNAVAILABLE` are distinct null-score states excluded from score averages.

Resume only the same configuration/dataset/settings:

```powershell
.\.venv\Scripts\python.exe -m canadianness_eval.cli calibrate --run-id my_final_v1_calibration --resume
# Explicit bounded retry, retaining earlier failed attempts:
.\.venv\Scripts\python.exe -m canadianness_eval.cli calibrate --run-id my_final_v1_calibration --resume --retry-failures

# Analyze saved records into a fresh report directory; no inference:
.\.venv\Scripts\python.exe -m canadianness_eval.cli calibration-report --run-id final_v1_calibration_20261103_01
```

For independent human review, enter reviewer identity and normalized 0–1 score; duplicate an item row for another reviewer. Empty fields remain unreviewed. Reveal hidden judge columns after scoring. Actual human labels can then be analyzed:

```powershell
.\.venv\Scripts\python.exe -m canadianness_eval.cli compare-human --workbook outputs/calibration/final_v1_calibration_20261103_01/human_calibration_review.xlsx --output outputs/calibration/human_comparison_01 --tolerance 0.1
```

This reports per-metric/per-reviewer MAE, rank correlation where meaningful, tolerance agreement, large disagreements and disagreement among reviewers. No human labels are generated. Synthetic ranges are diagnostic hypotheses, not independent human scores. Gateway-default sampling does not establish determinism.

See [validation report](docs/metric_validation_report.md), [implementation notes](docs/implementation_notes.md) and [calibration provenance](data/calibration/README.md). Final team approval, verified real benchmark evidence and human calibration are required before freezing these selected metrics. The earlier `evaluate` command remains gated on its legacy frozen format; this addition does not silently approve the proposed JSON for production experiments.

The [observed findings report](docs/metric_calibration_report.md) records **141/141 successful main-run scores**, six further French-control scores, repeat variation up to 0.3, and specific M1/M4/M5/M6 concerns. The corrected numerical-tolerance analysis is in `outputs/calibration/final_v1_calibration_20261103_01/reports/analysis_v2/`; the initial reports and all inference results remain preserved. Human scores are still blank, and these results do not authorize freezing.

## Incoming 756-question benchmark and HPC exports

See [local preparation and verified judge connectivity](docs/local_preparation.md) for the offline import contract, workload planning, observed live smoke checks, and remaining production requirements. No full benchmark evaluation was run.


## First Llama HPC pilot (2026-11-06)

The [Llama pilot report](docs/llama_pilot_report.md) records validated 756-question input, the exact selected rubric checksum, 22 real provisional metric evaluations, request audits, checkpoint/resume verification, and the staged 1,814-task plan. The full run awaits user review and the existing production approval gate. Use `python -m canadianness_eval.hpc_workflow report` for network-free exports.

## Versioned evaluator clarification and blinded pilot revalidation

The [v2 revalidation report](docs/llama_evaluator_v2_revalidation.md) records the separately versioned generic interpretation guidance, unchanged rubric checksum, all 22 old/new score pairs, request-isolation and baseline-integrity checks, and the production hold decision. The single revalidation is complete; no full run or further automatic scoring cycle is authorized. New v2 configuration metadata intentionally prevents resuming a v1 run with changed instructions.

## Full-size provisional research experiment (separate execution permission)

At the user's explicit request, the [full-run readiness and permission guide](docs/llama_full_run_readiness.md) adds a separately authorized provisional research pathway using the existing v2 evaluator/checkpoint engine. It locks the exact dataset, rubric, template, software and task inventory. `python -m canadianness_eval.research_run run` requires an actual execution-only permission record and resumes missing/failed tasks. It does not replace or relax the scientific production-release frozen gate. No scientific/team approval or empirical calibration is inferred. The real run remains NOT STARTED until the pending request is explicitly authorized. `python -m canadianness_eval.research_run watch` monitors progress without contacting the judge.

## Completed authorized Llama experiment

Run `llama_full_20261106_v2` completed all 1,814 metric tasks successfully (756 primary, 1,058 secondary), with zero final failed/missing tasks. See [the full results report](docs/llama_full_run_results.md) and `outputs/evaluations/llama_full_20261106_v2/full_results.xlsx`. Results remain AI-provisional, pending calibration; the execution permission did not confer scientific or team approval. The original and v2 pilots and the pinned rubric/evaluator configuration were preserved.
