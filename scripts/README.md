# Script directory

Run scripts from the repository root with `.\.venv\Scripts\python.exe scripts\<name>.py`.

| Use | Scripts |
|---|---|
| Convert a supplied answer column, no inference | `prepare_answered_dataset.py` |
| Compare three response conditions | `analyse_llama_three_conditions.py`, `analyse_three_response_conditions.py --model gc_llm` or `--model apertus` |
| Historical two-condition analyses | `analyse_*_run_comparison.py`, `analyse_llama_temperature_comparison.py` |
| Report archive | `package_report_archive.py` (requires the old complete ZIP as its input; historical packaging recipe) |
| Full archive from canonical files | `package_three_experiments.py` (historical root-file assumptions; consult its paths before reuse) |
| Rebuild navigation and small summaries | `build_repository_catalog.py` |
| Preview/perform logged housekeeping | `organize_repository.py`, then `organize_repository.py --apply` |
| Check navigation, retained judgments and Git-visible links | `verify_repository_layout.py --git-index` |
| Check Git-visible files for suspected secrets | `check_git_secrets.py` |
| Development and historical diagnostics | Remaining calibration, isolation, concurrency, review and verification helpers |

Prefer the documented module commands in [the run guide](../docs/run_answered_benchmark.md) for evaluation. Historical helpers remain for provenance; they are not all required in a new study. Do not rerun candidate-generation or concurrency scripts just to inspect saved results: they can make live requests.
