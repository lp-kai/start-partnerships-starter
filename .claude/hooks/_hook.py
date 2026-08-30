"""Shared helpers. Every hook fails OPEN (exit 0) on its own errors and logs to .claude/state/hook-errors.log."""
import sys, json, datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
def read():
    try: return json.loads(sys.stdin.read() or '{}')
    except Exception: return {}
def command(d): return ((d.get('tool_input') or {}).get('command') or '') if d.get('tool_name') == 'Bash' else ''
def block(msg): print(msg, file=sys.stderr); return 2
def run(main):
    try: sys.exit(main())
    except Exception as e:
        try:
            p = ROOT / '.claude' / 'state'; p.mkdir(parents=True, exist_ok=True)
            open(p / 'hook-errors.log', 'a').write(f'{datetime.datetime.now().isoformat()} {Path(sys.argv[0]).name}: {e!r}\n')
        except Exception: pass
        sys.exit(0)
