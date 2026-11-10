from pydantic import BaseModel, Field, model_validator

from .settings import ROOT
from .storage import read_yaml

IDS = {f"M{i}" for i in range(1, 8)}


class MetricDefinition(BaseModel):
    metric_id: str
    metric_name: str
    purpose: str
    definition: str
    examine: list[str] = Field(min_length=1)
    strong_performance: str
    poor_performance: str
    failure_modes: list[str]
    exclusions: str
    required_evidence: list[str]
    evaluation_params: list[str]
    coverage_concepts: list[str]
    criteria: str

    @model_validator(mode="after")
    def validate_params(self):
        mapping = {
            "question": "INPUT",
            "model_answer": "ACTUAL_OUTPUT",
            "reference_answer": "EXPECTED_OUTPUT",
            "reference_context": "CONTEXT",
        }
        if self.metric_id not in IDS or any(
            mapping[x] not in self.evaluation_params for x in self.required_evidence
        ):
            raise ValueError("Unknown metric or evidence absent from evaluation parameters")
        return self


def load_metrics(path=ROOT / "config/metric_definitions.yaml"):
    metrics = [MetricDefinition.model_validate(x).model_dump() for x in read_yaml(path)["metrics"]]
    if {m["metric_id"] for m in metrics} != IDS or len(metrics) != 7:
        raise ValueError("Exactly M1-M7 required")
    return metrics
