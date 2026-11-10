# Human calibration protocol (proposed, not completed)

Before production use, independently label a stratified pilot sample across the seven metrics, provinces/territories, English/French, factual/practical prompts and answer lengths. Include distinctions among Indigenous peoples with appropriate domain review. Start with 30–60 questions if resources permit; sample size should be justified by study precision, not this illustrative suggestion.

Two reviewers first assign applicability and reference adequacy without seeing model identity. Score anonymized base and fine-tuned responses independently with the same frozen definitions, recording native scores, explanations and uncertainty. Randomize presentation order and obscure model variant and prior LLM scores. Resolve definitions on a development subset and freeze a new version before held-out assessment.

Report human–human and human–judge agreement with sample counts, mean absolute error and rank association; an ordinal weighted kappa or an appropriately specified ICC may supplement these if their assumptions fit. Retain disagreements and inspect construct confusion separately from factual evidence disputes. Do not report agreement until actual independent labels exist.

Repeat judge scoring on a subset with separate output paths while holding all inputs fixed. Report within-question spread, rank/order reversals, failure rates and score drift; gateway-default sampling prevents guarantees of identical results. Treat repeat scores as repeated measurements, not new independent questions.

Create meaning-preserving concise/expanded answer pairs, including correct brief factual answers and long irrelevant answers. Test score differences within pairs. Create carefully reviewed English/French equivalents, randomize layout/order and test possible position/presentation effects. Distinguish legitimate language requirements from bias. Test confident fabricated assertions versus properly bounded uncertainty on M6.

For each comparison document applicable count, missing data, uncertainty, effects and limitations. Inspect whether strong responses generally outrank weak ones without concealing contrary outcomes. The built-in synthetic pilot checks ordering only; its length/language/bias analyses remain pending. Material rubric revisions require a new reviewed frozen version and a fresh held-out check. No human calibration, inter-rater analysis or broad validity claim has been completed by generating this framework.
