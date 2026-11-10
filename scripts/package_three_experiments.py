"""Read-only source collection and verified research archive creation."""
import csv
import hashlib
import io
import json
import statistics
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/archives/three_models_three_conditions_20261107'
OUT.mkdir(parents=True, exist_ok=True)
files = set()

def collect(path):
    p = ROOT / path
    if not p.exists():
        raise FileNotFoundError(p)
    for f in ([p] if p.is_file() else p.rglob('*')):
        if f.is_file() and not any(x in f.parts for x in ['__pycache__', '.git', '.venv']):
            if f.suffix not in ['.pyc', '.lock'] and f.name != '.env':
                files.add(f)

def table(name, rows):
    (OUT / (name + '.jsonl')).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf8')
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with (OUT / (name + '.csv')).open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in r.items()} for r in rows)

runs = []
judgments = []
common_keys = None
for model in ['llama', 'gc_llm', 'apertus']:
    original = {'llama': 'llama_full_20261106_v2', 'gc_llm': 'gc_llm_full_as_generated_20261106_v2', 'apertus': 'apertus_full_as_generated_c4_20261107_v2'}[model]
    for condition, rid in [('original_temp0_label', original), ('workbook_temp07_label', f'{model}_mixed_temperature_workbook_c4_20261107_v2'), ('cleaned', f'{model}_cleaned_responses_c4_20261107_v2')]:
        folder = ROOT / 'outputs/evaluations' / rid
        rows = [json.loads(line) for line in (folder / 'all_results.jsonl').read_text(encoding='utf8').splitlines() if line.strip()]
        keys = {(r['question_id'], r['evaluation_metric']) for r in rows}
        assert len(rows) == len(keys) == 1814
        assert all(r['status'] == 'SUCCESS' and r['judge_reason'].strip() and 0 <= r['score'] <= 1 for r in rows)
        assert len({r['question_id'] for r in rows}) == 756
        assert sum(r['metric_role'] == 'primary' for r in rows) == 756
        assert sum(r['metric_role'] == 'secondary' for r in rows) == 1058
        if common_keys is None:
            common_keys = keys
        assert common_keys == keys
        runs.append(dict(model=model, condition=condition, run_id=rid, questions=756, successful=1814, primary=756, secondary=1058))
        judgments.extend(dict(r, archive_condition=condition, archive_model=model) for r in rows)
        collect(folder.relative_to(ROOT))
        collect(Path('config/research') / rid)

for path in ['data/incoming', 'config/final', 'config/evaluator', 'config/frozen', 'src', 'scripts', 'tests', 'requirements.txt', 'requirements-lock.txt', 'requirements-verification-lock.txt', 'pyproject.toml', 'README.md', 'Canadianness_Final_GEVAL_Evaluation_Steps.xlsx', 'Canadianness_Final_GEVAL_Metrics.json', 'Canadian_ness_Three_Models_Cleaned_for_Evaluation.jsonl', 'canadianness_756_three_model_answers_MIXED_TEMPERATURE_COMPLETE.xlsx', 'apertus_756_evaluation_1024_tokens.jsonl', 'apertus_756_evaluation_1024_tokens.xlsx']:
    collect(path)
for p in (ROOT / 'data/processed').iterdir():
    if p.is_dir() and 'general_answer' not in p.name:
        collect(p.relative_to(ROOT))
for base in ['docs', 'outputs/comparisons']:
    for p in (ROOT / base).iterdir():
        if not any(x in p.name.lower() for x in ['general_quality', 'general_answer', 'correctness_completeness']):
            collect(p.relative_to(ROOT))
for name in ['cleaned_three_model_queue_v1', 'mixed_temperature_three_model_queue_v1']:
    collect(Path('config/research') / name)
    collect(Path('outputs/queues') / name)

table('all_16326_judgments', judgments)
table('run_index', runs)
groups = defaultdict(list)
for r in judgments:
    for axes in [(), ('language',), ('metric_role',), ('language', 'metric_role')]:
        groups[(r['archive_condition'], r['archive_model'], r['evaluation_metric'], axes, tuple(r[k] for k in axes))].append(r['score'])
summaries = []
for (condition, model, metric, axes, values), scores in sorted(groups.items()):
    summaries.append(dict(condition=condition, model=model, metric=metric, grouping='/'.join(axes) or 'metric', **dict(zip(axes, values)), evaluations=len(scores), mean_score=statistics.mean(scores), result_label='AI-provisional, pending calibration'))
table('all_models_conditions_summaries', summaries)
readme = '''# Three-model, three-condition research archive

AI-provisional, pending calibration. Execution authorization is not scientific validation or team approval.

Nine completed M1–M7 runs: Llama, GC LLM and Apertus, each evaluated on the original outputs (user-labelled temperature 0), mixed-temperature workbook (user-labelled temperature 0.7), and cleaned workbook-derived responses. Each run has 756 questions, 1,814 successful metric judgments, 756 primary assignments and 1,058 secondary assignments. Total: 16,326 judgments. No new judge calls were made to create this archive.

START HERE
- analysis/all_16326_judgments.csv or .jsonl: unified records, answers, reference information, context, scores, judge reasoning and original metadata. archive_condition and archive_model identify groups.
- analysis/all_models_conditions_summaries.csv: all nine conditions by metric, language, primary/secondary role and language×role. Means remain separate per metric; no combined score.
- analysis/run_index.csv: exact run IDs and counts.
- project/outputs/comparisons/: detailed per-model side-by-side comparison workbooks and paired CSV/JSONL, including changed/unchanged answer decomposition.
- project/outputs/evaluations/<run ID>/: complete run exports, immutable individual records/raw judge responses, sessions, checkpoints, request/retry accounting and failure reports. Historical failed attempts can exist despite every final task succeeding.
- project/data/incoming/ and data/processed/: original supplied datasets, normalized selected-model cases, validation and generation metadata. Original root datasets are also preserved under project/.
- project/config/: exact frozen rubric, interpretation instructions, run manifests and execution-permission records. Existing snapshots are preserved, including historical pending-state labels; consult execution records/completion reports together.
- project/src/, scripts/, tests/, requirements*: implementation, analysis code and environment dependencies.
- project/docs/: protocol, scoring limitations, pilot reviews and comparison reports. Some documents describe earlier historical states; final run records are authoritative for completed counts.
- analysis/file_inventory.csv: per-file SHA-256 and sizes for every other archive member.

IMPORTANT COMPARABILITY LIMITATIONS
Temperature labels are condition names, not independently verified generation settings for all models. Missing original temperature/top_p/prompt/revision metadata is not inferred. GC LLM workbook explicitly contains 755 temperature-0.7 answers and one reused temperature-0 answer. Cleaned answers are edited workbook responses, not generations at another temperature. Cleaning may change meaning/coverage as well as repetition. Judge sampling was omitted/server-default, not proven deterministic; identical answer texts can receive different scores in independent runs. Language/role groups and multiple metrics have different task counts. Metrics should be interpreted independently. Context is supporting judge evidence, not necessarily tested-model input or verified verbatim quotation. Reference answers are not infallible.

The original 42 steps, 35 bands and scoring rubric remain unchanged. Rubric SHA-256: bb9889807b7babc8feed6a97ddd0c12c0fa334627e5d295017167fbd0a767cb2. Evaluator final-json-factory-v2 SHA-256: ecb714aa746f7bdce82d86fd9bcc288d4e26ffd15cfa210bbd19a356e095793f. Judge: gpt-oss-120b; DeepEval 4.3.2. Scores use 0–1 normalization once.

Scope excludes the separate ongoing general correctness/completeness experiment. Credentials, .env, virtual environments, caches, Git internals and live lock files are excluded. This archive contains research responses and complete judge evidence; share appropriately. Archive source files are unmodified unless explicitly listed as credential-redacted in archive_manifest.json.
'''
(OUT / 'README.md').write_text(readme, encoding='utf8')

# Only values of explicitly secret-labelled .env entries are used for a non-printing credential scan.
secrets = []
env = ROOT / '.env'
if env.exists():
    for line in env.read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key, value = line.split('=', 1)
            value = value.strip().strip('"\'')
            if any(t in key.upper() for t in ['API_KEY', 'TOKEN', 'PASSWORD', 'SECRET']) and len(value) >= 12:
                secrets.append(value.encode())
archive = OUT.parent / 'three_models_temp0_temp07_cleaned_complete_20261107.zip'
inventory = []
redacted = []
with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
    members = [(str(Path('project') / p.relative_to(ROOT)).replace('\\', '/'), p) for p in sorted(files)]
    members += [('analysis/' + p.name, p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name not in ['archive_manifest.json', 'file_inventory.csv']]
    for name, path in members:
        data = path.read_bytes()
        source_hash = hashlib.sha256(data).hexdigest()
        for secret in secrets:
            if secret in data:
                data = data.replace(secret, b'[REDACTED_CREDENTIAL]')
                if name not in redacted:
                    redacted.append(name)
        z.writestr(name, data)
        inventory.append(dict(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), source_sha256=source_hash, credential_redacted=name in redacted))
    manifest = dict(created_at=datetime.now(timezone.utc).isoformat(), runs=runs, successful_judgments=len(judgments), all_tasks_unique=True, conditions=3, models=3, result_label='AI-provisional, pending calibration', credential_redacted_files=redacted, inventory_entries=len(inventory), scope='Completed M1–M7 experiments only')
    manifest_data = json.dumps(manifest, indent=2).encode()
    z.writestr('analysis/archive_manifest.json', manifest_data)
    inventory.append(dict(path='analysis/archive_manifest.json', bytes=len(manifest_data), sha256=hashlib.sha256(manifest_data).hexdigest(), source_sha256='', credential_redacted=False))
    buf = io.StringIO(newline='')
    writer = csv.DictWriter(buf, fieldnames=list(inventory[0]))
    writer.writeheader()
    writer.writerows(inventory)
    z.writestr('analysis/file_inventory.csv', buf.getvalue().encode('utf-8-sig'))
    (OUT / 'archive_manifest.json').write_bytes(manifest_data)
    (OUT / 'file_inventory.csv').write_text(buf.getvalue(), encoding='utf-8-sig')
print('Archive written; verifying all CRCs and inventory hashes...', flush=True)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert len(z.namelist()) == len(set(z.namelist()))
    for r in inventory:
        assert hashlib.sha256(z.read(r['path'])).hexdigest() == r['sha256'], r['path']
digest = hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest()
archive.with_suffix('.zip.sha256').write_text(digest + '  ' + archive.name + '\n', encoding='ascii')
print(json.dumps(dict(archive=str(archive), bytes=archive.stat().st_size, files=len(inventory)+1, judgments=len(judgments), credential_redacted_file_count=len(redacted), sha256=digest)), flush=True)
