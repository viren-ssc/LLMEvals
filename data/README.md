# Datasets

| Folder | Contents |
|---|---|
| [benchmarks/core_756/](benchmarks/core_756/) | Answer-free question/reference view, with derivation and hashes |
| [incoming/](incoming/) | Supplied answered benchmarks, untouched |
| [processed/](processed/) | Per-model evaluator inputs, selected answers and generation metadata |
| calibration/, examples/ | Controls and examples required by calibration/testing code; not final research results |
| verification/ | Original reference-verification provenance, where retained |

## Answered sources

- Original Llama: `incoming/Canadian-ness_Llama_756_Ready_for_DeepEval.xlsx` and normalized generations JSONL.
- Original GC LLM: `incoming/gc_llm_as_generated/`.
- Original Apertus: `incoming/apertus_as_generated/`.
- Workbook condition: `incoming/mixed_temperature_three_model/`.
- Cleaned condition: `incoming/cleaned_three_model/`.
- Two additional metrics: reuse the same cleaned strings; prepared selected-model cases are in `processed/general_answer_quality_cleaned_v1/`.

The answer-free benchmark is a projection of supplied question/reference fields, not an independently recovered earlier benchmark or new factual verification. Original answered sources are retained. No responses were shortened or corrected during this organization.

Put future supplied files in `incoming/<benchmark_name>/` and version converted files in `processed/<benchmark_name>_v1/`. Never overwrite a historical input. See [run guide](../docs/run_answered_benchmark.md).
