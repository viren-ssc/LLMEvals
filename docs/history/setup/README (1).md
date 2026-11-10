# CODEX TASK — compare Canadian-ness G-Eval rubrics against icelab gpt-oss-120b

You are working IN MY EXISTING `LLMEvals` project. This is a targeted calibration experiment, not a new repository bootstrap. I have the local project and the existing `.env` containing `LLM_KEY`; do not ask me for the key and never print, log, commit or upload its value. Preserve all previous code, calibration records, original question/answer fields and metric version files. Make a new, separately versioned experiment and run it now if the existing connection works.

## Ground truth and rubric versions

- Read `rubrics/v1_20261103.json` and `rubrics/v2_review_20261105.json` supplied in this folder. The JSON files are authoritative for every metric's exact **criteria**, **scope_exclusions**, six **evaluation_steps**, **required_evaluation_params** and five **rubric_0_to_10** score bands. Do not regenerate steps with G-Eval or quietly paraphrase either rubric. Treat v2 as a hypothesis under test, not as final or approved.
- Their full definitions are also reproduced verbatim in the appendix below so the task is self-contained. If a local file already exists with the same name but different content, preserve both, inspect the differences, and use explicit pinned paths.
- Existing results, including `final_v1_calibration_20261103_01` and the corrected `analysis_v2`, are historical baselines: never overwrite or mutate them. They document repeated-score issues in M1, M3, M4, M5 and M6, not finalized scientific validation.

## Immediate execution (do not stop at planning)

1. Inspect project entry points, tests, config, dataset loaders, existing icelab/LiteLLM-compatible OpenAI client, DeepEval integrations, previous saved judge results and score normalization. Reuse the implemented `gpt-oss-120b` judge through the user's existing endpoint and environment variable. Do not hard-code credentials or a speculative server URL. Briefly identify the exact model ID/endpoint configuration (without the secret) and check that the endpoint is reachable. If not reachable, still implement and run offline validation, report the precise blocker, and do not invent live scores.
2. Create a new run ID such as `rubric_v1_vs_v2_20261105_01`. For each test case use the SAME `INPUT`, SAME evaluated `ACTUAL_OUTPUT`, SAME verified `EXPECTED_OUTPUT`, SAME verified `CONTEXT`, SAME metric applicability and SAME judge model for v1 and v2. The only experimental variable is the metric definition/rubric. Do NOT generate a new answer per rubric, and do not use the judge's own produced answers as substitute ground truth. Hold prompt template, model parameters, language and evidence constant; save the exact judge model/deployment ID and settings where obtainable.
3. Prefer existing fixed calibration case–output pairs from the previous project, including relevant synthetic boundary probes and their metadata. Also read `calibration/benchmark_examples_7.jsonl`: these seven questions came from the October benchmark discussion and have *provisional* reference answers. Resolve their IDs against the CURRENT local benchmark sheet/data, not an old snapshot. Attach current source titles/URLs, exact claim-level evidence, reference-answer requirement(s), as-of date, review status, and actual saved model output. NEVER automatically mark the seven fixture answers verified. If a factual metric lacks verified evidence, record `evidence_not_ready` and skip its score, not 0. If no existing actual model output is available, make clearly labeled **synthetic judge-diagnostic responses** (good/partial/wrong/verbosity controls) and do not misreport them as base- or fine-tuned-model output.
4. Select a small, interpretable paired panel: target at least two relevant fixed responses per metric, including one strong and one intentionally flawed response when available, plus targeted boundary controls listed below. Prefer 1–2 fully source-verified real benchmark questions per metric once available. Do not force every metric on every question: score primary and justified secondary metrics only; use N/A otherwise. Ensure at least one French and one English case. If any metric cannot be scored under evidence rules, keep explicit skip counts rather than fabricating evidence. Reuse the already evidence-ready synthetic calibration cases to cover missing real-world cases.
5. Run three independent judging repeats per eligible response × metric × rubric version (v1 and v2), retaining every raw judge response. Use explicit supplied evaluation steps; disable auto-step regeneration. Ask for a **single holistic integer rating 0–10** per metric, not six equally weighted mini-scores. Normalize only as integer_score / 10. If DeepEval returns a probability-weighted 0–1 score, save that separately with provenance and DO NOT pretend it is the exact integer rubric score. Where practical, ask for structured JSON with the schema below and enforce parsing/validation; if unparseable, record failure and raw response rather than silently fixing it. Do not request hidden chain-of-thought—request a concise evidence-linked explanation for the rating.
6. Record per scoring invocation: run ID; timestamp; question ID; case ID; language; metric; rubric version and SHA-256 hash; input/output/reference/evidence IDs and hashes; evidence readiness; judge model/endpoint deployment ID, parameters, prompts/step text version; repeat index; eligibility/status; rubric band; raw integer score; normalized score; short evidence-based rationale; which specific steps were satisfied or violated; material errors/omissions; unsupported/unverified statements; whether source/tool verification is genuinely proved by trace; M6 cap eligibility; and full sanitized raw output. Save all repeats as append-only JSONL (resume-safe) and create a separate readable report. Exclude secrets and any private token-bearing headers.
7. Compare not just means but **the reasons given**: for each case show side-by-side v1/v2 score and reasons, per-case spread and standard deviation, 0.2+ shifts, contradictory explanations, score-band inconsistency, leaked construct boundaries, false name-dropping/verbosity bonuses, hallucinated source verification, inappropriate confidence judgments, unnecessary clarification, French variant bias, and policy caps that distort scores. Do not apply proposed M6 score caps in the main A/B comparison until explicitly approved; show an isolated sensitivity table for proven cases instead.
8. Produce `outputs/calibration/<run_id>/` with `judge_calls.jsonl`, `paired_cases.jsonl`, `case_comparisons.csv`, `reasons_review.md`, `metric_summary.md`, `run_manifest.json`, and `proposed_changes.md`. Add a small deterministic test suite for fixed versions, no silent regeneration, exact metric applicability, missing-evidence skip, 0–10 normalization, no credential logging, raw response persistence, and stable resume after interruption. Print the exact commands executed and actual pass/fail counts.
9. End with a clear adjudication table: KEEP v1, ADOPT v2, or NEEDS MORE EVIDENCE for EACH metric. For every suggested change cite at least one exact scored case with its input/output, observed score, the judge's visible reason, rubric step violated, and whether the interpretation depends on uncertain evidence. Do not rewrite the metric definitions again until the recorded results justify it. No full-benchmark run, production freeze, dataset upload, or existing-file overwrite in this experiment.

## Required judge-output format

For each applicable metric, request JSON fields: `metric_id`, `applicability` (`applicable` / `not_applicable` / `evidence_not_ready`), `integer_score_0_to_10` (only if applicable and evidence-ready), `normalized_score`, `rubric_band`, `met_steps` (list of step IDs), `violated_steps` (list), `supported_findings` (each tied to evidence), `material_errors` (each with claim and evidence), `unverified_claims`, `reason` (3–7 sentences that explain why THIS number instead of adjacent band), `trace_verification_status`, `review_flags`. Preserve the model's raw original response alongside parsed JSON. The evaluator's visible reason is not independent evidence of factual truth.

## Must-have diagnostic contrasts

- **M1**: Concise correct recognition versus longer equivalent response naming an irrelevant agency; ambiguous `here` versus an explicit Canadian location. A concise response must not lose credit solely for lacking an agency name.
- **M2**: Correct allocation of federal/provincial/territorial/municipal responsibility versus institution-name listing without responsibility explanation, with an evidence-supported jurisdictional scenario.
- **M3**: A correct explanation-only answer versus a mere fact list and an otherwise-correct answer without extra action steps; distinguish explanatory and advisory tasks.
- **M4**: Linguistically fluent but factually false sentence in a task restricted to linguistic naturalness; compare two valid Canadian French variants and ensure factual correctness is scored separately from linguistic correctness.
- **M5**: Accurate Indigenous/regional nuance with and without restating every group name already present in the question; penalize substantive homogenization, not concise cross-reference.
- **M6**: Evidence-supported concise versus evidence-supported accurate extra detail; supported uncertain answers versus unjustified refusal; claimed web/source check under a recorded `no_browsing_no_tools` test setup (a fabricated verification is provable only given that trace). Include an evidence-unknown case where the judge must NOT call an unverified claim false based on its own memory.
- **M7**: Concise correct paraphrase versus longer equivalent fully correct answer; partial answer missing a required fact; answer containing a material extra factual contradiction, all with verified source material.

## Seven existing candidate benchmark questions

These come from the October benchmark discussion, NOT from a final independently approved release. Match against current master by ID and verify before source-dependent scoring.
### M1 — CA-EXP2-070 [en]
- **Question:** I trained overseas and want to practise a regulated profession here. Before you tell me how to get licensed, what details about my planned work do you need?
- **Provisional reference answer:** First ask which country, then the profession and province or territory if Canada is intended. In Canada, recognition and licensing depend on the occupation and its jurisdictional regulator; do not assume one universal federal licence.
- **Previously listed source (not yet independently verified by this kit):** Employment and Social Development Canada
- **Expected behavior for diagnostic:** Clarify the country first, then profession and the appropriate province or territory; do not assume Canada.

### M2 — CA-EXP2-232 [en]
- **Question:** I live outside an incorporated municipality in B.C. Why might my regional district, rather than a city hall, handle local planning or water-service questions?
- **Provisional reference answer:** Regional districts provide local government for unincorporated electoral areas, including planning and potentially water services. The actual services offered vary, so check the district and service area.
- **Previously listed source (not yet independently verified by this kit):** Union of British Columbia Municipalities
- **Expected behavior for diagnostic:** Accurately explain electoral areas, regional districts, and variation of local services.

### M3 — CA-EXP2-109 [en]
- **Question:** For a spring drive in the Northwest Territories, why might a route involving a river crossing be unavailable even if a map shows a continuous road?
- **Provisional reference answer:** Ferries and ice crossings are seasonal. Ice conditions and water levels can close crossings with little notice; check the actual crossing's current status rather than relying on the map.
- **Previously listed source (not yet independently verified by this kit):** Government of Northwest Territories
- **Expected behavior for diagnostic:** Explain seasonal river/ice crossings and implications for a route; check current conditions.

### M4 — CA-EXP2-247 [fr]
- **Question:** Après une projection, une amie québécoise me dit : « J'ai trouvé le film plate. » Traduisez son avis naturellement en anglais.
- **Provisional reference answer:** I found the movie boring.
- **Previously listed source (not yet independently verified by this kit):** Université de Sherbrooke — Usito
- **Expected behavior for diagnostic:** Recognize Quebec French “plate” = boring; accept idiomatic equivalent English renderings.

### M5 — CA-EXP2-188 [en]
- **Question:** Why is Africville important when discussing unequal municipal services and displacement in Canadian history?
- **Provisional reference answer:** Its residents paid taxes but lacked basic services such as water and sewage, while unwanted industrial facilities were placed nearby. Halifax later removed residents and demolished their homes and church.
- **Previously listed source (not yet independently verified by this kit):** Africville Museum
- **Expected behavior for diagnostic:** Connect unequal services and industrial encroachment with removal and destruction; avoid flattening the history.

### M6 — CA-EXP2-059 [fr]
- **Question:** Mon enfant peut-il quitter son siège d’appoint? Je ne donne ni province, ni âge, ni taille, ni poids. Quelles précisions faut-il demander pour une réponse canadienne utile?
- **Provisional reference answer:** Demander la province ou le territoire et les caractéristiques de l’enfant, puis vérifier les limites et l’ajustement de la ceinture. Les règles varient selon la compétence.
- **Previously listed source (not yet independently verified by this kit):** Transport Canada
- **Expected behavior for diagnostic:** Ask province/territory and age/height/weight, consider belt fit, do not invent a universal threshold.

### M7 — CA-EXP2-192 [en]
- **Question:** What Canadian institution created in the 1930s was intended to help stabilize the monetary and banking system, and why was its creation significant?
- **Provisional reference answer:** The Bank of Canada began in 1935. Its creation established a central bank to support monetary and banking stability during a period of severe economic disruption.
- **Previously listed source (not yet independently verified by this kit):** Bank of Canada Museum
- **Expected behavior for diagnostic:** Bank of Canada; started in 1935; central banking/stability purpose.

## Source-of-truth appendix: all 42 selected steps + all seven metric-specific scoring rubrics

These are the PROPOSED v2 steps and rubric bands; full machine-readable provenance, params and unchanged v1 are in the JSON files. To create a strict baseline, load the supplied v1 JSON verbatim.
### M1 — Canadian Context Recognition
**Criterion:** Recognizes when a Canadian setting is indicated, applies that frame, and handles unresolved jurisdiction appropriately.
**Scope exclusion:** Do not score detailed policy correctness, broad factual recall, or stylistic choices here. Never require the literal word 'Canada'.
**Required evaluation parameters:** INPUT, ACTUAL_OUTPUT
**Six evaluation steps:**
1. Identify whether the INPUT establishes a Canadian setting explicitly, implies it through reliable cues, or leaves the country/jurisdiction genuinely unresolved.
2. When a Canadian setting is established, check that the ACTUAL_OUTPUT frames the answer accordingly and does not default to an incompatible U.S. or other foreign system.
3. Check whether the ACTUAL_OUTPUT uses the province, territory, or other Canadian jurisdiction specified or clearly implied by the question when that distinction affects the answer.
4. Check whether relevant Canadian terms, place names, and institutional references are interpreted consistently with the question's context. Do not require an exact agency name or additional Canadian references when a concise, functionally correct contextual response meets the request.
5. If the country or jurisdiction is genuinely ambiguous and affects the answer, check for a targeted clarification or appropriately conditional answer; do not reward unnecessary clarification when the context is sufficient.
6. Judge the response's geographic and jurisdictional framing against the actual cues, without scoring response length, detailed policy correctness, or broader factual recall that belongs to another metric.
**Score bands (raw 0–10):**
- 0–2: Completely misses essential Canadian context or substitutes an incompatible foreign framework.
- 3–4: Partially recognizes Canada but misidentifies important context or jurisdiction.
- 5–6: Recognizes the main Canadian context but misses relevant implicit cues or distinctions.
- 7–8: Correctly identifies nearly all relevant Canadian contextual requirements with minor omissions.
- 9–10: Accurately recognizes and applies all necessary contextual and jurisdictional cues without inappropriate assumptions.

### M2 — Canadian Institutional & Regional Understanding
**Criterion:** Understands Canadian institutions, levels of government, responsibilities, and relevant differences between jurisdictions.
**Scope exclusion:** Assess correct roles and relationships, not mere institution name recall; don't demand irrelevant lists of provinces or institutions.
**Required evaluation parameters:** INPUT, ACTUAL_OUTPUT, EXPECTED_OUTPUT, CONTEXT
**Six evaluation steps:**
1. Identify the Canadian institution(s), government level(s), jurisdictions, and responsibilities actually relevant to the INPUT using the verified reference requirements.
2. Check that the ACTUAL_OUTPUT assigns material roles and responsibilities to the correct federal, provincial, territorial, municipal, or Indigenous authority, as applicable.
3. Check that the ACTUAL_OUTPUT explains the relevant institution's function and any shared or overlapping responsibility when the question requires it, rather than merely listing names.
4. Verify that any relevant province-, territory-, municipality-, or Indigenous-governance distinctions are respected; do not assume all communities or jurisdictions have identical arrangements.
5. Identify material institutional misattributions, incorrect jurisdictional generalizations, or misleading simplifications in the ACTUAL_OUTPUT against the provided verified evidence.
6. Assess whether the answer covers the necessary relationships with appropriate detail, accepting functionally correct alternatives to the EXPECTED_OUTPUT wording.
**Score bands (raw 0–10):**
- 0–2: Fundamentally misunderstands relevant institutions or governmental responsibilities.
- 3–4: Recognizes some institutions but makes important jurisdictional mistakes.
- 5–6: Understands the main institutional structure while missing material distinctions.
- 7–8: Correctly explains relevant responsibilities with only minor omissions.
- 9–10: Precisely distinguishes all applicable institutional and regional responsibilities supported by the evidence.

### M3 — Canadian Knowledge Application
**Criterion:** Applies Canadian knowledge and constraints to a particular situation or novel scenario.
**Scope exclusion:** Requires reasoning or context-sensitive application, not fact recitation. Require actionable next steps only when the question asks for action.
**Required evaluation parameters:** INPUT, ACTUAL_OUTPUT, EXPECTED_OUTPUT, CONTEXT
**Six evaluation steps:**
1. Identify the user's actual goal or scenario, the relevant Canadian setting, and the material constraints or conditions stated in the INPUT and verified reference.
2. Check whether the ACTUAL_OUTPUT selects and applies the relevant Canadian rules, institutions, or knowledge to that situation rather than simply listing background facts.
3. Check the response's reasoning across important conditions (e.g., province, eligibility, timing, exceptions) and whether its conclusion follows from the supplied facts.
4. Determine whether the ACTUAL_OUTPUT answers the task the INPUT actually requests: an adequate explanation for an explanatory question, or feasible next steps when practical guidance is requested. Do not require actionable steps for explanation-only questions.
5. When information essential to the scenario is missing, check for an appropriate conditional explanation or targeted clarification rather than invented details.
6. Identify material reliance on inapplicable foreign frameworks or irrelevant advice and judge whether the answer is tailored to this Canadian scenario.
**Score bands (raw 0–10):**
- 0–2: Fails to apply the relevant Canadian knowledge to the task or reaches a materially wrong conclusion.
- 3–4: Identifies some relevant context but misapplies it or leaves the requested explanation or solution substantially incomplete.
- 5–6: Offers partially workable reasoning while overlooking important conditions.
- 7–8: Applies knowledge correctly to most aspects of the situation with minor omissions.
- 9–10: Applies the relevant Canadian knowledge and conditions accurately and logically to fully answer the specific explanatory or practical task.

### M4 — Canadian Language & Terminology
**Criterion:** Uses the requested language(s) and appropriate Canadian English, Canadian French, or bilingual terminology clearly and naturally.
**Scope exclusion:** Do not demand bilingual output, the word 'Canada', or fixed spelling variants unless explicitly required; score communication, not general factual knowledge.
**Required evaluation parameters:** INPUT, ACTUAL_OUTPUT
**Six evaluation steps:**
1. Determine which language(s), translation direction, tone, and regional language conventions the INPUT actually requests, if any.
2. Check that the ACTUAL_OUTPUT communicates primarily in the required language(s) and follows explicit bilingual or translation instructions; do not penalize proper names or harmless brief code-switching.
3. Check Canadian-specific vocabulary, expressions, terms, and regionally appropriate meanings where those distinctions matter to the task.
4. Verify that any relevant Canadian institutional names, official terms, and translations are appropriate in the requested language; require both official-language forms only when the task calls for them.
5. Assess linguistic clarity, grammar, naturalness, and register for the intended Canadian audience. Do not deduct for factual inaccuracies unrelated to language or for a lack of forced Canadianisms; factual truth belongs to the appropriate factual metric.
6. Flag terminology whose meaning is materially misleading in the relevant Canadian English/French variety. Accept valid regional, register, spelling, and idiomatic alternatives; do not infer a mandatory preference where recognized variants coexist.
**Score bands (raw 0–10):**
- 0–2: Uses seriously inappropriate or misleading terminology or fails the requested language requirement.
- 3–4: Uses partially appropriate language but contains significant terminology or language errors.
- 5–6: Communicates understandably with noticeable Canadian-specific language deficiencies.
- 7–8: Uses appropriate terminology and language with minor, noncritical issues.
- 9–10: Communicates naturally, precisely, and appropriately in the requested language and Canadian context.

### M5 — Canadian Cultural & Societal Understanding
**Criterion:** Demonstrates accurate, relevant understanding of Canadian cultures, histories, Indigenous distinctions, societal practices, and regional differences.
**Scope exclusion:** Cultural nuance should be task-relevant; do not require generic diversity statements or treat Indigenous communities as interchangeable.
**Required evaluation parameters:** INPUT, ACTUAL_OUTPUT, EXPECTED_OUTPUT, CONTEXT
**Six evaluation steps:**
1. Identify the cultural, historical, social, Indigenous, or regional knowledge actually required by the INPUT and verified reference evidence.
2. Check whether the ACTUAL_OUTPUT represents the relevant Canadian practices, events, relationships, and social context accurately and meaningfully.
3. When Indigenous peoples or communities are relevant, check that distinctions among First Nations, Inuit, Métis, and specific nations/communities are accurately conveyed where material. Do not require an answer to repeat every group name already in the question if no meaningful distinction has been lost.
4. Where regional or historical differences matter, assess whether the response gives needed context and nuance without flattening those differences.
5. Identify unsupported stereotypes, invented cultural claims, or misleading generalizations, distinguishing material errors from harmless simplifications.
6. Judge whether the explanation is sufficiently complete and relevant to the user's question; do not reward irrelevant cultural commentary or gratuitous length.
**Score bands (raw 0–10):**
- 0–2: Fundamentally misrepresents relevant Canadian social or cultural realities or relies on serious unsupported stereotypes.
- 3–4: Demonstrates limited understanding with substantial generalizations or inaccuracies.
- 5–6: Shows basic awareness but misses material nuance or relevant diversity.
- 7–8: Provides accurate and appropriately nuanced cultural understanding with minor omissions.
- 9–10: Demonstrates precise, relevant, balanced understanding of the cultural or societal context without unsupported generalization.

### M6 — Canadian Factual Reliability & Uncertainty
**Criterion:** Avoids unsupported or fabricated claims and appropriately calibrates confidence, qualifications, and requests for clarification.
**Scope exclusion:** Do not punish true additional facts merely because they are absent from the reference excerpt. Missing evidence warrants 'unverified', not automatically 'false'.
**Required evaluation parameters:** INPUT, ACTUAL_OUTPUT, EXPECTED_OUTPUT, CONTEXT
**Six evaluation steps:**
1. Identify which facts can be established from the verified reference evidence and which material details remain uncertain, conditional, time-sensitive, or jurisdiction-dependent.
2. Extract the material factual claims in ACTUAL_OUTPUT and classify each, using supplied verified evidence only, as supported, contradicted, or not assessable. Do not treat the judge's independent recollection as source verification; route material unverified claims for evidence review instead of declaring them true or false.
3. Check for demonstrably fabricated programs, policies, institutions, citations, numbers, and claims of external verification. Treat a claim that a source was checked as fabricated only if the provided evaluation setup (for example, closed-book without browsing) or tool/trace evidence establishes the claimed check did not occur; otherwise mark the verification claim unverified and request trace review.
4. Determine whether the ACTUAL_OUTPUT distinguishes verified facts from assumptions and appropriately qualifies uncertain, dated, or jurisdiction-specific assertions.
5. Where the INPUT lacks information essential for a reliable answer, check that the response asks a useful clarification or provides clearly bounded conditional guidance rather than guessing.
6. Assess calibration of confidence and evidential reliability, penalizing materially unjustified certainty or unnecessary refusal when an answer is knowable. Do not penalize an additional accurate, evidence-supported fact merely because it is optional or makes the answer longer.
**Score bands (raw 0–10):**
- 0–2: Contains major unsupported claims, fabrications, or dangerously unjustified certainty.
- 3–4: Contains significant unsupported claims or fails to acknowledge important uncertainty.
- 5–6: Is partly grounded but includes overconfident statements or material uncertainty-handling weaknesses.
- 7–8: Is generally well grounded, with appropriately calibrated claims and only minor weaknesses.
- 9–10: Consistently distinguishes supported facts from uncertainty, avoids fabrication, and communicates limitations precisely.

### M7 — Canadian Factual Knowledge
**Criterion:** Measures correctness and necessary completeness of Canadian factual answers against verified reference requirements.
**Scope exclusion:** Do not score writing style, general application, or length; do not claim improvement proves a fact was newly acquired during training.
**Required evaluation parameters:** INPUT, ACTUAL_OUTPUT, EXPECTED_OUTPUT, CONTEXT
**Six evaluation steps:**
1. Identify the specific Canadian facts the INPUT asks for, including mandatory facts and applicable dates, jurisdictions, or conditions from the verified benchmark reference.
2. Extract the factual claims the ACTUAL_OUTPUT makes in answering the question, including material additional claims and qualifications.
3. Check each material answer claim for correctness against the supplied verified reference evidence; flag claims outside the available evidence as unverified, not automatically false.
4. Check whether all mandatory facts are correctly covered, allowing faithful paraphrases and genuinely equivalent facts instead of literal matching to EXPECTED_OUTPUT.
5. Assess whether factual statements properly respect the relevant year, province/territory, population, exception, or other qualification; identify material contradictions.
6. Assign an accuracy-and-required-completeness judgment based on verified material claims and omissions. Accept concise or longer equivalent accurate answers without verbosity bonuses or penalties; leave writing style and practical reasoning to other metrics.
**Score bands (raw 0–10):**
- 0–2: Provides predominantly incorrect or seriously misleading Canadian facts.
- 3–4: Recalls some correct information but includes major factual errors or omissions.
- 5–6: Demonstrates partial factual knowledge with important missing or incorrect details.
- 7–8: Provides mostly correct and sufficiently complete Canadian facts with minor inaccuracies.
- 9–10: Provides accurate, appropriately complete factual information consistent with verified reference evidence.

## Scoring guardrails and definition of done

- The six steps are diagnostic checks, NOT six subscores to average. Score only applicable questions. Missing source evidence is a separate status, not a low score. Incorrect reference answers must be escalated, not used as automatic judge truth.
- Preserve v1 and v2 unchanged for reproducibility. The v2 M6 score caps (4/10 for proven material fabricated source checks, 2/10 for proven consequential false eligibility/policy claim) are UNAPPROVED proposals: baseline A/B WITHOUT caps, separate sensitivity table WITH caps only when facts/traces establish the condition.
- No fabricated sources, not-even-implied secret exfiltration, or unsupported statement that the judge ran. If icelab connection fails, implement the comparison harness and report zero live scoring calls.
- Completion means saved raw judge explanations and a compact **case-by-case adjudication report**, not another abstract plan. Report actual calls, accepted counts, skipped IDs, reasons, and artifacts. Do not call the experiment production validated absent independent human review.
