"""Rerun exactly the baseline pilot IDs; resume with no new audit events for completed IDs."""
# ruff: noqa: E402

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from canadianness_eval.settings import Settings
from canadianness_eval.verification.config import Config
from canadianness_eval.verification.db import Database, process_lock
from canadianness_eval.verification.export import export_package
from canadianness_eval.verification.local_io import load_inputs
from canadianness_eval.verification.models import digest, now
from canadianness_eval.verification.pipeline_v2 import PipelineV2
from canadianness_eval.verification.sources import SourceRetriever


def run(args):
    os.chdir(ROOT)
    with sqlite3.connect(f"file:{args.baseline.resolve().as_posix()}?mode=ro", uri=True) as old:
        baseline = {
            qid: json.loads(payload)
            for qid, payload in old.execute(
                "SELECT id,result FROM tasks WHERE state='researched' ORDER BY ordinal"
            )
        }
        events = dict(old.execute("SELECT task_id,id FROM events"))
    if len(baseline) != 10 or next(iter(baseline)) != "GC-ADD-0012":
        raise ValueError("Baseline must contain the exact ten-question pilot beginning GC-ADD-0012")
    questions, progress = load_inputs(args.benchmark, args.queue, original_evidence=args.benchmark)
    questions = [q for q in questions if q.question_id in baseline]
    if len(questions) != 10 or any(
        q.fingerprint != baseline[q.question_id]["input_fingerprint"] for q in questions
    ):
        raise ValueError("Original pilot input records changed or selected IDs are missing")
    instructions = args.instructions.read_text(encoding="utf-8-sig")
    settings = Settings.load()
    settings.require_key()
    config = Config(
        database=args.run_dir / "pilot.sqlite3",
        cache=args.run_dir / "source_cache",
        workers=4,
        source_timeout=12,
        attempts=2,
        extra_authority_hosts=["cmec.ca"],
        discovery_index=args.search_index,
    )
    with process_lock(config.database.with_suffix(".lock")):
        db = Database(config.database)
        db.bind(
            digest(
                {
                    "engine": "evidence-id-v3",
                    "inputs": progress["input_signature"],
                    "baseline_events": events,
                    "instructions": instructions,
                    "endpoint": settings.base,
                    "model": settings.model,
                    "search_index": args.search_index.read_text(encoding="utf-8"),
                }
            )
        )
        db.ingest(questions)
        if args.seed_db and not db.results():
            with sqlite3.connect(
                f"file:{args.seed_db.resolve().as_posix()}?mode=ro", uri=True
            ) as seed:
                with db.transaction() as c:
                    c.executemany(
                        "INSERT OR IGNORE INTO steps VALUES (?,?,?,?)",
                        seed.execute(
                            "SELECT task_id,name,signature,value FROM steps WHERE name='discovery_v2'"
                        ).fetchall(),
                    )
                    c.executemany(
                        "INSERT OR IGNORE INTO sources VALUES (?,?,?)",
                        seed.execute("SELECT cache_key,url,payload FROM sources").fetchall(),
                    )
        db.recover()
        retriever = SourceRetriever(db, config)
        pipeline = PipelineV2(db, config, settings, instructions, retriever, baseline_events=events)
        try:
            timing = pipeline.run(10, retry_failed=True)
            db.check_integrity()
            report = {
                "at": now(),
                "run": timing,
                "local": db.report(),
                "baseline_events": events,
                "question_ids": [q.question_id for q in questions],
                "search_mode": "recorded official web searches plus official page links; live API optional",
            }
            target = args.run_dir / "results"
            if target.exists():
                from canadianness_eval.verification.export import verify_package

                old_manifest = verify_package(target)
                if old_manifest["counts"]["proposed_updates"] != len(db.results()):
                    target = args.run_dir / ("results-" + now().replace(":", "").replace("+", ""))
            report["package"] = str(target)
            export_package(db, target, [args.benchmark, args.queue, args.instructions])
            if timing["attempted"]:
                with (args.run_dir / "runs.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps(report) + "\n")
            report_name = "run_report.json" if timing["attempted"] else "resume_report.json"
            (args.run_dir / report_name).write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))
            return 1 if timing["failed"] else 0
        finally:
            pipeline.close()
            retriever.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("outputs/verification/real-pilot-20261103/pilot-recovered.sqlite3"),
    )
    parser.add_argument(
        "--run-dir", type=Path, default=Path("outputs/verification/pilot-final-20261104")
    )
    parser.add_argument(
        "--search-index",
        type=Path,
        default=Path("outputs/verification/pilot-v2-20261103/discovery_index.json"),
    )
    parser.add_argument("--benchmark", type=Path, default=Path("docs/history/setup/project_instructions.txt"))
    parser.add_argument("--queue", type=Path, default=Path("docs/history/setup/README.txt"))
    parser.add_argument("--seed-db", type=Path)
    parser.add_argument(
        "--instructions", type=Path, default=Path("data/verification/project_instructions.txt")
    )
    raise SystemExit(run(parser.parse_args()))
