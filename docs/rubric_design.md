# Rubric design and human review

All seven editable rubric drafts are in `config/rubric_drafts.yaml`. They retain the requested metric-specific behavioral anchors, general materiality guidance, metric-specific boundaries, examples and ambiguity guidance. The workbook carries those descriptions for manual revision; it never selects an anchor as approved.

| Native interval | Normalized conceptual interval | Meaning |
|---|---|---|
| 0–2 | 0.0–0.2 | Very poor |
| 3–4 | 0.3–0.4 | Poor |
| 5–6 | 0.5–0.6 | Partial |
| 7–8 | 0.7–0.8 | Good |
| 9–10 | 0.9–1.0 | Excellent |

These cover native integer anchors. Custom-judge schema scores may be fractional; these intervals should not be interpreted as banning every intermediate continuous value. DeepEval owns score normalization over the full 0–10 span. The transport does not request or assume logprobs.

Within a band, use the extent and consequence of errors. Perfect performance means satisfying every task-relevant requirement within that metric with no material error; it does not require listing all provincial institutions, irrelevant nuance or bilingual text in every answer. A concise complete answer can earn 10. Omission is material when it leaves an explicit part unanswered, prevents a practical action, confuses responsibility or misrepresents a community. Cosmetic omissions should not dominate.

Unsupported claims affect M6 directly and another metric only when they impair that metric's own construct. Avoid mechanically subtracting the same number across dimensions. Missing reference material is an evaluator input failure, not grounds for assigning an answer zero. The pilot examples are calibration exercises, with explicit assumptions or separately cited official reference material; they are not a representative validation sample.

Reviewers should resolve ambiguity about necessary detail, regional scope, historical dates, institutional names, reasonable uncertainty and harmless language variants. Choose observable steps, remove irrelevant constructs, examine near duplicates and add/revise missing concepts through explicit workbook edits. The clustering method uses normalized character-sequence similarity >=0.78 against each group's first representative; run-frequency counts distinct runs, not duplicate mentions inside one run. This transparent lexical heuristic misses paraphrases and may group text that differs in a crucial negation. Human review is essential.

Coverage uses literal concept keyword hits, not an embedding model or secret second judge. Missing concepts, vague short steps and cross-metric leakage are suggestions for a researcher to inspect. Neither frequency nor a generated quality suggestion is approval. GEval remains an LLM-based judgment and these rubrics do not guarantee deterministic scores.
