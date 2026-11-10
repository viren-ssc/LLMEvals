"""Isolated replay benchmark; never writes to evaluation runs or changes scoring code."""

import json
import random
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from canadianness_eval.api_client import Gateway
from canadianness_eval.final_metrics import file_hash
from canadianness_eval.hpc_ingestion import read_records
from canadianness_eval.settings import ROOT, Settings


def main():
    source = ROOT / "outputs/evaluations/gc_llm_full_as_generated_20261106_v2"
    run = "judge_concurrency_" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    dest = ROOT / "outputs/diagnostics" / run
    dest.mkdir(parents=True, exist_ok=False)
    rows = read_records(source / "all_results.jsonl")
    selected = []
    used = set()
    for index, metric in enumerate(["M1", "M2", "M3", "M4", "M5", "M6", "M7"]):
        for language in ["en", "fr"]:
            candidates = sorted(
                [
                    r
                    for r in rows
                    if r["evaluation_metric"] == metric
                    and r["language"] == language
                    and r["question_id"] not in used
                ],
                key=lambda r: len(r["model_answer"]),
            )
            row = candidates[
                int((len(candidates) - 1) * (0.85 if (index + (language == "fr")) % 2 else 0.15))
            ]
            raw = json.loads((source / row["raw_output_file"]).read_text(encoding="utf8"))
            event = next(e for e in reversed(raw["responses"]) if e.get("status") == 200)
            selected.append(
                {
                    "question_id": row["question_id"],
                    "metric": metric,
                    "language": language,
                    "answer_characters": len(row["model_answer"]),
                    "body": event["request_body"],
                }
            )
            used.add(row["question_id"])
    manifest = {
        "run_id": run,
        "purpose": "Concurrency diagnostic only; not new benchmark scores",
        "script_sha256": file_hash(Path(__file__)),
        "source_results_sha256": file_hash(source / "all_results.jsonl"),
        "levels": [1, 2, 4, 8, 16],
        "rounds": 2,
        "requests_per_block": 14,
        "retry_policy": "Unchanged Gateway bounded retries and Retry-After handling",
        "limitations": [
            "Shared server load is uncontrolled",
            "Repeated prompts may benefit from provider caching",
            "Two rounds and fourteen prompts per level are exploratory, not a load-test SLA",
            "Server-default temperature unchanged; prior scores/reasons not sent",
        ],
        "requests": selected,
    }
    (dest / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf8"
    )
    settings = Settings.load()
    settings.require_key()
    all_rows = []
    blocks = []
    stopped_levels = set()

    def request(item, round_id, concurrency):
        gateway = Gateway(settings)
        started = time.perf_counter()
        result = {
            "question_id": item["question_id"],
            "metric": item["metric"],
            "language": item["language"],
            "concurrency": concurrency,
            "round": round_id,
            "started_at": datetime.now(UTC).isoformat(),
            "success": False,
        }
        try:
            response = gateway.request("POST", "chat/completions", json=item["body"])
            if response.status_code != 200:
                raise ValueError("HTTP " + str(response.status_code))
            payload = response.json()
            gateway.history[-1]["raw_response"] = payload
            content = payload["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            value = json.loads(content)
            if not (
                isinstance(value.get("reason"), str)
                and value["reason"].strip()
                and type(value.get("score")) in (int, float)
                and 0 <= value["score"] <= 10
            ):
                raise ValueError("Invalid ReasonScore response")
            result.update(success=True, usage=payload.get("usage", {}))
        except Exception as exc:
            result["error"] = gateway.safe_error(exc)
        finally:
            result.update(
                latency_seconds=time.perf_counter() - started,
                http_attempts=gateway.attempts,
                statuses=[e.get("status") for e in gateway.history],
                cached_prompt_tokens=sum(
                    e.get("raw_response", {})
                    .get("usage", {})
                    .get("prompt_tokens_details", {})
                    .get("cached_tokens", 0)
                    for e in gateway.history
                ),
            )
            raw_path = (
                dest / f"round_{round_id}_c{concurrency}_{item['metric']}_{item['language']}.json"
            )
            raw_path.write_text(
                json.dumps(
                    {"result": result, "events": gateway.history}, ensure_ascii=False, indent=2
                ),
                encoding="utf8",
            )
            gateway.close()
        return result

    def publish():
        (dest / "request_results.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in all_rows), encoding="utf8"
        )
        (dest / "block_results.json").write_text(json.dumps(blocks, indent=2), encoding="utf8")

    for round_id, levels in [(1, [1, 2, 4, 8, 16]), (2, [16, 8, 4, 2, 1])]:
        for concurrency in levels:
            if concurrency in stopped_levels:
                continue
            batch = list(selected)
            random.Random(731 + round_id).shuffle(batch)
            started = time.perf_counter()
            results = []
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = [executor.submit(request, item, round_id, concurrency) for item in batch]
                for future in as_completed(futures):
                    result = future.result()
                    results.append(result)
                    all_rows.append(result)
                    publish()
            elapsed = time.perf_counter() - started
            good = sum(r["success"] for r in results)
            latencies = sorted(r["latency_seconds"] for r in results)
            block = {
                "round": round_id,
                "concurrency": concurrency,
                "requests": len(results),
                "successful": good,
                "elapsed_seconds": elapsed,
                "successful_per_minute": good / elapsed * 60,
                "mean_latency_seconds": statistics.mean(latencies),
                "p95_latency_seconds": latencies[
                    min(len(latencies) - 1, int(0.95 * len(latencies)))
                ],
                "http_attempts": sum(r["http_attempts"] for r in results),
                "error_rate": 1 - good / len(results),
                "status_counts": {
                    str(s): sum(r["statuses"].count(s) for r in results)
                    for s in set(s for r in results for s in r["statuses"])
                },
            }
            blocks.append(block)
            publish()
            print(json.dumps(block), flush=True)
            if any(s in [401, 403] for r in results for s in r["statuses"]):
                print("STOP: authentication/access failure; no further test requests.", flush=True)
                return
            if good < len(results) * 0.9 or any(429 in r["statuses"] for r in results):
                stopped_levels.update(c for c in [1, 2, 4, 8, 16] if c >= concurrency)
            time.sleep(3)
    print("Diagnostic results:", dest, flush=True)


if __name__ == "__main__":
    main()
