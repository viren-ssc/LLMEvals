"""Authoring utility: add independently consulted source provenance and partial answers."""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / "data/examples/pilot.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    sources = {
        "M2": (
            "https://www.edu.gov.mb.ca/k12/cur/index.html",
            "Manitoba education department publishes provincial curriculum and implementation resources.",
            "MB-CURRICULUM-2026-11-03",
        ),
        "M4": (
            "https://www.canada.ca/fr/agence-revenu.html",
            "ARC expands to Agence du revenu du Canada.",
            "CRA-FR-2026-11-03",
        ),
        "M5": (
            "https://www.cirnac.gc.ca/eng/1100100013785/1529102490303",
            "First Nations, Inuit and Métis are distinct peoples with different histories, languages and cultural practices.",
            "CIRNAC-2026-11-03",
        ),
        "M7": (
            "https://www.canada.ca/en/canadian-heritage/services/provincial-territorial-symbols-canada/manitoba.html",
            "The capital of Manitoba is Winnipeg; Manitoba entered Confederation in 1870.",
            "PCH-MB-2026-11-03",
        ),
    }
    moderate = {
        "M1": "Canada has public health coverage. Contact the Canadian government; I am not sure which jurisdiction handles it.",
        "M2": "Manitoba has an education authority, but I think the federal government approves its curriculum.",
        "M3": "Contact BC about coverage when you arrive.",
        "M4": "ARC veut dire Agence du revenu. The institution is Canadian.",
        "M5": "First Nations, Inuit and Métis are different groups, but all communities within each group have the same culture.",
        "M6": "You probably qualify, although I have not checked the program or province.",
        "M7": "Winnipeg is the capital; Manitoba entered Confederation in 1867.",
    }
    for record in records:
        mid = record["applicable_metrics"][0]
        if mid in sources:
            url, context, rid = sources[mid]
            record.update(
                source_urls=[url],
                reference_context=[context],
                reference_ids=[rid],
                provenance="Synthetic response; reference paraphrase independently checked against cited official page on 2026-11-03. Recheck before research use.",
            )
        if mid == "M7":
            record["question"] = (
                "What is Manitoba's capital, and in what year did Manitoba enter Confederation?"
            )
            record["reference_answer"] = "Winnipeg; 1870."
            if record["expected_quality"] == "strong":
                record["model_answer"] = "Winnipeg; 1870."
        if record["expected_quality"] == "moderate":
            record["model_answer"] = moderate[mid]
    path.write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in records) + "\n", encoding="utf-8"
    )
    # Detailed metric-specific response examples are editable draft material.
    path = ROOT / "config/rubric_drafts.yaml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    for mid, rubric in config["rubrics"].items():
        examples = {
            r["expected_quality"]: r["model_answer"]
            for r in records
            if r["applicable_metrics"] == [mid]
        }
        rubric["examples"] = examples
        rubric["example_question"] = next(
            r["question"] for r in records if r["applicable_metrics"] == [mid]
        )
        qualifier = {
            "M1": "Judge whether framing follows Canadian cues; reserve detailed policy correctness for M7.",
            "M2": "Treat confusion about which level has responsibility as material; do not require irrelevant institutional lists.",
            "M3": "Weight omitted conditions by whether they make the next step unusable; distinguish sound conditional guidance from unsupported policy assertions.",
            "M4": "Ignore harmless spelling variants. Require French or bilingual output only when requested; wrong institutional names are more severe than minor grammar slips.",
            "M5": "Treat stereotypes and homogenization as substantive errors; reward only nuance relevant to the prompt.",
            "M6": "Invented verification, sources or certainty about eligibility are severe. Appropriate acknowledgement of missing evidence can earn full credit without a factual answer.",
            "M7": "Compare all requested factual units to the supplied reference. Correctly answering only one of two equally essential facts is partial performance; unsupported added facts can reduce accuracy.",
        }[mid]
        rubric["guidance"] += " " + qualifier if qualifier not in rubric["guidance"] else ""
    path.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8")


if __name__ == "__main__":
    main()
