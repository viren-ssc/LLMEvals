"""Additional unambiguous paraphrase controls; original calibration dataset stays unchanged."""

from canadianness_eval.calibration.pilot_cases import build_cases
from canadianness_eval.settings import ROOT

if __name__ == "__main__":
    base = next(c for c in build_cases() if c.question_id == "CAL-M4-FRENCH-VARIANT")
    cases = []
    for suffix, answer in [
        ("PENDANT", "Le bureau sera fermé pendant la fin de semaine."),
        ("DURANT", "Le bureau sera fermé durant la fin de semaine."),
    ]:
        cases.append(
            base.model_copy(
                update={
                    "question_id": "CAL-M4-FRENCH-" + suffix,
                    "model_answer": answer,
                    "dataset_version": "synthetic-calibration-2026-11-03-french-supplement-v1",
                    "case_family": "canadian_french_unambiguous_paraphrase",
                    "comparison_group": "M4-french-unambiguous",
                    "comparison_role": suffix.lower(),
                    "expected_behavior": "Both retain the same Canadian fin-de-semaine expression; pendant/durant is a harmless syntactic paraphrase. Synthetic expectation requiring human confirmation.",
                }
            )
        )
    path = ROOT / "data/calibration/french_supplement_v1.jsonl"
    content = "\n".join(c.model_dump_json() for c in cases) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise SystemExit("Supplement already exists with different content")
    if not path.exists():
        path.write_text(content, encoding="utf-8")
    print(path)
