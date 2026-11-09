#!/usr/bin/env python3
"""Check this public archive for excluded data and verify its hash index."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'SNAPSHOT-SHA256SUMS.json'
SKIP = {'.git', '__pycache__', '.venv'}
FORBIDDEN_SUFFIXES = {'.deb', '.pem', '.key', '.p12', '.pfx', '.ko', '.o', '.a',
                      '.bin', '.tar', '.gz', '.bz2', '.xz', '.zst'}


def files():
    return sorted(p for p in ROOT.rglob('*') if p.is_file()
                  and not any(part in SKIP for part in p.relative_to(ROOT).parts)
                  and p != MANIFEST)


def inspect(path):
    relative = path.relative_to(ROOT)
    problems = []
    if path.is_symlink():
        return [f'{relative}: symlinks are excluded from the public snapshot']
    if path.suffix.lower() in FORBIDDEN_SUFFIXES or path.name in {'.env', 'hosts.yml', 'id_rsa', 'id_ed25519'}:
        problems.append(f'{relative}: excluded artifact filename')
    data = path.read_bytes()
    if len(data) > 2_000_000:
        problems.append(f'{relative}: unexpectedly large file')
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        return problems + [f'{relative}: binary/non-UTF-8 content']
    # Construct secret/personal-data patterns without embedding actual secrets
    # or the original local identifiers inside the checker itself.
    patterns = ['/' + r'home/(?!example(?:/|\b))[^/\s`"\']+/',
                r'\b192\.168\.\d{1,3}\.\d{1,3}\b',
                r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})',
                r'-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----',
                r'\bAKIA[A-Z0-9]{16}\b']
    for pattern in patterns:
        if re.search(pattern, text):
            problems.append(f'{relative}: potential unredacted personal data or credential')
    for match in re.finditer(r'\benx([0-9a-fA-F]{12})\b', text):
        if match[1] != '020000000001':
            problems.append(f'{relative}: actual MAC-derived interface name')
    for match in re.finditer(r'(?<![0-9a-fA-F:])(?:[0-9a-fA-F]{2}:){5,}[0-9a-fA-F]{2}(?![0-9a-fA-F:])', text):
        if match[0].lower() not in {'02:00:00:00:00:01', '02:00:00:00:00:02', '02:00:00:00:00:03'}:
            problems.append(f'{relative}: actual MAC or long network identity')
    for match in re.finditer(r'\b[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\b', text):
        if not re.fullmatch(r'00000000-0000-4000-8000-[0-9]{12}', match[0]):
            problems.append(f'{relative}: non-placeholder UUID')
    if path.suffix == '.json':
        try:
            json.loads(text)
        except json.JSONDecodeError:
            problems.append(f'{relative}: invalid JSON')
    if path.suffix == '.py':
        try:
            compile(text, str(relative), 'exec')
        except SyntaxError:
            problems.append(f'{relative}: invalid Python syntax')
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-manifest', action='store_true')
    args = parser.parse_args()
    paths = files()
    problems = [problem for path in paths for problem in inspect(path)]
    if problems:
        raise SystemExit('\n'.join(problems))
    actual = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in paths}
    if args.write_manifest:
        MANIFEST.write_text(json.dumps(actual, indent=2, sort_keys=True) + '\n')
    if not MANIFEST.is_file():
        raise SystemExit('Snapshot index missing; use --write-manifest after review.')
    expected = json.loads(MANIFEST.read_text())
    if expected != actual:
        raise SystemExit('Snapshot index differs; review changes and refresh it.')
    print(f'Publication checks passed: {len(paths)} UTF-8 source/evidence files, JSON/Python validation, privacy checks and SHA256 index.')


if __name__ == '__main__':
    main()
