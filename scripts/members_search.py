#!/usr/bin/env python3
"""members_search.py - company search on the members platform. No full member export, ever.
Default output: company names + member count; --full shows the matched people (personal data)."""
import sys, argparse, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _cli import run, preflight, die


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('company'); ap.add_argument('--full', action='store_true'); a = ap.parse_args()
    preflight(need_identity=True)
    from _clients import Members
    from _config import team
    m = Members()
    if not m.enabled: die('MEMBERS_API_KEY not set (optional source). Rerun setup.py to add it.')
    rows = m.companies(a.company, team()['limits']['members_max_hits'])
    print(f'{len(rows)} companies matched (current AND former members count as intro paths)')
    for r in rows:
        if a.full: print(json.dumps(r, ensure_ascii=False)[:400])
        else:
            name = r.get('name') or r.get('company') or '?'
            n = len(r.get('members', r.get('people', []))) if isinstance(r, dict) else '?'
            print(f'  {name}: {n} member(s). Use --full to see who (personal data).')
    return 0


if __name__ == '__main__':
    run(main)
