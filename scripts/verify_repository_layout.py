"""Offline navigation and completed-result checks after repository housekeeping."""
import json
import argparse
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--git-index', action='store_true', help='Require link targets to exist in the Git index, not just locally')
    args = parser.parse_args()
    tracked = set()
    if args.git_index:
        output = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT)
        tracked = {p.decode('utf8') for p in output.split(b'\0') if p}
    pages = [ROOT / 'README.md', *ROOT.glob('results/**/*.md')]
    pages += [ROOT / name / 'README.md' for name in ['data', 'config', 'outputs', 'src', 'scripts', 'docs']]
    pages += [ROOT / 'docs/run_answered_benchmark.md', ROOT / 'docs/experiment_interpretation.md', ROOT / 'docs/repository_organization/README.md']
    broken = []
    untracked_targets = []
    checked = 0
    for page in pages:
        for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', page.read_text(encoding='utf8')):
            if '://' in target or target.startswith('#'):
                continue
            path = page.parent / unquote(target.split('#')[0])
            checked += 1
            if not path.exists():
                broken.append(dict(page=str(page.relative_to(ROOT)), target=target))
            elif args.git_index:
                relative = path.resolve().relative_to(ROOT).as_posix()
                published = relative in tracked or (path.is_dir() and any(p.startswith(relative.rstrip('/') + '/') for p in tracked))
                if not published:
                    untracked_targets.append(dict(page=str(page.relative_to(ROOT)), target=target))
    index = ROOT / 'results/run_index.csv'
    import csv
    with index.open(encoding='utf-8-sig', newline='') as f:
        runs = list(csv.DictReader(f))
    assert len(runs) == 12
    total = 0
    for run in runs:
        path = ROOT / run['canonical_output'] / 'all_results.jsonl'
        rows = [json.loads(x) for x in path.read_text(encoding='utf8').splitlines() if x.strip()]
        assert len(rows) == int(run['evaluations'])
        assert all(r['status'] == 'SUCCESS' and r['judge_reason'].strip() for r in rows)
        total += len(rows)
    result = dict(checked_links=checked, broken_links=broken, untracked_link_targets=untracked_targets, git_index_checked=args.git_index, completed_model_runs=len(runs), retained_final_judgments=total, no_judge_calls=True)
    destination = ROOT / 'docs/repository_organization/layout_verification.json'
    destination.write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(result))
    if broken or untracked_targets:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
