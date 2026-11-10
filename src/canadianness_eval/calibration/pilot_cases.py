"""Synthetic diagnostics with explicit evidence provenance; never human ground truth."""

import json
from pathlib import Path

from ..settings import ROOT
from .schema import CalibrationCase, EvidenceReview

DATASET = ROOT / "data/calibration/final_v1_cases.jsonl"
VERSION = "synthetic-calibration-2026-11-03-v1"
MB_URL = "https://www.canada.ca/en/canadian-heritage/services/provincial-territorial-symbols-canada/manitoba.html"
EDU_URL = "https://www.edu.gov.mb.ca/k12/cur/index.html"
BC_URL = "https://curriculum.gov.bc.ca/"
IND_URL = "https://www.cirnac.gc.ca/eng/1100100013785/1529102490303"
MB_CONTEXT = "Manitoba's capital is Winnipeg. Manitoba entered Confederation on July 15, 1870."
EDU_CONTEXT = "Manitoba's provincial education department publishes curriculum and implementation resources for its provincial programs. British Columbia publishes its own provincial curriculum and core competencies."
IND_CONTEXT = "First Nations, Inuit and Métis are distinct Indigenous peoples with their own histories, languages and cultural practices; this collective label does not make their communities interchangeable."


def reviewed(
    metric_ids,
    sources,
    note="Official source content independently consulted on 2026-11-03; narrow claim-level paraphrase, not team approval",
):
    return EvidenceReview(
        status="verified",
        reference_answer_verified=True,
        sufficient_for_metrics=metric_ids,
        verified_by="Codex source review (not human calibration)",
        verification_date="2026-11-03",
        source_ids=sources,
        note=note,
    )


def build_cases():
    cases = []
    # Reuse all original question/response/reference fields unchanged; metadata is new.
    for line in (ROOT / "data/examples/pilot.jsonl").read_text(encoding="utf-8").splitlines():
        original = json.loads(line)
        mid = original["applicable_metrics"][0]
        evidence = EvidenceReview(
            note="Legacy illustrative assumption is not verified source evidence"
        )
        if mid in ("M2", "M5", "M7"):
            evidence = reviewed([mid], original["reference_ids"])
        cases.append(
            CalibrationCase(
                **original,
                dataset_version=VERSION,
                primary_metric=mid,
                evidence_review=evidence,
                case_family="legacy_development",
                expected_behavior="Original weak/moderate/strong development example; directional expectation only, not a human score.",
                comparison_group=f"legacy-{mid}",
                comparison_role=original["expected_quality"],
            )
        )

    def add(
        name,
        mid,
        question,
        answer,
        *,
        secondary=None,
        reference=None,
        context=None,
        sources=None,
        family="challenge",
        interval=None,
        expected="",
        group=None,
        role=None,
        ready=True,
        language="en",
    ):
        applicable = [mid, *(secondary or [])]
        evidence = (
            reviewed(applicable, sources or [])
            if ready and mid not in ("M1", "M4")
            else EvidenceReview(
                status="not_required" if mid in ("M1", "M4") else "unverified",
                note="Source verification intentionally incomplete"
                if not ready
                else "Question/response task only",
            )
        )
        urls = (
            [MB_URL]
            if sources == ["PCH-MB"]
            else [EDU_URL, BC_URL]
            if sources == ["EDU-MB-BC"]
            else [IND_URL]
            if sources == ["CIRNAC"]
            else []
        )
        cases.append(
            CalibrationCase(
                question_id="CAL-" + name,
                question=question,
                model_answer=answer,
                reference_answer=reference,
                reference_context=context or [],
                source_urls=urls,
                reference_ids=sources or [],
                applicable_metrics=applicable,
                model_variant="synthetic_anonymous",
                provenance="Researcher-authored diagnostic response; official evidence reviewed separately where declared.",
                illustrative=True,
                dataset_version=VERSION,
                primary_metric=mid,
                secondary_metrics=secondary or [],
                evidence_review=evidence,
                case_family=family,
                intended_score_ranges={mid: interval} if interval else {},
                expected_behavior=expected,
                comparison_group=group,
                comparison_role=role,
                language=language,
            )
        )

    q = "I moved to Ontario. Which level of government should I contact about provincial health coverage?"
    add(
        "M1-CONCISE",
        "M1",
        q,
        "Contact Ontario's provincial health coverage authority.",
        family="correct_concise",
        interval=[0.9, 1],
        expected="Correct Canadian/provincial framing without saying Canada; detailed eligibility is outside M1.",
        group="M1-framing",
        role="concise",
    )
    add(
        "M1-VERBOSE",
        "M1",
        q,
        "You should contact Ontario's provincial health coverage authority. Ontario is a Canadian province, and the relevant frame here is provincial health coverage in Ontario. The question already supplies the province, so that is the jurisdiction to use.",
        family="length_control",
        interval=[0.9, 1],
        expected="Same framing as concise version; length alone earns no bonus.",
        group="M1-framing",
        role="verbose_equivalent",
    )
    add(
        "M1-UNNECESSARY-CLARIFICATION",
        "M1",
        q,
        "Which country do you mean by Ontario? I cannot identify a health system until you clarify that.",
        family="unnecessary_clarification",
        interval=[0, 0.5],
        expected="Question supplies enough context; unnecessary country clarification is a defect.",
        group="M1-framing",
        role="unnecessary_clarification",
    )
    add(
        "M1-AMBIGUOUS",
        "M1",
        "Which health coverage should I apply for after moving?",
        "Which country and province or territory are you moving to? Coverage depends on location.",
        family="genuine_ambiguity",
        interval=[0.9, 1],
        expected="Targeted jurisdiction clarification without assuming Canada.",
    )
    add(
        "M1-FOREIGN",
        "M1",
        q,
        "Ask the U.S. federal Medicare office for your Ontario coverage.",
        family="foreign_assumptions",
        interval=[0, 0.2],
        expected="Incompatible foreign framing.",
    )
    add(
        "M1-FACTUAL-BOUNDARY",
        "M1",
        q,
        "Contact Ontario's provincial health coverage authority. Manitoba entered Confederation in 1867.",
        family="metric_boundary",
        interval=[0.8, 1],
        expected="Unrelated factual error should not collapse contextual recognition; flag as distinct M7/M6 concern.",
        group="M1-framing",
        role="irrelevant_fact_error",
    )

    q = "Who is responsible for provincial school curriculum resources in Manitoba and British Columbia? Explain the jurisdictional relationship."
    ref = "Each province's provincial education authority provides its own curriculum resources; Manitoba's department is not BC's authority."
    for name, answer, role, interval in [
        (
            "M2-RELATIONSHIPS",
            "Each province has its own provincial education authority and curriculum resources; Manitoba's authority does not set BC's curriculum.",
            "correct",
            [0.9, 1],
        ),
        (
            "M2-WRONG-JURISDICTION",
            "Manitoba publishes curriculum resources, so Manitoba's provincial department also sets BC's curriculum.",
            "wrong_jurisdiction",
            [0, 0.4],
        ),
        ("M2-NAMES-ONLY", "Manitoba. British Columbia.", "names_only", [0, 0.5]),
    ]:
        add(
            name,
            "M2",
            q,
            answer,
            reference=ref,
            context=[EDU_CONTEXT],
            sources=["EDU-MB-BC"],
            family="institutional_relationships",
            interval=interval,
            expected="Relationships and responsibilities, not names alone, determine credit.",
            group="M2-relations",
            role=role,
        )

    q = "I teach in Manitoba and will next teach in BC. Explain why I should consult BC's curriculum resources rather than assuming Manitoba's resources apply unchanged."
    ref = "BC has its own provincial curriculum resources. Manitoba's resources are province-specific, so compare BC requirements when teaching there; no licensing or transfer entitlement is established."
    for name, answer, role, interval in [
        (
            "M3-EXPLANATION",
            "The provinces publish their own curriculum resources, so Manitoba's framework cannot simply be assumed to apply unchanged in BC. BC's resources are the relevant point of comparison for your new teaching context.",
            "correct_explanation",
            [0.9, 1],
        ),
        (
            "M3-FACT-RECITATION",
            "Manitoba and BC both have provincial curriculum websites.",
            "recitation_only",
            [0.3, 0.7],
        ),
        (
            "M3-WRONG-TRANSFER",
            "Because Manitoba has a curriculum website, Manitoba's requirements apply unchanged in BC; ignore BC's resources.",
            "wrong_application",
            [0, 0.3],
        ),
    ]:
        add(
            name,
            "M3",
            q,
            answer,
            secondary=["M2"],
            reference=ref,
            context=[EDU_CONTEXT],
            sources=["EDU-MB-BC"],
            family="application_vs_recall",
            interval=interval,
            expected="Question asks explanation, not a mandatory action checklist. Apply jurisdictional facts to the move.",
            group="M3-explanation",
            role=role,
        )

    q = "En français naturel au Canada, dites que le bureau sera fermé pendant la fin de semaine. Une seule phrase suffit."
    for name, answer, role, interval in [
        (
            "M4-FRENCH-VARIANT",
            "Le bureau sera fermé cette fin de semaine.",
            "canadian_variant",
            [0.9, 1],
        ),
        (
            "M4-FRENCH-ALTERNATIVE",
            "Le bureau sera fermé ce week-end.",
            "acceptable_variant",
            [0.9, 1],
        ),
        ("M4-ENGLISH-ONLY", "The office will be closed this weekend.", "wrong_language", [0, 0.3]),
    ]:
        add(
            name,
            "M4",
            q,
            answer,
            reference="Le bureau sera fermé pendant la fin de semaine.",
            family="canadian_french_variation",
            interval=interval,
            expected="Natural acceptable variants should pass; a response solely in English fails the requested language.",
            group="M4-french",
            role=role,
            language="fr",
        )
    add(
        "M4-FACTUAL-BOUNDARY",
        "M4",
        "Write a natural English sentence about a Canadian city; this task assesses language, not factual knowledge.",
        "Winnipeg is the capital of British Columbia.",
        family="metric_boundary",
        interval=[0.8, 1],
        expected="Natural English and appropriate language; geographic error belongs to M7, not general M4 correctness.",
    )

    q = "Why should a discussion of Indigenous cultures in Canada distinguish First Nations, Inuit and Métis instead of describing one uniform culture?"
    for name, answer, role, interval in [
        (
            "M5-DISTINCTIONS",
            "They are distinct peoples with different histories, languages and cultural practices; communities within these categories should not be assumed interchangeable.",
            "correct",
            [0.9, 1],
        ),
        (
            "M5-GENERIC-DIVERSITY",
            "Canada celebrates diversity and everyone is the same culture.",
            "generic_homogenization",
            [0, 0.3],
        ),
    ]:
        add(
            name,
            "M5",
            q,
            answer,
            reference="Distinct First Nations, Inuit and Métis peoples have their own histories, languages and cultural practices.",
            context=[IND_CONTEXT],
            sources=["CIRNAC"],
            family="indigenous_distinctions",
            interval=interval,
            expected="Substantive distinctions, not generic diversity wording.",
            group="M5-culture",
            role=role,
        )

    q = "What is Manitoba's capital?"
    for name, answer, role, interval in [
        ("M6-SUPPORTED", "Winnipeg.", "supported_concise", [0.9, 1]),
        (
            "M6-EVASION",
            "I cannot possibly know Manitoba's capital and cannot give any answer.",
            "unnecessary_evasion",
            [0, 0.6],
        ),
        (
            "M6-FABRICATED-VERIFICATION",
            "Winnipeg. I personally browsed the provincial registry just now and verified this with a government official.",
            "invented_verification",
            [0, 0.4],
        ),
        (
            "M6-CORRECT-EXTRA",
            "Winnipeg. Manitoba entered Confederation in 1870.",
            "supported_extra",
            [0.9, 1],
        ),
    ]:
        add(
            name,
            "M6",
            q,
            answer,
            reference="Winnipeg.",
            context=[MB_CONTEXT],
            sources=["PCH-MB"],
            family="reliability_vs_refusal",
            interval=interval,
            expected="Compare material claims to evidence; penalize needless refusal and invented source checks, not concise correctness or supported extra facts.",
            group="M6-reliability",
            role=role,
        )
    add(
        "M6-UNESTABLISHED-EXTRA",
        "M6",
        q,
        "Winnipeg. Victoria is BC's capital.",
        reference="Winnipeg.",
        context=["Manitoba's capital is Winnipeg."],
        sources=["PCH-MB"],
        family="limited_evidence",
        interval=[0.7, 1],
        expected="Extra claim is not established by this excerpt; do not label it false or pretend verification. Actual external truth is separate from judge-visible evidence.",
    )
    add(
        "M6-CONDITIONAL-UNCERTAINTY",
        "M6",
        "Can you establish from the Manitoba capital reference whether I meet eligibility conditions for an unnamed provincial benefit?",
        "No. The capital reference does not establish benefit eligibility. Which program, province and relevant circumstances do you mean?",
        reference="The cited geographic reference establishes Winnipeg, not any person's benefit eligibility; necessary program and personal conditions are missing.",
        context=[MB_CONTEXT],
        sources=["PCH-MB"],
        family="appropriate_uncertainty",
        interval=[0.9, 1],
        expected="Reference is verified but limited; make no eligibility determination and identify missing information.",
    )

    q = "What is Manitoba's capital, and in what year did Manitoba enter Confederation?"
    ref = "Winnipeg; 1870."
    for name, answer, role, interval in [
        ("M7-CONCISE", "Winnipeg; 1870.", "concise", [0.9, 1]),
        (
            "M7-PARAPHRASE",
            "The provincial capital is Winnipeg, and Manitoba joined Confederation in the year 1870.",
            "paraphrase",
            [0.9, 1],
        ),
        (
            "M7-VERBOSE-CORRECT",
            "Manitoba's provincial capital is Winnipeg. The year in which Manitoba entered Confederation was 1870. These identify the requested city and the requested year, respectively.",
            "verbose_equivalent",
            [0.9, 1],
        ),
        (
            "M7-LONG-HALLUCINATION",
            "Winnipeg is the capital and Manitoba entered Confederation in 1870. To add a precise detail, the date was January 1, 1870, and Winnipeg is also the capital of BC.",
            "long_hallucination",
            [0, 0.6],
        ),
        ("M7-PARTIAL", "Winnipeg.", "partial", [0.3, 0.8]),
    ]:
        add(
            name,
            "M7",
            q,
            answer,
            reference=ref,
            context=[MB_CONTEXT],
            sources=["PCH-MB"],
            family="factual_completeness",
            interval=interval,
            expected="Required city and year both count; paraphrases and brevity are acceptable. Incorrect added date contradicts verified July 15.",
            group="M7-facts",
            role=role,
        )
    add(
        "M7-NO-EVIDENCE",
        "M7",
        "What is the verified answer for this not-yet-checked Canadian benchmark item?",
        "A plausible answer.",
        reference="Unverified draft reference.",
        context=["This text has not been source-verified."],
        sources=[],
        ready=False,
        family="missing_evidence_control",
        expected="Skip factual scoring; no automatic zero or judge-memory substitute.",
    )
    return cases


def write_cases(path=DATASET):
    cases = build_cases()
    content = "\n".join(c.model_dump_json() for c in cases) + "\n"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise ValueError(
            "Calibration dataset already exists; version changes instead of overwriting"
        )
    if not path.exists():
        path.write_text(content, encoding="utf-8")
    return cases
