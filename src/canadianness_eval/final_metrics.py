"""Exact supplied research configuration; no generation and no implied approval."""

import hashlib
import json
import re
from pathlib import Path

from openpyxl import load_workbook
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .settings import ROOT

SOURCE_JSON = ROOT / "Canadianness_Final_GEVAL_Metrics.json"
SOURCE_EXCEL = ROOT / "Canadianness_Final_GEVAL_Evaluation_Steps.xlsx"
FINAL_JSON = ROOT / "config/final/2026-11-03-v1/metrics_final.json"
PARAMS = ["INPUT", "ACTUAL_OUTPUT", "EXPECTED_OUTPUT", "CONTEXT"]


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Band(BaseModel):
    model_config = ConfigDict(extra="forbid")
    min: int = Field(strict=True, ge=0, le=10)
    max: int = Field(strict=True, ge=0, le=10)
    expected_outcome: str = Field(min_length=1)


class StepProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_id: str
    source_candidate_ids: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1)


class FinalMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric_id: str
    name: str = Field(min_length=1)
    criteria: str = Field(min_length=1)
    scope_exclusions: str = Field(min_length=1)
    required_evaluation_params: list[str]
    optional_evaluation_params: list[str]
    evaluation_steps: list[str] = Field(min_length=6, max_length=6)
    steps_provenance: list[StepProvenance] = Field(min_length=6, max_length=6)
    rubric_0_to_10: list[Band] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def coherent(self):
        if any(not value.strip() for value in (self.name, self.criteria, self.scope_exclusions)):
            raise ValueError("Metric definitions cannot be blank")
        if self.metric_id not in {f"M{i}" for i in range(1, 8)}:
            raise ValueError("Unknown metric ID")
        required = PARAMS[:2] if self.metric_id in ("M1", "M4") else PARAMS
        optional = PARAMS[2:] if self.metric_id in ("M1", "M4") else []
        if (
            self.required_evaluation_params != required
            or self.optional_evaluation_params != optional
        ):
            raise ValueError("Unexpected evaluation parameter requirements")
        if [(b.min, b.max) for b in self.rubric_0_to_10] != [
            (0, 2),
            (3, 4),
            (5, 6),
            (7, 8),
            (9, 10),
        ]:
            raise ValueError("Invalid or overlapping rubric bands")
        if any(not step.strip() for step in self.evaluation_steps):
            raise ValueError("Blank final step")
        expected_ids = [f"{self.metric_id}-S{i}" for i in range(1, 7)]
        if [p.step_id for p in self.steps_provenance] != expected_ids:
            raise ValueError("Step IDs must be unique and ordered consistently with metric")
        return self


class FinalConfig(BaseModel):
    model_config = ConfigDict(extra="allow")  # Retain original top-level provenance verbatim.
    title: str
    version: str = Field(min_length=1)
    status: str
    metrics: list[FinalMetric] = Field(min_length=7, max_length=7)

    @model_validator(mode="after")
    def all_metrics(self):
        if [m.metric_id for m in self.metrics] != [f"M{i}" for i in range(1, 8)]:
            raise ValueError("Exactly M1-M7 in order required")
        ids = [p.step_id for m in self.metrics for p in m.steps_provenance]
        if len(set(ids)) != 42:
            raise ValueError("Duplicated step IDs")
        return self


def load_final(path=FINAL_JSON):
    return FinalConfig.model_validate_json(Path(path).read_text(encoding="utf-8-sig"))


def install_final(source=SOURCE_JSON, destination=FINAL_JSON):
    load_final(source)
    destination = Path(destination)
    if destination.exists():
        if file_hash(source) != file_hash(destination):
            raise ValueError(
                "Versioned final JSON differs; choose a new version path instead of overwriting"
            )
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as handle:
            handle.write(Path(source).read_bytes())
    return destination


def validate_final(json_path=SOURCE_JSON, workbook_path=SOURCE_EXCEL, report_path=None):
    config = load_final(json_path)
    warnings, errors = [], []
    book = load_workbook(workbook_path, data_only=False)
    steps = [r for r in book["FINAL STEPS"].values if r[0] in {m.metric_id for m in config.metrics}]
    rubrics = [
        r for r in book["SCORING RUBRICS"].values if r[0] in {m.metric_id for m in config.metrics}
    ]
    traces = [
        r for r in book["SOURCE TRACE"].values if r[0] in {m.metric_id for m in config.metrics}
    ]
    overview = [
        r for r in book["METRIC OVERVIEW"].values if r[0] in {m.metric_id for m in config.metrics}
    ]
    if len(steps) != 42 or len(rubrics) != 35 or len(traces) != 42 or len(overview) != 7:
        errors.append("Workbook has unexpected metric/step/rubric/provenance row counts")
    for metric in config.metrics:
        mid = metric.metric_id
        rows = [r for r in steps if r[0] == mid]
        if [(r[1], r[2]) for r in rows] != list(enumerate(metric.evaluation_steps, 1)):
            errors.append(f"{mid}: workbook step wording/order differs from JSON")
        if [(r[1], r[2], r[4]) for r in rubrics if r[0] == mid] != [
            (b.min, b.max, b.expected_outcome) for b in metric.rubric_0_to_10
        ]:
            errors.append(f"{mid}: workbook rubric differs from JSON")
        row = next((r for r in overview if r[0] == mid), None)
        if row is None or tuple(row[1:4]) != (
            metric.name,
            metric.criteria,
            metric.scope_exclusions,
        ):
            errors.append(f"{mid}: metric overview differs from JSON")
        for index, provenance in enumerate(metric.steps_provenance, 1):
            trace = next((r for r in traces if r[0] == mid and r[1] == index), None)
            if (
                trace is None
                or trace[3] != metric.evaluation_steps[index - 1]
                or [x.strip() for x in trace[4].split(",")] != provenance.source_candidate_ids
                or trace[5] != provenance.rationale
            ):
                errors.append(f"{provenance.step_id}: workbook source trace differs")
            elif trace[2] != provenance.step_id:
                if re.sub(r"-S0+(\d+)$", r"-S\1", trace[2]) != provenance.step_id:
                    errors.append(f"{provenance.step_id}: inconsistent workbook ID")
        # Check supplied candidate provenance against preserved actual generations.
        for provenance in metric.steps_provenance:
            for candidate in provenance.source_candidate_ids:
                match = re.fullmatch(r"(M\d)-R(\d+)-(\d+)", candidate)
                if not match:
                    errors.append(f"Malformed candidate ID: {candidate}")
                    continue
                cid, run, step = match.groups()
                path = ROOT / "outputs/generations" / cid / f"run_{int(run):02}.json"
                if path.exists():
                    record = json.loads(path.read_text(encoding="utf-8"))
                    if cid != mid or not 1 <= int(step) <= len(record["evaluation_steps"]):
                        errors.append(f"Unresolvable source candidate: {candidate}")
                else:
                    warnings.append(f"Original generation not available locally: {candidate}")
    warnings.append(
        "Workbook IDs use zero-padded S01; JSON uses S1. Wording/order and source IDs checked; original files unchanged."
    )
    warnings.append(
        "Configuration is proposed for calibration, not a human-approved frozen scientific standard."
    )
    warnings.append(
        "M6 rubric mentions unsupported claims; final steps distinguish not-established from contradicted. Test this tension empirically; no wording changed."
    )
    book.close()
    result = {
        "valid": not errors,
        "version": config.version,
        "metrics": 7,
        "steps": 42,
        "rubric_bands": 35,
        "json_sha256": file_hash(json_path),
        "workbook_sha256": file_hash(workbook_path),
        "warnings": warnings,
        "errors": errors,
    }
    if report_path:
        path = Path(report_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Final metric validation",
            "",
            f"Valid: **{result['valid']}**",
            "",
            f"Version: `{config.version}`; seven metrics, 42 exact steps, 35 rubric bands.",
            "",
            f"JSON SHA-256: `{result['json_sha256']}`",
            "",
            f"Workbook SHA-256: `{result['workbook_sha256']}`",
            "",
            "Step wording, order, criteria, exclusions, rubric descriptions and provenance were compared with the workbook.",
            "Required inputs match the supplied M1/M4 versus evidence-dependent metric mapping. No semantic edits were made.",
            "",
        ]
        lines += ["- " + value for value in errors + warnings]
        if path.exists() and path.read_text(encoding="utf-8") != "\n".join(lines) + "\n":
            raise ValueError(
                "Validation report already exists with different content; choose another path"
            )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if errors:
        raise ValueError("Final metric consistency errors: " + "; ".join(errors))
    return result
