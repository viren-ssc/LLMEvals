"""Reduce the complete archive to records useful for analysis and reporting."""
import csv
import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[1]
folder = root / 'outputs/archives'
source = folder / 'three_models_temp0_temp07_cleaned_complete_20261107.zip'
target = folder / 'three_models_three_conditions_REPORT_20261107.zip'
run_files = {
    'all_results.jsonl', 'full_results.xlsx', 'full_run_report.md',
    'full_run_summary.json', 'completion_verification.json', 'manifest.json',
    'locked_experiment.json', 'retry_report.csv', 'failures.csv',
    'missing_tasks.csv', 'run_statistics.json', 'attempts.csv',
    'metric_summaries.json', 'all_metric_summaries.csv',
}
comparison_folders = {
    'apertus_previous_workbook_cleaned_20261107',
    'gc_llm_previous_workbook_cleaned_20261107',
    'llama_temp0_temp07_cleaned_20261107',
}
def keep(name):
    parts = name.split('/')
    base = parts[-1]
    if name.startswith('analysis/'):
        return base in {'all_16326_judgments.csv', 'all_models_conditions_summaries.csv', 'run_index.csv'}
    if name.startswith('project/outputs/evaluations/'):
        return len(parts) == 5 and base in run_files
    if name.startswith('project/outputs/comparisons/'):
        return parts[3] in comparison_folders and len(parts) == 5 and (
            base.endswith('.xlsx') or base in {
                'report.md', 'comparison_manifest.json',
                'metric_language_role_summaries.csv',
                'all_three_pairwise_metric_comparisons.csv',
                'cleaning_changed_vs_unchanged_decomposition.csv',
            })
    if name.startswith('project/outputs/'):
        return False
    if name.startswith('project/config/'):
        return True
    if name.startswith('project/data/'):
        return True
    if name.startswith('project/src/'):
        return base.endswith('.py')
    if name.startswith('project/scripts/'):
        return base.startswith('analyse_') and base.endswith('.py')
    if name.startswith('project/docs/'):
        return any(s in base for s in ['comparison', 'scoring_review', 'revalidation', 'limitations', 'readiness'])
    if len(parts) == 2:
        return True
    return False

readme = '''# Report and analysis archive: three models, three conditions

AI-provisional, pending calibration. Nine completed M1–M7 runs: Llama, GC LLM and Apertus across original outputs (user-labelled temperature 0), workbook outputs (user-labelled temperature 0.7), and cleaned responses. Each run has 756 questions and 1,814 judgments: 756 primary and 1,058 secondary. Total 16,326 successful individual judgments.

START HERE
analysis/all_16326_judgments.csv is the unified analysis dataset: every answer, score, judge explanation, question, reference/context and evaluation metadata, with model and condition columns. analysis/all_models_conditions_summaries.csv provides separate metric, language and assignment-role means. analysis/run_index.csv maps exact run IDs.

project/outputs/evaluations/<run ID>/all_results.jsonl retains the original full machine-readable records per run. Each full_results.xlsx is the run's review workbook. Execution summaries, retry/failure accounting and configuration manifests are retained.

project/outputs/comparisons/ contains the three side-by-side comparison workbooks, paired metric summaries, language/role summaries and changed-versus-unchanged analysis. Workbooks retain detailed matched scores and reasons.

project/data/ and original dataset files at project/ include supplied evaluation datasets, normalized cases, supporting evidence, source validation and generation metadata. project/config/ preserves fixed evaluation steps, scoring bands, interpretation instructions, run manifests and execution authorizations. project/src/ and analysis scripts preserve scoring and analysis implementation; dependencies are included.

REMOVED TO REDUCE SIZE
Duplicate immutable per-task checkpoint files, worker shards, raw HTTP/session request-response logs, progress/lock files, duplicate primary/secondary exports, duplicate comparison JSONL/CSV containing the same full answers, historical two-condition comparison exports, test files and unrelated operational documents. Every final score and judge explanation remains in the retained per-run JSONL, full Excel workbooks and unified CSV. Historical transport-level payloads and individual failed-call traces are excluded; aggregate execution and retry reports remain. The original complete archive remains available separately.

INTERPRETATION LIMITATIONS
Condition labels do not prove generation temperature/top_p settings. Missing metadata is not inferred. GC LLM workbook contains 755 temperature-0.7 responses and one reused temperature-0 response. Cleaned data are edited workbook strings, not a third generation temperature. Editing can change coverage or meaning. Judge temperature/top_p were omitted/server-default; repeatability is not established, and unchanged answers can receive different scores on independent scoring. Context is judge evidence, not necessarily model input or verified quotation. References may require factual checking. No arbitrary overall Canadian-ness score is supplied. Human/team calibration has not been established.

Rubric SHA-256: bb9889807b7babc8feed6a97ddd0c12c0fa334627e5d295017167fbd0a767cb2
Evaluator final-json-factory-v2 SHA-256: ecb714aa746f7bdce82d86fd9bcc288d4e26ffd15cfa210bbd19a356e095793f
Judge: gpt-oss-120b. DeepEval: 4.3.2. Scores normalized once to 0–1.

The separate new general correctness/completeness experiment is outside this archive. Credentials are excluded. file_inventory.csv lists archived file sizes and SHA-256 hashes, excluding the inventory itself.
'''
inventory = []
with zipfile.ZipFile(source) as src, zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9, allowZip64=True) as dst:
    selected = [i for i in src.infolist() if keep(i.filename)]
    runs = {}
    for i in selected:
        data = src.read(i)
        if i.filename.startswith('project/outputs/evaluations/') and i.filename.endswith('/all_results.jsonl'):
            rows = [json.loads(line) for line in data.decode('utf8').splitlines() if line.strip()]
            assert len(rows) == 1814 and len({(r['question_id'], r['evaluation_metric']) for r in rows}) == 1814
            assert all(r['status'] == 'SUCCESS' and r['judge_reason'].strip() for r in rows)
            runs[i.filename.split('/')[3]] = len(rows)
        dst.writestr(i.filename, data)
        inventory.append(dict(path=i.filename, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    assert len(runs) == 9 and sum(runs.values()) == 16326
    extras = {
        'README.md': readme.encode('utf8'),
        'analysis/archive_manifest.json': json.dumps(dict(created_at=datetime.now(timezone.utc).isoformat(), runs=runs, judgments=16326, result_label='AI-provisional, pending calibration', reduced_from=source.name, exclusions_documented='README.md'), indent=2).encode(),
    }
    for name, data in extras.items():
        dst.writestr(name, data)
        inventory.append(dict(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    buf = io.StringIO(newline='')
    writer = csv.DictWriter(buf, fieldnames=['path', 'bytes', 'sha256'])
    writer.writeheader()
    writer.writerows(inventory)
    dst.writestr('analysis/file_inventory.csv', buf.getvalue().encode('utf-8-sig'))
print('Archive created; verifying...', flush=True)
assert target.stat().st_size < 500_000_000
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
    for r in inventory:
        assert hashlib.sha256(z.read(r['path'])).hexdigest() == r['sha256']
with target.open('rb') as f:
    digest = hashlib.file_digest(f, 'sha256').hexdigest()
target.with_suffix('.zip.sha256').write_text(digest + '  ' + target.name + '\n', encoding='ascii')
print(json.dumps(dict(path=str(target), bytes=target.stat().st_size, decimal_MB=round(target.stat().st_size/1e6, 1), files=len(inventory)+1, verified_judgments=16326, sha256=digest)), flush=True)
