# Repository organization

The repository has four human-facing experiment folders under `results/`, with direct links to canonical datasets, full results and reasoning. `data/benchmarks/core_756/` supplies an answer-free question/reference view and its derivation. Folder READMEs separate code, configuration, source inputs, prepared inputs and final outputs.

## Why some historical paths remain

Existing experiment manifests hash input files, evaluator code and pilot artifacts. Existing source also names specific root files. Moving those or silently rewriting manifests would break integrity checks and erase the connection to the actual authorized experiment. They therefore remain at their recorded paths; the new indexes provide navigation without duplicating large results.

The root JSON/Excel final metric artifacts, cleaned source, mixed-temperature workbook and supplied two-metric Markdown can therefore be compatibility inputs, not accidental clutter. The cleanup manifest lists the exact protected root files.

## Cleanup boundaries

Housekeeping removes disposable caches, generated diagnostics outside protected contracts, an oversized redundant archive/staging tables, and only those worker-shard JSON files whose bytes match canonical `records/` or `raw/` files. Original supplied answers, final scores/reasoning, original canonical checkpoint attempts, authoritative rubrics, code, tests, permissions and manifest-bound pilot/calibration evidence remain.

Unreferenced root setup notes/drafts are moved into labelled history folders; duplicate root datasets are deleted only after matching an existing retained copy byte for byte. No benchmark answer, rubric band or scoring instruction is edited. The local `.env` and `.venv` are retained for the current desktop but must not be distributed or committed.

`cleanup_plan.json` documents the proposed operations. `cleanup_applied.json` records applied operations and any filesystem failures. `protected_files_sha256.json` lists checksums used to prove preserved input/code/pilot integrity. Removal failures are explicitly recorded rather than silently treated as success.

The organization does not change experimental authorization or claim human/team calibration. All operations are local; no judge requests or new evaluations are launched.

## Completed verification (2026-11-10)

- 134 offline tests passed; one live integration test was deselected.
- All 17,301 protected artifact hashes are unchanged.
- All 88 checked navigation links resolve.
- All 20,862 final judgments remain across four experiments and twelve completed model runs.
- Seven root-level notes/examples/drafts were relocated. Disposable working artifacts and 12,711 byte-identical shard records were removed, with no cleanup failures.
- The oversized 716 MB archive and redundant staging tables were removed; the 92.9 MB three-condition reporting archive remains as a historical snapshot. The fourth experiment's canonical exports remain separately linked from its experiment page.

See `verification_summary.json`, `layout_verification.json` and `cleanup_applied.json` for the machine-readable checks. Test temporary directories created during verification were removed after the tests finished.
