# Proposed general-answer G-Eval metrics — correctness and completeness

**Status:** PROPOSED, not approved for execution. No new judge calls or scoring runs were made.
**Version:** `2026-11-07-proposed-v1`  
**Metric-definitions SHA-256:** `a92693de355475a2a061442e6268345fcf8f938c16cc9478bfb023566e05f1a2`  
**Source:** Four user-provided G-Eval candidates for each metric, preserved separately in `correctness_completeness_4_candidates_each.xlsx`.

## Design principle

- **Correctness:** factual accuracy of the distinct claims actually made, including relevant additional assertions; do not penalize a partial yet true answer solely for missing information.
- **Completeness:** sufficient coverage of each fact, condition or distinction genuinely required by the question; do not demand optional background.
- A response giving no substantive answer is low on both. An answer containing both a true and a false answer claim can be lower on both because the incorrect claim also undermines coverage.
- Treat reference and Context as judge-side evidence, not necessarily the prompt provided to the model. Equivalent formulations are valid; unsupported is not automatically false.

## Answer Correctness

Accuracy of the distinct substantive factual claims the model actually makes when answering the question. Score factual errors and misleading conclusions, not whether every required item is included.

### Six fixed G-Eval steps

1. Identify the central factual question or decision the Input asks the model to address. Read the Actual Output as the model's answer; disregard wording, length and duplicated text when determining distinct content.
2. Extract each distinct, substantive factual claim in the Actual Output. Separate the central answer or conclusion from relevant supporting or additional claims; count an exactly repeated claim only once.
3. Compare the distinct claims with the Expected Output and Context. Label each as supported/correct, contradicted/incorrect, or not verifiable from the supplied evidence. Accept factually equivalent wording and valid alternative answers; a missing citation or absent evidence is not itself a contradiction.
4. Evaluate whether the central conclusion is factually correct and whether any additional incorrect claims materially mislead. Weight errors by significance; do not automatically assign the lowest score for one minor ancillary error.
5. Assess qualifications, uncertainty, refusals and clarification requests against the Input and evidence. Give credit when uncertainty or abstention is warranted; an off-topic reply, empty refusal or response that merely restates the question without giving any factual answer is a non-answer. If the reference and Context conflict, flag the limitation rather than inventing a resolution.
6. Select the 0–10 correctness band using the accuracy and impact of factual claims, not how many required items were supplied. Explain the decisive correct and incorrect claims and flag unresolved evidence. Do not penalize omissions, optional detail, style, language choice or repetition under this metric.

### Five scoring bands

| Raw score | Outcome |
|---|---|
| **0–2** | The central answer is false or contradicted and little or no relevant factual substance is correct; or the response is off-topic, content-free, unjustifiably refuses an answerable question, or merely repeats the question's premise without supplying any answer. A decisive error or absence of a substantive answer makes the response fundamentally wrong. |
| **3–4** | The response contains meaningful correct information but also a materially false central claim, required factual condition or conclusion. The mixture of correct and incorrect content makes its substantive answer unreliable. |
| **5–6** | The central answer is largely correct, but one or more identifiable factual errors, misleading qualifications or consequential mistakes in supporting details weaken its reliability without overturning the main answer. |
| **7–8** | The central answer is correct and no material falsehood changes its meaning. Any remaining problems are minor factual imprecision or noncritical ancillary inaccuracies; valid equivalents and appropriate qualifications receive credit. |
| **9–10** | Every distinct material claim that can be verified is factually correct and the response contains no misleading contradictory statements. A concise answer, valid alternative or justified uncertainty can receive full credit; omitted required information is scored only by Completeness. |

**Metric boundary:** Omissions and required-element coverage belong to Answer Completeness. Correct optional facts count for factual accuracy; incorrect extra facts can reduce correctness. Repetition is deduplicated analytically, not rewarded or penalized.

## Answer Completeness

Coverage of the minimum information genuinely required to answer the question, including all core elements and necessary qualifications. Do not reward optional background or verbosity.

### Six fixed G-Eval steps

1. Determine the minimum set of information required to satisfy the Input, before examining how much the Actual Output says. Use the Expected Output and Context as evidence; separate core requested elements and genuinely necessary conditions/qualifications from optional background, examples and reference elaboration.
2. For every required element, identify whether the Actual Output conveys it fully, partially or not at all. Accept concise semantic equivalents, alternative correct formulations and the requested degree of specificity; mere term mentions or factually contradictory statements do not establish coverage.
3. For multi-part, list, conditional, comparison and time- or jurisdiction-specific questions, check each independently required part and any qualifier necessary to avoid changing the answer's meaning. Do not invent requirements not implied by the Input.
4. Assess omissions by their importance to satisfying the question: missing a core element matters more than missing a minor necessary detail. If extra claims are unrelated to the required answer elements, leave their correctness to the Correctness metric; do not reward or penalize optional elaboration.
5. Consider whether an appropriately qualified answer, clarification or abstention fully meets a genuinely ambiguous or unanswerable question. Flag missing, outdated or conflicting reference evidence and do not fabricate answer requirements or assume Context was provided to the tested model.
6. Select the 0–10 completeness band from the coverage of required elements and explain the specific items covered, partial or missing. Ignore answer length, repetition, copied phrasing and stylistic differences; a brief answer can earn full credit when it is sufficient.

### Five scoring bands

| Raw score | Outcome |
|---|---|
| **0–2** | None, or almost none, of the essential information requested by the question is meaningfully covered. The answer is generic, unrelated, unjustifiably refuses an answerable question or omits essentially the whole substantive answer. |
| **3–4** | Some required information is present, but one or more major core elements are entirely absent or inadequately conveyed. The answer is fragmentary and fails to satisfy a substantial part of the question. |
| **5–6** | The main request is substantially addressed, but a core element is only partially covered or an important necessary condition, distinction or qualification is missing. The answer is useful yet materially incomplete. |
| **7–8** | All core requested elements are covered and the answer meets the principal information need. Only small gaps in genuinely necessary supporting details or minor qualifications remain; optional background is not required. |
| **9–10** | Every core requested element and necessary qualification is sufficiently covered, including any required parts, scope, timing or distinctions. Correct concise equivalents receive full credit; optional examples, length and elaboration are not required. |

**Metric boundary:** Distinct claims unrelated to required elements do not lower completeness, even if wrong; correctness assesses them. A wrong or self-contradictory statement of a required element does not count as adequate coverage.

## Common scoring rules

- The same fixed definitions, scoring bands, judge model/configuration, input fields, normalization and logging must apply to Llama, GC LLM and Apertus.
- Use judge-side Input, Actual Output, Expected Output and Context. Context is evidence for evaluation, not proof that the tested model saw it.
- Unverified is not the same as false. If supplied evidence is inadequate to adjudicate a material claim, flag it for evidence/human review instead of inventing certainty.
- Neither metric measures repetition, truncation, fluency, response length or general instruction-following as an independent quality defect; retain those as separate diagnostics.
- Score on a 0–10 rubric. Normalize raw 0–10 results to 0–1 once; if the scorer already returns 0–1, never divide by 10 again. Do not blend these two scores into the existing seven Canadian-ness metrics.
- An original and a repetition-cleaned response are distinct experimental conditions; never replace the former and never revise the reference answer to favor a model.
- Select a lower integer within the band for more severe problems and a higher integer for milder problems; score 10 is allowed for a minimal sufficient answer.
- A material contradiction between Expected Output and Context, or an uncheckable decisive claim, should be flagged for evidence review; do not present the numeric judgment as independently verified ground truth.

## Source-candidate synthesis

| Metric | Candidate | Retained | Corrected |
|---|---:|---|---|
| Correctness | 1 | Keep distinct claim labels; treat unverified separately from false. | Remove omission penalties and any requirement to include optional details for a perfect correctness score. |
| Correctness | 2 | Keep on-topic/non-answer check and recognition of justified abstention. | Remove the automatic lowest-band rule for any single false claim; weight its significance. |
| Correctness | 3 | Keep central vs ancillary error severity, semantic equivalence, and evidence limitations. | Avoid vague 'comprehensive' requirements in a factual accuracy metric. |
| Correctness | 4 | Keep reference/context conflict handling and caution about unsupported claims. | Avoid requiring that every additional claim be explicitly documented in Context to earn top scores. |
| Completeness | 1 | Keep independent question-driven required-element extraction and full/partial/missing coverage. | Do not require optional background, nor force all-core-covered answers into 5-6 for unneeded details. |
| Completeness | 2 | Keep separation of core/required details and semantic equivalence. | Remove 'secondary = optional' ambiguity and correctness/style issues from coverage bands. |
| Completeness | 3 | Keep concise per-element coverage evidence and unambiguous scoring rationale. | Remove absolute 'at most one core element' phrasing, which fails when a question has only one core element. |
| Completeness | 4 | Keep importance-weighted omissions and clear band boundaries. | Avoid a rigid single-partial-element cap unrelated to that element's significance. |

## Illustrative calibration cases (not model results)

| Case | Input | Example response | Correctness | Completeness |
|---|---|---|---|---|
| Two official languages | What are Canada's two official languages? | English and French. | 9–10 | 9–10 |
| Correct but incomplete | What are Canada's two official languages? | English. | 9–10 | 3–4 |
| Extra false statement | What are Canada's two official languages? | English and French. Ottawa is in Quebec. | 5–6 | 9–10 |
| Mixed factual response | What are Canada's two official languages? | English and Spanish. | 3–4 | 3–4 |
| True but avoids request | What are Canada's two official languages? | Canada has two official languages. | 0–2 | 0–2 |
| Concise complete answer | How many provinces and territories are there in Canada? | 10 provinces and 3 territories. | 9–10 | 9–10 |
| One required part missing | How many provinces and territories are there in Canada? | 10 provinces. | 9–10 | 3–4 |
| Repeated answer | What are Canada's two official languages? | English and French. English and French. | 9–10 | 9–10 |
| Ambiguous input | Which address is closer? | Please provide both addresses and the starting point. | 9–10 | 9–10 |

These are **proposed anchor bands**, not human-validated labels. Confirm with a human-reviewed, bilingual, diverse calibration sample before locking a full run.

## Integration boundary

- Use the existing `final-json-factory-v2`-style fixed-step evaluation pipeline and explicitly supply `evaluation_steps` rather than asking G-Eval to regenerate them per run.
- In current DeepEval documentation, `evaluation_steps` and `criteria` are alternatives when constructing G-Eval; use only the fixed steps for the actual runtime call, with `Rubric` bands `(0,2)`, `(3,4)`, `(5,6)`, `(7,8)`, `(9,10)`.
- Evaluation parameters: `INPUT`, `ACTUAL_OUTPUT`, `EXPECTED_OUTPUT`, `CONTEXT`. Use one identical metric definition per model and separate score/checkpoint outputs.
- Await user approval of these proposed definitions. Do not start the new 4,536-task experiment based on this file alone.
