# Evidence-ID verification and the repeated pilot

The default local verifier now uses generated evidence passages. The original engine is retained behind `--engine legacy` so historical decisions remain readable. Original records and first-pilot packages are not rewritten.

```powershell
.\.venv\Scripts\python.exe -m canadianness_eval.verification.cli run `
  --benchmark project_instructions.txt --queue README.txt `
  --original-evidence project_instructions.txt `
  --instructions data/verification/project_instructions.txt `
  --search-index outputs/verification/pilot-v2-20261103/discovery_index.json `
  --workers 4 --limit 10 --output outputs/verification/new-run
```

Use a new `--db` path before `run` for a deliberately different research version. Resume an existing version with exactly its original configuration. To rerun or resume **only the same ten pilot IDs**, including links to their original audit events, use:

```powershell
.\.venv\Scripts\python.exe scripts/rerun_verification_pilot.py `
  --seed-db outputs/verification/pilot-v2-20261103/pilot.sqlite3
```

The repeated-pilot runner defaults to `outputs/verification/pilot-final-20261104`. It validates that the source records match the original ten fingerprints, selects exactly those ten IDs, skips completed work, and checks audit uniqueness. The optional seed database transfers only discovery checkpoints/source snapshots; extraction and factual decisions are recomputed. Completed reruns schedule zero new questions and create zero new audit records.

Generate the comparison separately:

```powershell
.\.venv\Scripts\python.exe scripts/compare_verification_pilots.py
```

## Retrieval

Original URLs are still attempted. When they fail or yield HTTP 200 migration/missing-page notices, discovery consults recorded official-search results and observed hyperlinks/meta-refresh targets from official documents. Robots redirects are followed conservatively, HTTPS downgrades remain refused, and substantive content is distinguished from successful HTTP transport. Search results and migration notices never become evidence merely because they were retrieved.

The local search-index format is a JSON array:

```json
[{"question_id":"EXISTING-ID","url":"https://www.canada.ca/current-page","query":"actual search query","provider":"recorded official-domain search","searched_at":"2026-11-04","evidence":false}]
```

This pilot's index contains actual recorded official-domain web-search results, including the earlier primary-source lookups and newly located documents. Each URL must still pass the Python retriever and evidence gates. Results are logged with their discovery method, query/provider and retrieval outcome.

For unattended live discovery on topics absent from the recorded index, `BRAVE_SEARCH_API_KEY` enables the optional [Brave Web Search API](https://api-dashboard.search.brave.com/app/documentation/web-search/get-started) adapter. Put credentials only in `.env` or the environment. Without it, logs explicitly report that general live search is not configured. Official hyperlinks can still be followed and the saved index still works. The public Canada.ca search page is not scraped because its robots policy disallows that path. No authentication or access-control bypass is used.

## Claim alignment and citations

Claims have a complete contextual `assertion` and an exact original-answer span. Shared sentence anchors are permitted when several atomic assertions share a subject. A coverage pass looks for missing factual relations, invented assertions and unsupported nonfactual exclusions; a bounded repair pass addresses defects. Unique case/typography-normalized matches map back to exact original offsets. This never removes changed words, negation or quantities to manufacture a match. Remaining alignment problems are recorded separately as `extraction_error`.

Source text is divided into deterministic passages with actual source URL, body hash, line/page locator, exact excerpt and evidence ID. Ranking considers the full retrieved document, avoiding the first pilot's fixed-prefix exclusion of later evidence. The judge chooses IDs from supplied passages; the application copies the quote/location from those records and validates them against the source. The model cannot supply arbitrary quote or locator strings. Semantic entailment is checked separately, including temporal scope, jurisdiction, qualifiers and explicitly incompatible evidence for contradiction findings.

This prevents fabricated locations by construction. It does not guarantee that the model correctly understands every passage or qualification. Internal entailment checks remain research, not an independent AI audit. Model disagreement or excessive literalism must remain visible in the comparison rather than being changed merely to increase acceptance.

## Statuses and comparisons

`reference_status` distinguishes `fully_supported`, `needs_more_evidence`, `contradicted`, and `extraction_error`. Missing evidence and failed retrieval are never automatically false claims. Proposed corrections remain unverified and use `needs_more_evidence`; metric-only revisions can be proposed for a factually supported original answer without rewriting it. Human approval and independent audit fields remain empty.

Metric recommendations are made without the original label to reduce anchoring. Naming a program, listing facts/services, or recalling a date generally fits M7. M2 requires institutional roles or allocation of responsibilities; an institution name alone is insufficient. Mentioning First Nations alone does not establish M5. Boundary cases retain advisory review flags.

The comparison checks all protected file hashes and both audit ledgers, reads back packages, and produces Markdown, JSON, JSONL and Excel outputs. It distinguishes native claim counts from conservative mappings of the original claim IDs because repaired atomization changes the denominator. It also distinguishes source candidates, deduplicated source snapshots, citation-selection errors and semantic evidence limitations. Cached final verification is not reported as a new set of website requests.
