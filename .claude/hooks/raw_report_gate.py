"""SubagentStop counts; Stop warns ONCE if subagents ran and nothing was stored via scripts/agentreport.py."""
import sys, json, time, io
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); from _hook import read, block, run, ROOT
def main():
    action = sys.argv[1] if len(sys.argv) > 1 else ''; d = read()
    st = ROOT / '.claude' / 'state'; st.mkdir(parents=True, exist_ok=True)
    f = st / f'{d.get("session_id") or "session"}.json'
    z = json.load(io.open(f)) if f.exists() else {'begin': time.time(), 'n': 0, 'warned': False}
    if action == 'subagent': z['n'] += 1; io.open(f, 'w').write(json.dumps(z)); return 0
    if action != 'stop' or z['n'] == 0: return 0
    rep = ROOT / 'docs' / 'agentreports'
    if rep.is_dir() and any(p.stat().st_mtime >= z['begin'] and p.stat().st_size > 500 for p in rep.glob('*.json')):
        z.update(n=0, warned=False); io.open(f, 'w').write(json.dumps(z)); return 0
    if d.get('stop_hook_active') or z['warned']: return 0
    z['warned'] = True; io.open(f, 'w').write(json.dumps(z))
    return block(f'RAW REPORT MISSING: {z["n"]} subagent(s) ran but nothing was stored. Store full reports BEFORE summarizing: <report> | python3 scripts/agentreport.py <topic>')
run(main)
