import re
from pathlib import Path

import pandas as pd
import yaml

from .consolidate_steps import normalized
from .metric_definitions import IDS, MetricDefinition, load_metrics
from .rubric_builder import validate_bands
from .storage import digest, now, read_yaml


def freeze(workbook, destination, reviewer, version="v1"):
    if not reviewer.strip() or not re.fullmatch(r"[A-Za-z0-9_.-]+", version):
        raise ValueError("Reviewer identity and a simple version identifier required")
    destination = Path(destination)
    if destination.exists():
        raise ValueError("Frozen configuration exists. Choose a new version; overwrite forbidden.")
    candidates = pd.read_excel(workbook, sheet_name="Step Candidates", keep_default_na=False)
    rubrics = pd.read_excel(workbook, sheet_name="Rubric Review", keep_default_na=False)
    summary = pd.read_excel(workbook, sheet_name="Review Summary", keep_default_na=False)
    summaries = dict(zip(summary.iloc[:, 0], summary.iloc[:, 1]))
    metrics = load_metrics()
    if summaries.get("metric_definitions_hash") != digest(metrics):
        raise ValueError(
            "Metric definitions changed since workbook creation or workbook provenance is missing"
        )
    errors, finals = [], []
    if set(rubrics.metric_id) != IDS or not set(candidates.metric_id).issubset(IDS):
        raise ValueError("Workbook metric IDs must be M1-M7")
    for metric in metrics:
        mid = metric["metric_id"]
        subset = candidates[candidates.metric_id == mid]
        invalid = subset[
            ~subset.manual_selection.isin(["", "Keep", "Reject", "Revise", "Undecided"])
        ]
        if len(invalid):
            errors.append(f"{mid}: invalid manual decision")
        selected = subset[subset.manual_selection.isin(["Keep", "Revise"])]
        steps, orders, seen = [], set(), set()
        for _, row in selected.iterrows():
            text = str(row.edited_final_wording).strip() or str(row.original_step).strip()
            if row.manual_selection == "Revise" and not str(row.edited_final_wording).strip():
                errors.append(f"{mid}: Revise requires edited wording")
            try:
                order = float(row.final_order)
                if not order.is_integer() or order <= 0 or order in orders:
                    raise ValueError()
            except (TypeError, ValueError):
                errors.append(f"{mid}: chosen steps need unique positive integer final_order")
                continue
            orders.add(order)
            key = normalized(text)
            if not key:
                errors.append(f"{mid}: blank step")
            elif key not in seen:
                steps.append((order, text))
                seen.add(key)
        if not steps:
            errors.append(f"{mid}: select at least one step")
        # Conservative contradiction check: identical statements with opposite explicit polarity.
        positives, negatives = set(), set()
        for _, text in steps:
            key = normalized(text)
            if key.startswith("do not "):
                negatives.add(key.removeprefix("do not "))
            elif key.startswith("never "):
                negatives.add(key.removeprefix("never "))
            else:
                positives.add(key)
        if positives & negatives:
            errors.append(f"{mid}: contradictory positive and negative selected instructions")
        bands = []
        rubric_rows = rubrics[rubrics.metric_id == mid]
        if len(rubric_rows) != 5 or any(
            str(x).strip().lower() != "yes" for x in rubric_rows.approved
        ):
            errors.append(f"{mid}: all five rubric bands require explicit Yes approval")
        for _, row in rubric_rows.iterrows():
            try:
                if float(row.score_min) != int(row.score_min) or float(row.score_max) != int(
                    row.score_max
                ):
                    raise ValueError()
                bands.append(
                    {
                        "score_range": [int(row.score_min), int(row.score_max)],
                        "description": str(row.description).strip(),
                    }
                )
            except (ValueError, TypeError):
                errors.append(f"{mid}: invalid score bounds")
        try:
            validate_bands(bands)
        except ValueError as exc:
            errors.append(f"{mid}: {exc}")
        guidance = list(dict.fromkeys(str(x).strip() for x in rubric_rows.guidance))
        if not guidance or any(not x for x in guidance) or len(guidance) != 1:
            errors.append(f"{mid}: rubric guidance must be nonempty and consistent across bands")
        finals.append(
            {
                **metric,
                "evaluation_steps": [s for _, s in sorted(steps)],
                "rubric": bands,
                "rubric_guidance": guidance[0] if guidance else "",
            }
        )
    if errors:
        raise ValueError("Review validation failed:\n" + "\n".join(errors))
    config = dict(
        status="FROZEN",
        rubric_version=version,
        approval_date=now(),
        reviewer=reviewer,
        source_workbook_hash=__import__("hashlib").sha256(Path(workbook).read_bytes()).hexdigest(),
        metrics=finals,
        approval_attestation="Reviewer approved selected steps, order, evidence parameters, definitions and rubric bands; checked for contradictions.",
    )
    config["configuration_hash"] = digest(config)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation: never silently replace a frozen version.
    with destination.open("x", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, sort_keys=False, allow_unicode=True)
    return config


def load_frozen(path):
    if not Path(path).exists():
        raise ValueError(
            "No approved frozen configuration exists. Complete human review and run freeze-review first."
        )
    config = read_yaml(path)
    signature = config.pop("configuration_hash")
    if digest(config) != signature or config.get("status") != "FROZEN":
        raise ValueError("Frozen configuration invalid or altered")
    if {m["metric_id"] for m in config["metrics"]} != IDS or len(config["metrics"]) != 7:
        raise ValueError("Frozen configuration requires all seven metrics")
    for metric in config["metrics"]:
        MetricDefinition.model_validate(metric)
        validate_bands(metric["rubric"])
        if not metric["evaluation_steps"] or any(not s.strip() for s in metric["evaluation_steps"]):
            raise ValueError("Missing approved steps")
    return {**config, "configuration_hash": signature}
