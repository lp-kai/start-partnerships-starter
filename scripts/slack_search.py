#!/usr/bin/env python3
"""slack_search.py - read-only Slack search (auth.test, search.messages only). Never posts."""
import sys, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _clients import Slack, SourceError
ap = argparse.ArgumentParser(); ap.add_argument('query', nargs='?'); ap.add_argument('--count', type=int, default=15); ap.add_argument('--auth', action='store_true')
a = ap.parse_args(); s = Slack()
try:
    if a.auth or not a.query:
        d = s.auth(); print(f'OK {d.get("user")} @ {d.get("team")}'); sys.exit(0)
    total, rows = s.search(a.query, a.count)
    print(f'{total} total hits (showing {len(rows)}; first page can be noise - keep paging before concluding)')
    for r in rows: print(f'#{r["channel"]} {r["user"]}: {r["text"]}')
except SourceError as e:
    print(e, file=sys.stderr); sys.exit(1)
