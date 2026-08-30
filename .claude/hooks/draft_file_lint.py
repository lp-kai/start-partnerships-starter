"""PostToolUse(Write|Edit): lints markdown under drafts/ with scripts/draft_lint.py. Second line of defense."""
import sys, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); from _hook import read, block, run, ROOT
def main():
    d = read()
    if d.get('tool_name') not in ('Write', 'Edit'): return 0
    p = ((d.get('tool_input') or {}).get('file_path') or '').replace('\\', '/')
    if not p.endswith('.md') or ('/drafts/' not in p and not p.startswith('drafts/')): return 0
    lint = ROOT / 'scripts' / 'draft_lint.py'
    if not lint.exists() or not Path(p).exists(): return 0
    r = subprocess.run([sys.executable, str(lint), p], capture_output=True, text=True, timeout=30)
    return block(f'DRAFT LINT found issues in {p}:\n{r.stdout}') if r.returncode == 1 else 0
run(main)
