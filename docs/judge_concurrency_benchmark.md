# Judge concurrency benchmark

Recommendation: **4 concurrent requests** for a separately versioned future run configuration. It was fastest in both passes. Existing benchmark results and the production runner remain unchanged.

| Workers | Effective max | Successful/min | Speedup | Mean latency (s) | p95 (s) | Errors |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 15.22 | 1.00x | 3.51 | 5.39 | 0 |
| 2 | 2 | 22.90 | 1.50x | 4.61 | 6.79 | 0 |
| 4 | 4 | 36.82 | 2.42x | 5.41 | 8.65 | 0 |
| 8 | 8 | 33.45 | 2.20x | 9.46 | 13.84 | 0 |
| 16 | 14 | 30.83 | 2.02x | 13.41 | 22.70 | 0 |

## Method

140 live diagnostic judgments; fourteen exact saved GC evaluation request bodies with EN/FR examples across M1-M7 and different answer lengths. Two passes in opposite orders: 1,2,4,8,16 then 16,8,4,2,1. Same fixed prompts/rubric/schema, gpt-oss-120b judge and omitted-temperature behavior as the completed runs. No previous scores or explanations were sent. No answer generation or new evaluation steps. All returned explanations were nonempty and raw scores within the original 0-10 response span. These judgments are diagnostics, not added benchmark scores.

All 140 requests returned HTTP 200 on their first attempt: zero retries, rate-limit responses or other errors. The unchanged Gateway supplied timeouts and bounded retries, with isolated clients per task. Wall throughput includes client setup and diagnostic persistence. Reported task latency excludes some setup/persistence overhead.

## Limits

This is the best tested setting, not a proven global optimum or gateway hard limit. Intermediate values such as 3,5,6 were not tested. Blocks contain fourteen tasks, so configured concurrency 16 exercises at most fourteen in flight; it is not a sixteen-request saturation test. Higher parallelism increased latency and reduced throughput, consistent with contention/queueing, without establishing the underlying bottleneck. No rate-limit ceiling was encountered.

Provider load and caching are uncontrolled. Counterbalanced ordering reduces but cannot eliminate timing/cache bias; cached-token counts are saved by level in summary.json. Replaying prompts may differ from cold full-run performance. The sample is small and cannot establish long-run reliability; prior full runs experienced intermittent 403/500 failures. This diagnostic does not establish score consistency, scientific calibration or deterministic sampling.

Reported token consumption: {'prompt_tokens': 252900, 'completion_tokens': 74249, 'total_tokens': 327149}.

Sample-based projections for 1,814 tasks: 49.3 minutes at four workers versus 119.2 sequential. These are projections, not measured full-run durations or guarantees.

## Future integration

Use bounded four-worker execution with isolated judge/metric state, serialized immediate checkpoint commits, task idempotency and shared cooldown/authentication-stop handling. Preserve existing retry/timeouts and record concurrency=4 in a new immutable execution manifest. No existing runner or authoritative scoring configuration was changed by this benchmark.

Diagnostic directory: `outputs\diagnostics\judge_concurrency_20261107T013815Z`. Artifacts include manifest.json, request_results.jsonl, block_results.json, summary.json and all raw requests/responses.
