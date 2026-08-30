#!/usr/bin/env python3
"""slack_search.py - read-only Slack search (auth.test, search.messages only). Never posts.
Default output is counts + channel + permalink (no message text in the transcript); --full shows snippets."""
import sys, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _cli import run, preflight


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('query', nargs='?'); ap.add_argument('--max', type=int, default=20)
    ap.add_argument('--auth', action='store_true'); ap.add_argument('--full', action='store_true'); a = ap.parse_args()
    preflight(need_identity=True)
    from _clients import Slack
    s = Slack()
    if a.auth or not a.query:
        d = s.auth(); print(f'OK connected to workspace {d.get("team")}'); return 0
    total, rows, tr = s.search(a.query, a.max)
    print(f'{total} total hits, {len(rows)} fetched' + (' (truncated: raise --max)' if tr else '') + '. Note: message text is internal data; it lands in the AI transcript with --full.')
    for r in rows:
        print(f'#{r["channel"]} {r["ts"]} {r.get("permalink") or ""}' + (f'\n    {r["text"]}' if a.full else ''))
    return 0


if __name__ == '__main__':
    run(main)
