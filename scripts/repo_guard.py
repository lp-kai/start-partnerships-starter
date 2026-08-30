#!/usr/bin/env python3
"""repo_guard.py - blocks commits with forbidden paths, key-like values or PII. Scans the STAGED content
(git show :path), NUL-separated names. Installed as pre-commit by setup.py. Note: --no-verify skips local
hooks, so the public repo also needs a server-side/CI scan.
    python3 scripts/repo_guard.py --staged"""
import sys, re, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = re.compile(r'^(?!\.env\.example$)(\.env($|\.)|.*\.env$|me\.json($|\.)|data/|drafts/|state/|docs/agentreports/|memory/(?!README\.md$)|kb/firmen/(?!_TEMPLATE\.md$))')
SECRETS = re.compile(r'xox[pbes]-[A-Za-z0-9-]{10,}|sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|(ESPO_API_KEY|IMAP_APP_PW|SLACK_TOKEN|MEMBERS_API_KEY)[ \t]*[=:][ \t]*["\']?[A-Za-z0-9+/._-]{8,}|-----BEGIN [A-Z ]*PRIVATE KEY-----')
PII = re.compile(r'[A-Za-z0-9._%+-]+@(?!(example\.(com|org)|startmunich\.de)(?![A-Za-z0-9.-]))[A-Za-z0-9.-]+\.[A-Za-z]{2,}')


def main():
    r = subprocess.run(['git', 'diff', '--cached', '--name-only', '-z', '--diff-filter=ACMR'], cwd=ROOT, capture_output=True)
    if r.returncode != 0:
        print(f'COMMIT BLOCKED: repo_guard could not read the index ({r.stderr.decode("utf-8", "ignore")[:120]})', file=sys.stderr); return 1
    files = [f.decode('utf-8', 'replace') for f in r.stdout.split(b'\0') if f]
    bad = [f for f in files if FORBIDDEN.match(f)]; leaks, pii = [], []
    for f in files:
        sh = subprocess.run(['git', 'show', f':{f}'], cwd=ROOT, capture_output=True)
        if sh.returncode != 0:
            print(f'COMMIT BLOCKED: cannot read staged content of {f}', file=sys.stderr); return 1
        blob = sh.stdout.decode('utf-8', 'ignore')
        if SECRETS.search(blob): leaks.append(f)
        m = PII.search(blob)
        if m: pii.append(f'{f}: {m.group(0)}')
    if bad or leaks or pii:
        print('COMMIT BLOCKED by repo_guard:', file=sys.stderr)
        for f in bad: print(f'  forbidden path: {f}', file=sys.stderr)
        for f in leaks: print(f'  secret-looking value in: {f}', file=sys.stderr)
        for f in pii: print(f'  external e-mail address (PII) in: {f}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__': sys.exit(main())
