"""PreToolUse(Bash): blocks CRM writes (POST/PUT/PATCH/DELETE) from ad-hoc commands. Only scripts/crm_claim.py may write, when enabled."""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); from _hook import read, command, block, run
def main():
    c = command(read())
    if not c or 'crm_claim.py' in c: return 0
    if re.search(r'espo\.|/api/v1/|X-Api-Key|ESPO_API_KEY', c) and re.search(r'-X\s*(POST|PUT|PATCH|DELETE)|method\s*=\s*["\'](POST|PUT|PATCH|DELETE)|\.(post|put|patch|delete)\(|--data\b|\s-d\s', c):
        return block('CRM WRITE GUARD: no POST/PUT/PATCH/DELETE to the CRM from ad-hoc commands. Rule 2: never delete; writes only via the approved claim script.')
    return 0
run(main)
