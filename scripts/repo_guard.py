#!/usr/bin/env python3
"""repo_guard.py - blocks commits with forbidden paths or secret-looking values. Installed as pre-commit by setup.py.
    python3 scripts/repo_guard.py --staged"""
import sys, re, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = re.compile(r'^(?!\.env\.example$)(\.env($|\.)|.*\.env$|me\.json|data/|drafts/|state/|docs/agentreports/|memory/(?!README\.md)|kb/firmen/(?!_TEMPLATE\.md))')
SECRETS = re.compile(r'xox[pbes]-[A-Za-z0-9-]{10,}|sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|(ESPO_API_KEY|IMAP_APP_PW|SLACK_TOKEN|MEMBERS_API_KEY)[ \t]*=[ \t]*[A-Za-z0-9+/._-]{8,}')
def main():
    files = subprocess.run(['git', 'diff', '--cached', '--name-only'], cwd=ROOT, capture_output=True, text=True).stdout.split()
    bad = [f for f in files if FORBIDDEN.match(f)]; leaks = []
    for f in files:
        p = ROOT / f
        if p.exists() and p.stat().st_size < 5_000_000 and SECRETS.search(p.read_text(encoding='utf-8', errors='ignore')): leaks.append(f)
    if bad or leaks:
        print('COMMIT BLOCKED by repo_guard:', file=sys.stderr)
        for f in bad: print(f'  forbidden path: {f}', file=sys.stderr)
        for f in leaks: print(f'  secret-looking value in: {f}', file=sys.stderr)
        return 1
    return 0
if __name__ == '__main__': sys.exit(main())
