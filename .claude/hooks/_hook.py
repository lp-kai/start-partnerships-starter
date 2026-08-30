"""Shared hook helpers. run(): fails OPEN (exit 0) on own errors, for non-security gates.
run_closed(): fails CLOSED (exit 2) for the secret/send/crm guards. Both log to .claude/state/hook-errors.log."""
import sys, json, datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent


def read():
    try: return json.loads(sys.stdin.read() or '{}')
    except Exception: return {}


def command(d): return ((d.get('tool_input') or {}).get('command') or '') if d.get('tool_name') == 'Bash' else ''


def block(msg): print(msg, file=sys.stderr); return 2


def _log(e):
    try:
        p = ROOT / '.claude' / 'state'; p.mkdir(parents=True, exist_ok=True)
        open(p / 'hook-errors.log', 'a').write(f'{datetime.datetime.now().isoformat()} {Path(sys.argv[0]).name}: {e!r}\n')
    except Exception: pass


def run(main):
    try: sys.exit(main())
    except SystemExit: raise
    except Exception as e: _log(e); sys.exit(0)


def run_closed(main):
    try: sys.exit(main())
    except SystemExit: raise
    except Exception as e:
        _log(e); print(f'GUARD ERROR ({Path(sys.argv[0]).name}): blocked to be safe. See .claude/state/hook-errors.log', file=sys.stderr); sys.exit(2)
