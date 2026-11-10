"""Immutable delta packages: stable IDs, evidence, audit and provenance, never source workbooks."""

import hashlib
import json
import shutil
import tempfile
import time
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

from .db import Conflict
from .gates import quality_errors
from .models import digest, now


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_package(path):
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    for name, sha in manifest["files"].items():
        if file_hash(path / name) != sha:
            raise Conflict(f"Export readback/hash mismatch: {name}")
    for name, count in manifest["counts"].items():
        rows = [
            json.loads(line)
            for line in (path / (name + ".jsonl")).read_text(encoding="utf-8").splitlines()
        ]
        if len(rows) != count:
            raise Conflict(f"Export count mismatch: {name}")
    book = load_workbook(path / "results.xlsx", read_only=True)
    try:
        for name, count in manifest["counts"].items():
            if book[name].max_row != count + 1:
                raise Conflict(f"Excel row count mismatch: {name}")
    finally:
        book.close()
    return manifest


def export_package(db, target, protected_inputs=()):
    db.check_integrity()
    resolved = target.resolve()
    for path in protected_inputs:
        input_path = path.resolve()
        if resolved == input_path or resolved in input_path.parents:
            raise Conflict("Export directory contains an original input file")
    tables = {name: [] for name in ("proposed_updates", "claims", "sources", "audit", "failures")}
    source_index = {}
    for event_id, result in db.results():
        if errors := quality_errors(result):
            raise Conflict("Export consistency errors: " + "; ".join(errors))
        tables["proposed_updates"].append(
            {
                "question_id": result.question_id,
                "event_id": event_id,
                "input_fingerprint": result.input_fingerprint,
                "research_disposition": result.proposal.disposition,
                "original_answer_fully_supported": result.fully_supported,
                "proposed_answer_draft": result.proposal.corrected_answer,
                "corrected_answer_verified": False,
                "proposed_primary_metric": result.metric.primary_metric,
                "metric_suitable": result.metric.suitable,
                "metric_reason": result.metric.explanation,
                "missing_information": result.proposal.missing_information,
                "gate_errors": result.gate_errors,
                "reason": result.proposal.explanation,
                "human_approval": "",
                "independent_ai_audit": "",
                "created_at": result.created_at,
                "judge_model": result.judge_model,
                "instructions_sha256": result.instructions_sha256,
            }
        )
        if hasattr(result, "reference_status"):
            tables["proposed_updates"][-1].update(
                reference_status=result.reference_status,
                extraction_errors=result.alignment_errors,
                baseline_event_id=result.baseline_event_id,
                pipeline_version=2,
                tested_operation=result.metric.tested_operation,
                metric_review_flags=result.metric.review_flags,
            )
        for c in result.claims:
            common = {
                "question_id": result.question_id,
                "claim_id": c.claim_id,
                "event_id": event_id,
                **c.claim.model_dump(),
                "verdict": c.judgment.verdict,
                "verdict_explanation": c.judgment.explanation,
            }
            for i, citation in enumerate(c.judgment.citations or [None]):
                tables["claims"].append(
                    {
                        **common,
                        "evidence_id": c.claim_id + f"-E{i + 1}",
                        **(citation.model_dump() if citation else {}),
                    }
                )
        for source in result.sources:
            sid = digest([source.url, source.sha256, source.historical])
            source_index[sid] = {"source_id": sid, **source.model_dump()}
    tables["sources"] = list(source_index.values())
    tables["audit"] = db.audits()
    tables["failures"] = db.report()["failures"]
    signature = digest(tables)
    if target.exists():
        existing = verify_package(target)
        if existing["content_signature"] != signature:
            raise Conflict("Export path already holds a different package; choose a new path")
        return existing
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".verify-export-", dir=target.parent))
    try:
        raw_dir = stage / "source_bytes"
        raw_dir.mkdir()
        for source in tables["sources"]:
            if source["status"] == "ok":
                raw = Path(source["raw_path"])
                if not raw.is_file() or file_hash(raw) != source["sha256"]:
                    raise Conflict("Missing or altered cached source bytes; export blocked")
                shutil.copyfile(raw, raw_dir / (source["sha256"] + ".raw"))
                source["packaged_raw_path"] = "source_bytes/" + source["sha256"] + ".raw"
                if source["historical"] and source["archive_container_path"]:
                    archive = Path(source["archive_container_path"])
                    sha = source["archive_container_sha256"]
                    if not archive.is_file() or file_hash(archive) != sha:
                        raise Conflict("Missing or altered WARC container; export blocked")
                    shutil.copyfile(archive, raw_dir / (sha + ".warc"))
                    source["packaged_warc_path"] = "source_bytes/" + sha + ".warc"
        book = Workbook()
        book.remove(book.active)
        for name, records in tables.items():
            (stage / (name + ".jsonl")).write_text(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8"
            )
            sheet = book.create_sheet(name)
            headers = list(dict.fromkeys(k for record in records for k in record)) or ["no_records"]
            sheet.append(headers)
            for record in records:
                values = []
                for h in headers:
                    value = record.get(h, "")
                    if isinstance(value, (list, dict)):
                        value = json.dumps(value, ensure_ascii=False)
                    if isinstance(value, str) and len(value) > 32000:
                        value = value[:31000] + f"\n[Full value in {name}.jsonl]"
                    if isinstance(value, str):
                        value = ILLEGAL_CHARACTERS_RE.sub("", value)
                    values.append(value)
                sheet.append(values)
            # Excel must treat scraped text, questions and LLM outputs as literal strings.
            for row in sheet:
                for cell in row:
                    if isinstance(cell.value, str):
                        cell.data_type = "s"
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
        book.save(stage / "results.xlsx")
        book.close()
        manifest = {
            "format_version": 1,
            "created_at": now(),
            "content_signature": signature,
            "kind": "proposed_updates_only",
            "research_is_independent_ai_audit": False,
            "counts": {k: len(v) for k, v in tables.items()},
            "progress": db.report(),
            "files": {
                str(p.relative_to(stage)).replace("\\", "/"): file_hash(p)
                for p in stage.rglob("*")
                if p.is_file()
            },
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        verify_package(stage)
        for attempt in range(5):
            try:
                stage.rename(target)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.1 * 2**attempt)
        return manifest
    finally:
        if stage.exists():
            if stage.resolve().parent != target.parent.resolve() or not stage.name.startswith(
                ".verify-export-"
            ):
                raise Conflict("Refusing cleanup outside the verified export staging directory")
            # Only this invocation's known temporary directory, never the input/output target.
            shutil.rmtree(stage)
