# Metric boundaries and applicability

Applicability is assigned by a human during dataset curation using an explicit `applicable_metrics` list. No judge invents applicability and no absent dimension receives zero. Empty lists are permitted for intentionally out-of-scope controls. For a real study use question objectives, language requirements and independently curated evidence to label applicability **before seeing base/fine-tuned answers**. Check label agreement on a sample.

| Metric | Apply when | Do not use it to score |
|---|---|---|
| M1 Context Recognition | The answer must interpret a Canadian or implicit jurisdictional cue, e.g. Ontario health coverage | Every waiting-period detail after the framing is correctly Canadian |
| M2 Institutional and Regional Understanding | The task distinguishes responsibility or institutional relationships, e.g. Manitoba curriculum authority | A capital-city fact with no institutional question |
| M3 Canadian Knowledge Application | The task requires usable reasoning for a concrete situation, e.g. planning an interprovincial move | Purely recalling the name of a province |
| M4 Language and Terminology | Language choice or Canadian terms are task-relevant, e.g. a French ARC explanation | Harmless spelling variants or failure to provide unrequested bilingual text |
| M5 Cultural and Societal Understanding | Historical/social context or community diversity is relevant, e.g. distinctions among Indigenous peoples | Bonus cultural commentary added to an unrelated factual answer |
| M6 Factual Reliability and Uncertainty | Grounding, unknown eligibility, citations, currentness or confidence is tested | Repeating M7's factual recall penalty without a separate grounding/calibration failure |
| M7 Factual Knowledge Acquisition | Independent reference facts establish requested accuracy and completeness | Natural prose style, practical planning or generic recognition |

An Ontario response using US insurance framing is an M1 failure. Giving Canadian framing with an unsupported exact eligibility date may be an M6 failure and, if the task independently tests that date, M7 as well. Record distinct rationales rather than automatically copying the same penalty to all seven metrics.

Misassigning curriculum responsibility primarily tests M2. M7 can also apply if the research question explicitly tests recall of the responsible body, but the overlap should be declared at curation time. M3 can be poor despite all quoted facts being correct if the response never applies them to the user's constraints. M6 can be strong when a model appropriately says it cannot determine an answer from missing evidence; M7 is not a universal reward for hedging.

For M1 and M4, question/output evidence suffices in this draft design. Other metrics require reference answer and context. If your task needs external linguistic evidence for M4, revise that metric's approved evidence requirements and parameters before freezing rather than passing hidden supplementary facts.
