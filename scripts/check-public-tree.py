"""Supplementary release guard; never prints a matched secret.

Use --history to inspect blobs reachable from all local refs, including files
removed in later commits. Images still require manual review.
"""
import argparse
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SELF = 'scripts/check-public-tree.py'
PATTERNS = [
    r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    r'gh[pousr]_[A-Za-z0-9]{30,}',
    r'github_pat_[A-Za-z0-9_]{30,}',
    r'eyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}',
    r'https?://[^\s/]+\.ts\.net',
    r'(?:/Users/|[A-Z]:[\\/]Users[\\/])[A-Za-z0-9_-]+',
    r'(?<![\d.])(?:192\.168|10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}(?![\d.])',
]
FORBIDDEN = {'backups', '.local', 'node_modules', '.storage', 'private', 'deployments'}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def inspect(name, data):
    path = Path(name)
    if (set(path.parts) & FORBIDDEN or
        path.suffix.lower() in {'.blend', '.sqlite3', '.db', '.pem', '.key', '.p12', '.pfx'} or
        '.private.' in path.name or path.name in {'secrets.yaml', 'ha-token'} or
        path.name.startswith('.env') or path.name.endswith('identifiers.json')):
        return 'forbidden deployment artifact'
    if name == SELF or path.suffix.lower() in {'.png', '.jpg', '.glb'}:
        return None
    content = data.decode('utf-8', errors='replace')
    if any(re.search(pattern, content) for pattern in PATTERNS):
        return 'suspicious private material'
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history', action='store_true')
    args = parser.parse_args()
    failures = set()
    files = git('ls-files', '-z').decode('utf-8').split('\0')
    for name in filter(None, files):
        error = inspect(name, (ROOT / name).read_bytes())
        if error:
            failures.add(f'{name}: {error}')
    blobs = set()
    if args.history:
        for commit in git('rev-list', '--all').decode().splitlines():
            for item in git('ls-tree', '-rz', commit).split(b'\0'):
                if not item:
                    continue
                metadata, name = item.split(b'\t', 1)
                _, kind, oid = metadata.split()
                if kind != b'blob':
                    continue
                key = (oid, name)
                if key in blobs:
                    continue
                blobs.add(key)
                name = name.decode('utf-8')
                error = inspect(name, git('cat-file', 'blob', oid.decode()))
                if error:
                    failures.add(f'history {oid.decode()[:12]} {name}: {error}')
    for failure in sorted(failures):
        print(failure)
    if failures:
        raise SystemExit(1)
    print(f'Public-tree scan passed: {len(files)-1} tracked files, {len(blobs)} historical blobs; manual review still required.')


if __name__ == '__main__':
    main()
