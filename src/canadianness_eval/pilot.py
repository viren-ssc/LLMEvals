from .dataset import load_dataset
from .storage import write_json


def report_pilot(rows, input_path, output_dir):
    cases = {c.question_id: c for c in load_dataset(input_path)}
    checks = []
    for mid in [f"M{i}" for i in range(1, 8)]:
        scores = {
            cases[r["question_id"]].expected_quality: r["score"]
            for r in rows
            if r["metric_id"] == mid and r["status"] == "success"
        }
        complete = all(k in scores for k in ("weak", "moderate", "strong"))
        checks.append(
            dict(
                metric_id=mid,
                scores=scores,
                ordering_passed=(
                    scores["strong"] > scores["weak"]
                    and scores["strong"] >= scores["moderate"] >= scores["weak"]
                )
                if complete
                else None,
                interpretation="Calibration exercise; no claim of human agreement or validity",
            )
        )
    write_json(
        output_dir / "pilot_report.json",
        {
            "ordering_checks": checks,
            "pending_analyses": [
                "Human agreement",
                "Repeated-judge variability",
                "Matched length perturbations",
                "Presentation and language bias",
            ],
        },
    )
