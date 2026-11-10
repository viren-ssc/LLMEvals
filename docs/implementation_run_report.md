# Implementation run report — 2026-11-03

Live verification used the supplied HTTPS gateway and the `.env` key without displaying credentials. Discovery selected **gpt-oss-120b** unambiguously. Both plain Winnipeg and structured JSON smoke checks passed; the gateway accepted `response_format=json_schema`, and returned output passed local Pydantic validation. This establishes successful use, not a claim that the server enforces every arbitrary schema.

**28 of 28 independent GEval-template generation sets succeeded**, four for each metric. There were no failed generation sets. They produced **177 candidate steps**. Original prompts, response payloads, timestamps, latency, attempt counts, model ID, versions and settings are retained under `outputs/generations/`. The master workbook is `review/Canadian_Ness_GEVAL_Review.xlsx`, with original candidate text and separate manual decision cells. The initial generated workbook was archived before adding richer rubric examples and provenance to the unreviewed workbook.

**21 of 21 exploratory draft pilot calls succeeded.** These use first-run proposals and unapproved draft rubrics, and their records are marked `DRAFT_UNAPPROVED`. They are synthetic illustrative answers, not measured outputs from a real base/fine-tuned comparison.

| Metric | Weak | Intended moderate | Strong |
|---|---:|---:|---:|
| M1 | 0.0 | 0.3 | 0.8 |
| M2 | 0.0 | 0.1 | 1.0 |
| M3 | 0.1 | 0.3 | 1.0 |
| M4 | 0.0 | 0.3 | 1.0 |
| M5 | 0.1 | 0.2 | 1.0 |
| M6 | 0.0 | 0.1 | 1.0 |
| M7 | 0.0 | 0.5 | 1.0 |

All seven met the programmed direction check: strong > weak and weak <= intended moderate <= strong. Several intended moderate examples scored poorly; labels are author intentions, not ground truth, and this deserves human examination rather than changing or concealing observed results. Strong M1 received 0.8, showing that even obvious examples require review. Explanations and original completions are saved under `outputs/pilot/draft/`; see `pilot_report.json`, `results.jsonl` and `results.csv`.

The local watcher was implemented and exercised with `watch --once`. It displays responses as complete requests finish; token streaming is not implemented. The final evaluator was checked to reject execution before any API calls when no approved frozen config exists. Mocked tests exercise installed GEval scoring and prove explicitly approved context/expected-answer content reaches the judge prompt.

Human review, actual frozen experiment definitions, the independent approximately 510-question dataset, independent human labels, repeated-judge reliability, controlled length/presentation tests and broader bilingual validity remain future research work. No actual frozen configuration was created. No production base/fine-tuned comparison has been run.

Final verification: **35 mocked/offline tests passed**, with the opt-in live test skipped in that run; **one separately opted-in live integration test passed**. Ruff lint, formatting and Python compile checks passed. The artifact audit confirms every original generated step appears unchanged in the workbook, with no credential value found in source/research artifacts.

Windows sandbox restrictions initially blocked pip/pytest temporary directories and remote requests. Dependency installation, mocked tests and the authorized live gateway runs succeeded with normal host access. TLS verification remained enabled throughout. Reproduce checks using the commands in README.
