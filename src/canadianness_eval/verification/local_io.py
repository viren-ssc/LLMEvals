"""Read-only imports. Never open a benchmark workbook for writing."""

import json
import re
import zipfile
from pathlib import Path

from openpyxl import load_workbook

from .db import Conflict
from .models import Question, digest


def read_rows(path: Path, sheet: str):
    if path.suffix.lower() == ".jsonl":
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]
        if any(not isinstance(row, dict) for row in rows):
            raise ValueError("JSONL records must be objects")
        return rows
    if path.suffix.lower() != ".xlsx" and not zipfile.is_zipfile(path):
        raise ValueError("Use .xlsx or .jsonl inputs")
    # Some downloaded workbooks retain .txt filenames. Inspect the container and use
    # a binary handle so openpyxl doesn't reject a valid workbook by extension.
    handle = path.open("rb")
    try:
        book = load_workbook(handle, read_only=True, data_only=True)
    except BaseException:
        handle.close()
        raise
    try:
        if sheet not in book.sheetnames:
            raise ValueError(f"Missing worksheet {sheet!r} in {path}")
        iterator = book[sheet].iter_rows(values_only=True)
        headers = [str(h).strip() if h is not None else "" for h in next(iterator)]
        named = [h for h in headers if h]
        if len(named) != len(set(named)):
            raise ValueError(f"Duplicate column headers in {sheet}")
        return [
            {h: v for h, v in zip(headers, row) if h}
            for row in iterator
            if any(v is not None for v in row)
        ]
    finally:
        book.close()
        handle.close()


def strings(row):
    return {
        k: ""
        if v is None
        else (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else str(v))
        for k, v in row.items()
    }


def field(row, *keys, default=""):
    for key in keys:
        if row.get(key) not in (None, ""):
            return row[key]
    return default


def index_rows(rows, *id_keys):
    indexed = {}
    for row in rows:
        key = str(field(row, *id_keys)).strip()
        if not key or key in indexed:
            raise Conflict(f"Missing or duplicate ID: {key!r}")
        indexed[key] = row
    return indexed


def urls(value):
    if isinstance(value, list):
        return list(dict.fromkeys(str(x).strip() for x in value))
    return list(
        dict.fromkeys(u.rstrip(".,;)") for u in re.findall(r"https?://[^\s|<>\"]+", str(value)))
    )


def load_inputs(
    benchmark,
    queue,
    evidence=None,
    question_sheet="Questions",
    queue_sheet="Cycle 100 Queue",
    evidence_sheet="Verified claims",
    expected_queue=100,
    original_evidence=None,
    original_evidence_sheet="Original evidence",
):
    masters = index_rows(read_rows(benchmark, question_sheet), "question_id", "Question ID")
    queue_rows = read_rows(queue, queue_sheet)
    selected = index_rows(queue_rows, "question_id", "Question ID")
    if expected_queue and len(selected) != expected_queue:
        raise Conflict(f"Expected {expected_queue} queue IDs; found {len(selected)}")
    evidence_rows = read_rows(evidence, evidence_sheet) if evidence else []
    original_rows = (
        read_rows(original_evidence, original_evidence_sheet) if original_evidence else []
    )
    for row in evidence_rows + original_rows:
        qid = str(field(row, "question_id", "Question ID"))
        if qid not in masters:
            raise Conflict(f"Evidence refers to unknown question ID: {qid}")
    if evidence_rows:
        index_rows(evidence_rows, "claim_id", "Claim ID")
    pending, completed = [], []
    for qid, row in selected.items():
        if qid not in masters:
            raise Conflict(f"Queue ID absent from benchmark: {qid}")
        status = str(field(row, "status", "Cycle status")).strip().lower()
        if status in {"follow-up saved", "research saved", "completed", "done"}:
            completed.append(qid)
            continue
        if status != "pending":
            raise Conflict(f"Unknown queue status for {qid}: {status!r}")
        master = masters[qid]
        answer = str(field(master, "reference_answer", "Original proposed answer"))
        question = str(field(master, "question", "Question"))
        if not question.strip() or not answer.strip():
            raise Conflict(f"Missing question/reference answer for {qid}")
        pending.append(
            Question(
                question_id=qid,
                question=question,
                answer=answer,
                metric=field(master, "metric", "Original metric"),
                source_urls=urls(field(master, "source_urls", "Original source URL(s)")),
                original_row=strings(master),
                queue_row=strings(row),
                prior_claims=[
                    strings(e)
                    for e in evidence_rows
                    if str(field(e, "question_id", "Question ID")) == qid
                ],
                original_evidence=[
                    strings(e)
                    for e in original_rows
                    if str(field(e, "question_id", "Question ID")) == qid
                ],
            )
        )
    return pending, {
        "benchmark_questions": len(masters),
        "queue_selected": len(selected),
        "queue_completed_on_import": len(completed),
        "queue_pending_on_import": len(pending),
        "first_pending": pending[0].question_id if pending else None,
        "input_signature": digest(
            {
                "master": masters,
                "queue": list(selected.items()),
                "evidence": evidence_rows,
                "original_evidence": original_rows,
            }
        ),
    }
