"""Offline navigation and completed-result checks after repository housekeeping."""
import json
import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


def main():
    pages = [ROOT / 'README.md', *ROOT.glob('results/**/*.md')]
    pages += [ROOT / name / 'README.md' for name in ['data', 'config', 'outputs', 'src', 'scripts', 'docs']]
    pages += [ROOT / 'docs/run_answered_benchmark.md', ROOT / 'docs/experiment_interpretation.md', ROOT / 'docs/repository_organization/README.md']
    broken = []
    checked = 0
    for page in pages:
        for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', page.read_text(encoding='utf8')):
            if '://' in target or target.startswith('#'):
                continue
            path = page.parent / unquote(target.split('#')[0])
            checked += 1
            if not path.exists():
                broken.append(dict(page=str(page.relative_to(ROOT)), target=target))
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
    result = dict(checked_links=checked, broken_links=broken, completed_model_runs=len(runs), retained_final_judgments=total, no_judge_calls=True)
    destination = ROOT / 'docs/repository_organization/layout_verification.json'
    destination.write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(result))
    if broken:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
