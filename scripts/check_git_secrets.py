"""Offline check of Git-visible files; reports paths, never secret values.

Checks known local .env secrets and recognizable token/private-key patterns.
This is a precaution, not a guarantee that every possible secret is detected.
"""
import re
import subprocess
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    re.compile(rb'\bsk-[A-Za-z0-9_-]{24,}\b'),
    re.compile(rb'\bhf_[A-Za-z0-9]{24,}\b'),
    re.compile(rb'\bgh[pousr]_[A-Za-z0-9]{30,}\b'),
    re.compile(rb'\bgithub_pat_[A-Za-z0-9_]{30,}\b'),
    re.compile(rb'\bAKIA[A-Z0-9]{16}\b'),
]


def main():
    result = subprocess.run(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
        cwd=ROOT, check=True, capture_output=True,
    )
    names = sorted(set(n.decode('utf8') for n in result.stdout.split(b'\0') if n))
    secrets = [
        v.encode('utf8') for k, v in dotenv_values(ROOT / '.env').items()
        if v and len(v) >= 12 and any(s in k.upper() for s in ['KEY', 'TOKEN', 'PASSWORD', 'SECRET'])
    ]
    findings = []
    for name in names:
        p = ROOT / name
        if not p.is_file():
            continue
        data = p.read_bytes()
        if any(secret in data for secret in secrets) or any(pattern.search(data) for pattern in PATTERNS):
            findings.append(name)
        if p.name == '.env' or (p.name.startswith('.env.') and p.name != '.env.example'):
            if name not in findings:
                findings.append(name)
    print(f'Checked {len(names)} Git-visible files. Suspected-secret files: {len(findings)}.')
    for name in findings:
        print(name)
    return 1 if findings else 0


if __name__ == '__main__':
    raise SystemExit(main())
