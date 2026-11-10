"""Conservative, logged repository housekeeping. No judge calls or scoring changes."""
import argparse
import hashlib
import json
import shutil
from functools import lru_cache
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / 'docs/repository_organization'
ROOT_FILES = {p.name for p in ROOT.iterdir() if p.is_file()}

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

@lru_cache(maxsize=None)
def resolve(value):
    if not isinstance(value, str) or len(value) > 400 or '\n' in value:
        return None
    if '/' not in value and '\\' not in value and value not in ROOT_FILES:
        return None
    try:
        p = (ROOT / value).resolve()
        if p.is_relative_to(ROOT) and p.is_file():
            return p
    except (ValueError, OSError):
        pass
    return None

def protected_paths():
    protected = set()
    def walk(value):
        if isinstance(value, dict):
            for k, v in value.items():
                p = resolve(k)
                if p:
                    protected.add(p)
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)
        else:
            p = resolve(value)
            if p:
                protected.add(p)
    for p in (ROOT / 'config').rglob('*.json'):
        walk(json.loads(p.read_text(encoding='utf-8-sig')))
        protected.add(p.resolve())
    # Historical calibration ledgers also bind earlier assets and review artifacts.
    for p in (ROOT / 'outputs').glob('calibration/*/prior_artifact_integrity.json'):
        walk(json.loads(p.read_text(encoding='utf-8-sig')))
    # Keep source-path compatibility for existing fixed commands.
    source_names = set()
    for p in (ROOT / 'src').rglob('*.py'):
        text = p.read_text(encoding='utf8')
        for candidate in ROOT.iterdir():
            if candidate.is_file() and candidate.name in text:
                source_names.add(candidate.resolve())
    return protected | source_names

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    LOG.mkdir(parents=True, exist_ok=True)
    if args.apply and (LOG / 'cleanup_plan.json').exists():
        report = json.loads((LOG / 'cleanup_plan.json').read_text(encoding='utf8'))
        before = json.loads((LOG / 'protected_files_sha256.json').read_text(encoding='utf8'))
        protected = {(ROOT / name).resolve() for name in before}
        protected_parents = {parent for p in protected for parent in p.parents}
        failures = []
        for move in report['moves']:
            a, b = ROOT / move['source'], ROOT / move['destination']
            if a.resolve() in protected or not a.resolve().is_relative_to(ROOT) or not b.resolve().is_relative_to(ROOT):
                raise ValueError('Invalid move target')
            if a.exists():
                if b.exists():
                    raise ValueError('Destination already exists; re-plan instead of overwriting')
                b.parent.mkdir(parents=True, exist_ok=True)
                a.rename(b)
        for name in report['removals']:
            p = ROOT / name
            target = p.resolve()
            if not target.is_relative_to(ROOT) or target == ROOT or target in protected or target in protected_parents:
                raise ValueError('Invalid removal target')
            try:
                if p.is_dir():
                    shutil.rmtree(p)
                elif p.exists():
                    p.unlink()
            except OSError as exc:
                failures.append(dict(path=name, error=str(exc)))
        print('Cleanup applied; checking all protected artifact hashes...', flush=True)
        changes = [name for name, expected in before.items() if not (ROOT/name).is_file() or sha(ROOT/name) != expected]
        report.update(applied=True, removal_failures=failures, protected_integrity_changes=changes)
        (LOG / 'cleanup_applied.json').write_text(json.dumps(report, indent=2), encoding='utf8')
        print(json.dumps(dict(protected_files=len(before), integrity_changes=len(changes), removal_failures=len(failures))), flush=True)
        if changes:
            raise ValueError('Protected artifact integrity check failed')
        return
    protected = protected_paths()
    before = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    moves, deletions = [], []
    for name, destination in {
        'apertus_756_evaluation_1024_tokens.jsonl': 'data/incoming/apertus_as_generated',
        'apertus_756_evaluation_1024_tokens.xlsx': 'data/incoming/apertus_as_generated',
        'benchmark_examples_7.jsonl': 'data/examples',
        'correctness_completeness_4_candidates_each.xlsx': 'docs/history/metric_proposals',
        'CODEX_PROMPT (1).md': 'docs/history/setup',
        'project_instructions.txt': 'docs/history/setup',
        'README (1).md': 'docs/history/setup',
        'README.txt': 'docs/history/setup',
        'v1_20261103.json': 'docs/history/setup',
    }.items():
        p = ROOT / name
        if p.exists() and p.resolve() not in protected:
            dest = ROOT / destination / name
            if dest.exists():
                if sha(p) == sha(dest):
                    deletions.append(p)
            else:
                moves.append((p, dest))
    # Remove only generated working artifacts outside all immutable path contracts.
    for name in ['.pytest_cache', '.ruff_cache', '.tmp', 'pytest-cache-files-e4x3z45d',
                 'pytest-cache-files-qstbr9ae', 'outputs/diagnostics', 'outputs/verification',
                 'outputs/metric_candidates', 'outputs/archives/three_models_three_conditions_20261107',
                 'outputs/archives/three_models_temp0_temp07_cleaned_complete_20261107.zip',
                 'outputs/archives/three_models_temp0_temp07_cleaned_complete_20261107.zip.sha256']:
        p = ROOT / name
        if p.exists() and not any(q == p.resolve() or q.is_relative_to(p.resolve()) for q in protected):
            deletions.append(p)
    # Worker shards are duplicates only when their bytes occur in canonical raw/records.
    duplicate_shards = []
    for run in (ROOT / 'outputs/evaluations').iterdir():
        shard = run / 'shards'
        if not shard.exists():
            continue
        canonical = {sha(p) for sub in ['records', 'raw'] for p in (run / sub).glob('*.json')}
        for p in shard.rglob('*.json'):
            if p.resolve() not in protected and sha(p) in canonical:
                duplicate_shards.append(p)
    deletions.extend(duplicate_shards)
    report = dict(created_at=datetime.now(timezone.utc).isoformat(), applied=args.apply,
                  protected_files=len(protected),
                  moves=[dict(source=str(a.relative_to(ROOT)), destination=str(b.relative_to(ROOT))) for a,b in moves],
                  removals=[str(p.relative_to(ROOT)) for p in deletions],
                  protected_root_files=sorted(p.name for p in protected if p.parent == ROOT))
    if args.apply:
        failures = []
        for a, b in moves:
            b.parent.mkdir(parents=True, exist_ok=True)
            a.rename(b)
        for p in deletions:
            target = p.resolve()
            if not target.is_relative_to(ROOT) or target == ROOT:
                raise ValueError('Refusing operation outside repository')
            try:
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
            except OSError as exc:
                failures.append(dict(path=str(p.relative_to(ROOT)), error=str(exc)))
        report['removal_failures'] = failures
        changes = [name for name, expected in before.items() if not (ROOT/name).is_file() or sha(ROOT/name) != expected]
        report['protected_integrity_changes'] = changes
        if changes:
            raise ValueError('Protected artifacts changed: ' + str(changes))
    (LOG / ('cleanup_applied.json' if args.apply else 'cleanup_plan.json')).write_text(json.dumps(report, indent=2), encoding='utf8')
    (LOG / 'protected_files_sha256.json').write_text(json.dumps(before, indent=2), encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['removals','moves']}))
    print('Planned moves:', len(moves), 'removals:', len(deletions), flush=True)

if __name__ == '__main__':
    main()
