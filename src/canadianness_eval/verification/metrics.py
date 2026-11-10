"""Suitability of the question's primary metric, independent of reference truth or scoring."""

from .models import MetricAssessment


def assess(question, instructions, call):
    return call(
        "metric",
        {
            "question": question.question,
            "original_metric": question.metric,
            "project_instructions": instructions,
        },
        MetricAssessment,
        "Assess which ONE primary metric this question tests. Assess construct suitability, "
        "not correctness of the reference answer. Do not score a model response.",
    )
