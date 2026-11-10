import argparse
import json
import sys
from pathlib import Path

from ..settings import Settings
from .config import Config
from .db import Conflict, Database, process_lock
from .export import export_package, verify_package
from .local_io import load_inputs
from .models import digest
from .pipeline import Pipeline
from .sources import SourceRetriever


def parser():
    p = argparse.ArgumentParser(
        description="Local Canadian reference-answer verification; no Google API"
    )
    p.add_argument("--db", type=Path, default=None)
    sub = p.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Import the existing queue and resume pending research")
    run.add_argument("--benchmark", type=Path, required=True)
    run.add_argument("--queue", type=Path, required=True)
    run.add_argument("--evidence", type=Path)
    run.add_argument("--original-evidence", type=Path)
    run.add_argument("--original-evidence-sheet", default="Original evidence")
    run.add_argument("--instructions", type=Path, required=True)
    run.add_argument("--question-sheet", default="Questions")
    run.add_argument("--queue-sheet", default="Cycle 100 Queue")
    run.add_argument("--evidence-sheet", default="Verified claims")
    run.add_argument("--expected-queue", type=int, default=100)
    run.add_argument("--limit", type=int, default=10)
    run.add_argument(
        "--start-id", help="Require this to be the next pending ID; never reorder the queue"
    )
    run.add_argument("--workers", type=int)
    run.add_argument("--retry-failed", action="store_true")
    run.add_argument(
        "--dry-run", action="store_true", help="Validate inputs only; no network or DB writes"
    )
    run.add_argument(
        "--source-overrides",
        type=Path,
        help="JSON object: question ID to extra primary-source URLs",
    )
    run.add_argument("--warc", type=Path, action="append", default=[])
    run.add_argument(
        "--engine",
        choices=["v2", "legacy"],
        default="v2",
        help="Use evidence-ID verification (default) or reproduce the legacy engine",
    )
    run.add_argument(
        "--search-index",
        type=Path,
        help="JSON array of recorded official-search results with question_id, url and provenance",
    )
    run.add_argument(
        "--output", type=Path, help="Write immutable Excel + JSONL delta package after processing"
    )
    sub.add_parser("status")
    sub.add_parser("failures")
    export = sub.add_parser("export")
    export.add_argument("--output", type=Path, required=True)
    check = sub.add_parser("check-package")
    check.add_argument("path", type=Path)
    return p


def execute(args):
    if args.command == "check-package":
        return verify_package(args.path)
    config = Config.load()
    if args.db:
        config.database = args.db
    if args.command == "run":
        if args.search_index:
            config.discovery_index = args.search_index
        if args.limit < 1 or args.expected_queue < 0:
            raise ValueError("limit must be positive; expected-queue must be nonnegative")
        if args.workers is not None:
            config = Config.model_validate({**config.model_dump(), "workers": args.workers})
        instructions = args.instructions.read_text(encoding="utf-8-sig")
        if not instructions.strip():
            raise ValueError("Project instructions must not be empty")
        questions, progress = load_inputs(
            args.benchmark,
            args.queue,
            args.evidence,
            args.question_sheet,
            args.queue_sheet,
            args.evidence_sheet,
            args.expected_queue,
            args.original_evidence,
            args.original_evidence_sheet,
        )
        overrides = (
            json.loads(args.source_overrides.read_text(encoding="utf-8"))
            if args.source_overrides
            else {}
        )
        if not isinstance(overrides, dict) or any(
            not isinstance(v, list) or any(not isinstance(u, str) for u in v)
            for v in overrides.values()
        ):
            raise ValueError("Source overrides must map question IDs to URL lists")
        if args.dry_run:
            return {
                "dry_run": True,
                **progress,
                "first_batch_ids": [q.question_id for q in questions[: args.limit]],
                "note": "No network requests, research judgments, database changes or exports performed",
            }
        settings = Settings.load()
        settings.require_key()
        with process_lock(config.database.with_suffix(".lock")):
            db = Database(config.database)
            # Input binding catches removed/reordered queue records too, not just changed tasks.
            signature = {
                "pipeline": "local-verification-v1"
                if args.engine == "legacy"
                else "evidence-id-v2",
                "inputs": progress["input_signature"],
                "instructions": instructions,
                "base": settings.base,
                "model": settings.model,
                "authorities": config.extra_authority_hosts,
                "overrides": overrides,
                "warc": [digest(p.read_bytes().hex()) for p in args.warc],
            }
            if args.engine == "v2":
                signature["discovery_index"] = (
                    config.discovery_index.read_text(encoding="utf-8")
                    if config.discovery_index
                    else None
                )
            db.bind(digest(signature))
            db.ingest(questions)
            db.recover()
            pending = db.pending(args.limit, args.retry_failed)
            if args.start_id and (not pending or pending[0] != args.start_id):
                raise Conflict(
                    f"Next pending ID is {pending[0] if pending else None}, not {args.start_id}"
                )
            retriever = SourceRetriever(db, config)
            if args.engine == "v2":
                from .pipeline_v2 import PipelineV2

                engine = PipelineV2
            else:
                engine = Pipeline
            pipeline = engine(
                db, config, settings, instructions, retriever, source_overrides=overrides
            )
            try:
                for path in args.warc:
                    print(
                        f"WARC {path.name}: {retriever.import_warc(path)} records imported",
                        flush=True,
                    )
                timing = pipeline.run(args.limit, args.retry_failed)
                report = {**progress, "run": timing, "local": db.report()}
                if args.output:
                    protected = [args.benchmark, args.queue, args.instructions, *args.warc]
                    if args.evidence:
                        protected.append(args.evidence)
                    if args.original_evidence:
                        protected.append(args.original_evidence)
                    if args.source_overrides:
                        protected.append(args.source_overrides)
                    report["export"] = export_package(db, args.output, protected)
                return report
            finally:
                pipeline.close()
                retriever.close()
    if not config.database.is_file():
        raise ValueError("Database does not exist; run an import first")
    with process_lock(config.database.with_suffix(".lock")):
        db = Database(config.database)
        if args.command == "export":
            return export_package(db, args.output)
        return db.report()["failures"] if args.command == "failures" else db.report()


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        report = execute(args)
        print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)
        if isinstance(report, dict) and report.get("run", {}).get("failed"):
            return 1
        return 0
    except KeyboardInterrupt:
        print(
            "Interrupted. Checkpoints retained; repeat the same run command to resume.",
            file=sys.stderr,
        )
        return 130
    except Exception as exc:
        # No tracebacks with authenticated HTTP request objects or credential payloads.
        message = (
            str(exc)
            if isinstance(exc, (ValueError, Conflict, FileNotFoundError))
            else type(exc).__name__
        )
        print("Verification failed: " + message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
