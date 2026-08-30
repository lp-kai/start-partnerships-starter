#!/usr/bin/env python3
"""agentreport.py - store an agent's FULL report before it gets summarized. Local only (docs/agentreports/ is git-ignored).
    <report> | python3 scripts/agentreport.py <topic> [--source name]
Refuses reports that contain secret-looking values."""
import sys, io, os, re, json, datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; DIR = ROOT / 'docs' / 'agentreports'
SECRETS = [r'xox[pbes]-[A-Za-z0-9-]{10,}', r'sk-[A-Za-z0-9_-]{20,}', r'ghp_[A-Za-z0-9]{20,}', r'Bearer\s+[A-Za-z0-9._~+/-]{25,}',
           r'(ESPO_API_KEY|IMAP_APP_PW|SLACK_TOKEN|MEMBERS_API_KEY)\s*[=:]\s*\S{8,}']
def main(argv):
    if not argv or sys.stdin.isatty(): sys.exit('usage: <report> | agentreport.py <topic> [--source name]')
    src = argv[argv.index('--source') + 1] if '--source' in argv else 'unnamed'
    topic = ' '.join(a for a in argv if a not in ('--source', src)); text = sys.stdin.read()
    if any(re.search(p, text) for p in SECRETS): sys.exit('NOT STORED: secret-looking value in the report. Redact first.')
    DIR.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r'[^a-z0-9]+', '-', topic.lower()).strip('-')[:50] or 'report'
    p = DIR / f'{datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")}_{slug}.json'; tmp = p.with_suffix('.tmp')
    with io.open(tmp, 'w', encoding='utf-8') as f:
        json.dump({'topic': topic, 'source': src, 'at': datetime.datetime.now().isoformat(), 'chars': len(text), 'content': text}, f, ensure_ascii=False, indent=2); f.flush(); os.fsync(f.fileno())
    tmp.replace(p); print(f'stored: {p.relative_to(ROOT)} ({len(text)} chars)')
if __name__ == '__main__': main(sys.argv[1:])
