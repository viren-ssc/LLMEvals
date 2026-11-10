# Local Canadian benchmark verification

This application researches **reference answers**, separately from the existing G-Eval model-response scorer. It reads local files, uses the configured IceLab OpenAI-compatible endpoint, retrieves actual public primary sources, checkpoints in SQLite, and exports proposed changes. It contains no Google authentication or synchronization code. Original inputs are opened for reading only.

## Run the first batch

From the repository root in PowerShell, install the optional retrieval dependencies if needed:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[verification]"
```

The existing `.env` settings `LLM_KEY`, `LLM_BASE`, `LLM_MODEL`, and `LLM_TIMEOUT_SECONDS` are used. Keep the key in `.env`; environment variables override the file. Model discovery requires the configured model to be accessible and automatically selects GPT-OSS-120B only when it is unambiguous. There is no fallback to a different provider. TLS verification stays enabled.

Supply your local benchmark, exact existing queue, and project instructions. A single workbook can contain both Questions and Cycle 100 Queue. With the filenames below, first validate without networking or database changes:

```powershell
.\.venv\Scripts\python.exe -m canadianness_eval.verification.cli run `
  --benchmark data/input/benchmark.xlsx `
  --queue data/input/benchmark.xlsx `
  --instructions data/verification/project_instructions.txt `
  --limit 10 --dry-run
```

The dry run reports selected/completed/pending counts and the first ten IDs. It must show GC-ADD-0012 first for the original pilot. Then run:

```powershell
.\.venv\Scripts\python.exe -m canadianness_eval.verification.cli run `
  --benchmark data/input/benchmark.xlsx `
  --queue data/input/benchmark.xlsx `
  --instructions data/verification/project_instructions.txt `
  --limit 10 --start-id GC-ADD-0012 --workers 4 `
  --output outputs/verification/pilot-01
```

After installation, `canadian-verify` is an equivalent shorter command. The bundled project-instructions text was read from the connected project on 2026-11-03; replace it with your authoritative local version when needed. The connector snapshot beside it is a prior read-only capture, not an automatic pipeline input or proof of local research. The new CLI never uses a Drive connection.

The application does not generate new questions or resequence the queue. `--start-id` is a check on the next pending ID, not a request to skip earlier entries. The default `--limit 10` is a maximum number of pending questions attempted. The original queue has 100 selected, six saved, and 94 pending; requesting 100 will process at most the 94 remaining.

## Local input formats

Excel `.xlsx` and UTF-8 `.jsonl` are accepted. Each JSONL line must be one object. Unknown original columns are preserved in SQLite and never overwritten. Use Excel's actual cell values; formula columns must have saved calculated values if used as required inputs.

| Content | Default worksheet | JSONL columns | Existing Excel header aliases |
| --- | --- | --- | --- |
| Benchmark | Questions | question_id, question, reference_answer, metric, source_urls | Question ID, Question, Original proposed answer, Original metric, Original source URL(s) |
| Queue | Cycle 100 Queue | question_id, status | Question ID, Cycle status |
| Earlier verified claims (optional) | Verified claims | question_id, claim_id, plus original fields | question_id, claim_id |
| Original evidence (optional) | Original evidence | question_id, plus original fields | Question ID, plus original fields |

`source_urls` may be a JSON list or a string of URLs. Preserve historical excerpts in the benchmark's original columns or supply `--original-evidence path.xlsx`. Earlier claim decisions can be supplied with `--evidence path.xlsx`; neither original excerpts nor earlier verdicts are treated as newly verified sources. Actual WARC files are supported with repeated `--warc path.warc.gz` arguments. Complete archive containers and extracted response bytes remain in the cache, with captured dates recorded separately from retrieval dates.

Use `--question-sheet`, `--queue-sheet`, `--original-evidence-sheet`, and `--evidence-sheet` to specify other worksheet names. Separate benchmark and queue files can mix Excel and JSONL.

Minimal benchmark JSONL:

```json
{"question_id":"YOUR-EXISTING-ID","question":"Original question","reference_answer":"Original answer","metric":"M2","source_urls":["https://www.canada.ca/your-source"]}
```

Minimal queue JSONL:

```json
{"question_id":"YOUR-EXISTING-ID","status":"Pending"}
```

These are format illustrations, not benchmark questions. No replacement dataset is created.

Exactly 100 queue IDs are expected by default. For an intentionally different local queue use `--expected-queue N`; `0` disables only the size check. Duplicate/missing IDs, unknown queue statuses, orphan evidence, invalid metric codes, and missing reference answers cause import failure. Saved statuses `Research saved`, `Follow-up saved`, `Completed`, and `Done` are skipped; only `Pending` is scheduled.

## Resume and inspect

The default database is `outputs/verification/pipeline.sqlite3`. Use `--db path.sqlite3` **before** the subcommand to isolate a different run. `VERIFY_DB`, `VERIFY_CACHE`, `VERIFY_WORKERS`, `VERIFY_USER_AGENT`, and `VERIFY_AUTHORITY_HOSTS` are optional environment settings.

Repeat the same `run` command to resume. Successfully researched questions are skipped. If an export already exists and more work will be done, choose a new `--output` path or omit that option and export afterwards. On a resumed pilot, omit `--start-id GC-ADD-0012` once that question is completed; it would correctly fail because the next ID has changed.

Ctrl+C stops new scheduling and waits for current API requests to return before workers exit. Completed steps remain committed; interrupted tasks resume from those steps. A forced process termination also leaves committed checkpoints intact. There can be a repeated remote request if the process died after the server returned but before its checkpoint was committed; no local system can guarantee exactly-once external requests across that boundary. Completed questions do not run again.

```powershell
.\.venv\Scripts\python.exe -m canadianness_eval.verification.cli status
.\.venv\Scripts\python.exe -m canadianness_eval.verification.cli failures
```

Failed questions are retained separately from researched questions whose evidence is unresolved. Repeat `run` with `--retry-failed` to retry execution failures as well as pending questions. Successfully researched but unresolved verdicts are final for that run; use a new database for a deliberate investigation with changed sources or inputs.

Requests use bounded retries with exponential backoff. Source HTTP 429 honours numeric Retry-After up to 60 seconds. A SQLite/kernel lock prevents concurrent CLI writers to the same database, while configured workers process different questions concurrently. Concurrent runs with different databases should use different cache directories.

Resume rejects changed input records, queue order/statuses, instructions, endpoint/model configuration, source overrides, and imported WARC files. Resolved model identity is also checked. This protects existing decisions from silent replacement. Keep the original input exports unchanged for the duration of a run; use a new database when intentionally changing them.

After reviewing the pilot package, run the remaining queue unattended:

```powershell
.\.venv\Scripts\python.exe -m canadianness_eval.verification.cli run `
  --benchmark data/input/benchmark.xlsx `
  --queue data/input/benchmark.xlsx `
  --instructions data/verification/project_instructions.txt `
  --limit 100 --workers 4 --output outputs/verification/cycle-results
```

The runner supports larger local queues with `--expected-queue N --limit N`. It reports actual attempted/researched/failed counts, elapsed seconds, and researched questions per minute. This is throughput of research completion, including unresolved findings, rather than an assumed count of supported answers.

## Evidence and acceptance

1. Extract atomic factual claims as exact spans of the original reference answer, including incidental dates, quantities, conditions, and qualifications.
2. Check deterministic span coverage and have a separate LLM pass review omitted or wrongly nonfactual assertions.
3. Retrieve supplied source URLs and bounded candidate primary-source URLs suggested by the LLM. Candidate URLs are never evidence until retrieved. Retrieved documents are untrusted data in the judge prompt.
4. Judge each claim against inspected source text. Every factual supported/contradicted verdict requires an exact excerpt, content hash, URL, precise text-line or PDF-page locator, and temporal/jurisdiction match. Deterministic checks reject fabricated excerpts, uninspected URLs, incorrect hashes/locators, and archives used for current facts.
5. Assess the primary metric separately using project instructions. Propose corrections and missing information separately from original-answer truth.

All extracted claims must be supported for `original_answer_fully_supported=true`; incompleteness, invalid citations, or any insufficient, contradictory, or failed-retrieval claim blocks it. A broken URL never becomes evidence that its claim is false. Acceptance also requires metric suitability, the same primary metric, and no identified missing information. Corrected answers are **unverified drafts** even when their source original answer is fully supported. Human approval and independent AI audit fields remain empty.

HTML, readable PDF (up to 300 pages), plain text, and local WARC responses are supported. Official federal/provincial/territorial domains and selected public institutions are allowed. Add other reviewed institution domains with `VERIFY_AUTHORITY_HOSTS=cmec.ca,...`. This allowlist is an access/provenance constraint, not a guarantee that every page substantively supports its claims.

Robots restrictions are honoured, requests are spaced per host, cross-host redirects are checked, and nonpublic destinations/HTTPS downgrades are refused. There is no access-control bypass. Blocked pages, JavaScript-only content, scans without OCR, unsupported formats, and oversized documents remain retrieval limitations. Additional browser, OCR, archive retrieval, or official-search services can be added through the source module; none are silently substituted. Candidate URL discovery is not comprehensive web search.

Raw responses are content-hashed and cached. Successful live snapshots have a 24-hour cache lifetime; failed retrievals a one-minute lifetime. Committed per-question retrieval checkpoints pin the actually inspected snapshots during resume. Archive evidence remains explicitly historical. Source context is bounded to eight sources and 80,000 total characters per claim; evidence outside the inspected portion cannot be cited. This can produce conservative unresolved results for long documents.

These checks establish traceable provenance. Claim decomposition, semantic support, temporal suitability and proposed corrections still depend on the research model; they are not an independent AI audit or human approval.

## Export and manual import

```powershell
.\.venv\Scripts\python.exe -m canadianness_eval.verification.cli export --output outputs/verification/results-01
.\.venv\Scripts\python.exe -m canadianness_eval.verification.cli check-package outputs/verification/results-01
```

Each immutable directory contains:

- `results.xlsx`: proposed_updates, claims, sources, audit, and failures worksheets.
- Matching JSONL files containing full records, including long values that Excel cannot display completely.
- `source_bytes/`: actual retrieved response bytes and used WARC containers for evidence replay, named by SHA-256.
- `manifest.json`: counts, progress, package file hashes and a deterministic content signature.

The package is written in a staging directory and read back before publication. Re-exporting identical content to the same path validates and reuses the package; a different result requires a new path. Excel strings are written as literal text to prevent formulas in scraped/LLM content from executing. No original workbook is rewritten, and no original full benchmark is included in the package.

Import only proposed fields into Drive, matching `question_id`, deterministic `claim_id`, and `event_id`. Compare `input_fingerprint` with the original local record before applying changes; review concurrent human edits separately. The audit provides original/proposed answer and metric values and source references. Do not replace original material, prior research, independent audit decisions or human approvals. A local export is not proof that any Google Sheet was updated.

SQLite retains original input rows, step checkpoints, source snapshots, claim results, unverified corrected answers, research events, attempt outcomes and audit history. `status` counts locally imported pending tasks, while the run report additionally includes the original queue's skipped-completed counts.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_verification_pipeline.py -q
.\.venv\Scripts\python.exe -m ruff check src/canadianness_eval/verification tests/test_verification_pipeline.py
```

Tests use mocked HTTP responses and structured research judgments. They exercise the full local flow and package readback, resume after interruption, duplicate prevention, changed-input conflicts, partial failures, invalid citations, historical provenance, access restrictions, source caching, and literal Excel text. They do not constitute the real ten-question pilot. Run that pilot only with your supplied benchmark and queue files; inspect its evidence and proposals before accepting results.
