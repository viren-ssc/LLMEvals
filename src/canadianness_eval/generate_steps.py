"""Use the documented GEvalTemplate extension point, without a scoring call."""

import json
import time
from pathlib import Path

from deepeval.metrics import GEval
from deepeval.metrics.g_eval import GEvalTemplate
from deepeval.test_case import SingleTurnParams
from pydantic import BaseModel, Field, field_validator

from .storage import digest, now, versions, write_json


class Steps(BaseModel):
    steps: list[str] = Field(min_length=5, max_length=8)

    @field_validator("steps")
    @classmethod
    def nonempty(cls, values):
        if any(not x.strip() for x in values):
            raise ValueError("Blank step")
        return values


class ResearchTemplate(GEvalTemplate):
    @staticmethod
    def generate_evaluation_steps(parameters, criteria):
        # Retain installed official template and change only its default step count instruction.
        prompt = GEvalTemplate.generate_evaluation_steps(parameters=parameters, criteria=criteria)
        return (
            prompt.replace("3-4", "5-8")
            + "\nReturn 5 to 8 specific actionable steps in the steps array."
        )


def generate_all(metrics, judge, directory, runs=4, force=False):
    if runs not in (3, 4):
        raise ValueError("runs must be 3 or 4")
    records = []
    for metric in metrics:
        signature = digest(
            {
                "definition": metric,
                "model": judge.get_model_name(),
                "template": "ResearchTemplate-v1",
                "deepeval": versions()["deepeval"],
            }
        )
        for number in range(1, runs + 1):
            path = Path(directory) / metric["metric_id"] / f"run_{number:02}.json"
            if path.exists():
                old = json.loads(path.read_text(encoding="utf-8"))
                if old["status"] == "success" and not force:
                    if old["generation_signature"] != signature:
                        raise ValueError(
                            "Generation inputs changed; use a new output directory or --force"
                        )
                    records.append(old)
                    print(f"{metric['metric_id']}: Run {number}/{runs} resumed")
                    continue
                # Keep immutable previous attempt including successful outputs on explicit regeneration.
                archive = (
                    path.parent / "history" / (path.stem + "_" + str(time.time_ns()) + ".json")
                )
                write_json(archive, old)
            record = {
                "metric_id": metric["metric_id"],
                "metric_name": metric["metric_name"],
                "run_number": number,
                "model_id": judge.get_model_name(),
                "criteria": metric["criteria"],
                "generation_timestamp": now(),
                "generation_signature": signature,
                "generation_settings": {
                    "sampling": "gateway default; no unsupported temperature assumed",
                    "cache": False,
                    "template": "ResearchTemplate-v1",
                },
                "package_versions": versions(),
                "evaluation_steps": [],
                "status": "failed",
            }
            instance = GEval(
                name=metric["metric_name"],
                criteria=metric["criteria"],
                evaluation_params=[SingleTurnParams[x] for x in metric["evaluation_params"]],
                model=judge,
                evaluation_template=ResearchTemplate,
                async_mode=False,
            )
            prompt = instance.evaluation_template.generate_evaluation_steps(
                ", ".join(metric["evaluation_params"]), instance.criteria
            )
            record["prompt"] = prompt
            start = time.perf_counter()
            before = judge.gateway.attempts
            offset = len(judge.gateway.history)
            try:
                result = judge.generate(prompt, schema=Steps)
                record.update(evaluation_steps=result.steps, status="success")
            except Exception as exc:
                record["error"] = judge.gateway.safe_error(exc)
            record.update(
                latency_seconds=time.perf_counter() - start,
                attempt_count=judge.gateway.attempts - before,
                responses=judge.gateway.history[offset:],
                structured_mode=judge.gateway.structured_mode,
            )
            write_json(path, record)
            records.append(record)
            print(f"{metric['metric_id']}: Run {number}/{runs} {record['status']}", flush=True)
    return records
