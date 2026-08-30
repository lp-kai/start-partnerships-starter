#!/usr/bin/env python3
"""members_search.py - company search on the members platform. No full member export, ever.
Shows current AND former members - former ones count as intro paths."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _clients import Members, SourceError
from _config import team
if len(sys.argv) < 2: sys.exit('usage: members_search.py "<company>"')
m = Members()
if not m.enabled: sys.exit('MEMBERS_API_KEY not set (optional source) - rerun setup.py to add it')
try:
    rows = m.companies(sys.argv[1], team()['limits']['members_max_hits'])
    print(f'{len(rows)} companies matched'); import json
    for r in rows: print(json.dumps(r, ensure_ascii=False)[:300])
except SourceError as e:
    print(e, file=sys.stderr); sys.exit(1)
