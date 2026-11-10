from .settings import ROOT
from .storage import read_yaml


def validate_bands(bands):
    ranges = [b["score_range"] for b in bands]
    if ranges != [[0, 2], [3, 4], [5, 6], [7, 8], [9, 10]]:
        raise ValueError("Require five ordered nonoverlapping bands covering integers 0-10")
    if any(not isinstance(b["description"], str) or not b["description"].strip() for b in bands):
        raise ValueError("Every band requires a behavioral description")


def load_rubrics(path=ROOT / "config/rubric_drafts.yaml"):
    rubrics = read_yaml(path)["rubrics"]
    for rubric in rubrics.values():
        validate_bands(rubric["bands"])
    return rubrics
