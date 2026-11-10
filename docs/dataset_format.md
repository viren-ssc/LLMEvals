# JSONL dataset import

Use UTF-8 JSON, one object per line. Unknown fields, duplicate question/variant pairs, unknown/duplicate metric labels, empty questions/answers and malformed JSON are rejected. Explicit human applicability labels are required. The format can process the planned approximately 510 questions; those questions are not included or invented.

```json
{"question_id":"CAN-0001","question":"Who sets Manitoba public school curriculum?","model_answer":"The provincial education authority.","reference_answer":"The Manitoba provincial education authority.","reference_context":["Independently curated reference content goes here."],"source_urls":[],"reference_ids":["YOUR-CURATED-REF-ID"],"applicable_metrics":["M2","M7"],"model_variant":"base","provenance":"Describe original dataset, source and verification date","illustrative":true}
```

This schema example is illustrative. Replace placeholder evidence and label real records appropriately; it is not verified evaluation data. `reference_answer` is nullable and `reference_context` defaults to an empty list, but applicable metrics requiring these fields fail if evidence is absent. `source_urls` record provenance; the runner does not browse them or pretend to verify them. Provide the actual relevant reference text in `reference_context`. Optional `expected_quality` is used by synthetic pilot cases only.

M1/M4 approve INPUT and ACTUAL_OUTPUT only. M2/M3/M5/M6/M7 additionally approve EXPECTED_OUTPUT and CONTEXT. `reference_answer` maps to expected_output and `reference_context` to context, and these parameters are explicitly included in GEval. Source URLs/IDs are result metadata, not hidden evidence in the judge prompt. If a source must be examined, curate its content into the approved context first.

Independent references must come from authoritative source collection or human verification, never from the answer being evaluated or a judge's invented source. Keep retrieval dates, document versions, question objectives and independent reference identifiers in your provenance ledger. Pilot sources are documented in `data/examples/provenance.md`.

For paired comparison, repeat a question ID with variants `base` and `fine_tuned`, holding question, reference answer/context, source URLs/IDs and applicability fixed. Different model answers are expected. Missing variants and judge failures remain visible rather than being converted to zero. The importer rejects mismatched evidence across variants. Do not include personal, nonpublic or sensitive content until gateway-sharing authorization is confirmed.
