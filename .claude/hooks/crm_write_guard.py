"""PreToolUse(Bash): blocks CRM writes from ad-hoc commands, per shell segment, case-insensitive.
Exemption only for an exact call of scripts/crm_claim.py. Fails CLOSED."""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); from _hook import read, command, block, run_closed

EXEMPT = re.compile(r'^\s*(python[0-9.]*|py(\s+-3)?)\s+(\S*/)?scripts/crm_claim\.py(\s|$)')
CRM = re.compile(r'espo\.|/api/v1/|X-Api-Key|ESPO_API_KEY|espocrm', re.I)
WRITE = re.compile(r'-X\s*(POST|PUT|PATCH|DELETE)\b|--request\s+(POST|PUT|PATCH|DELETE)\b|--json\b|--upload-file\b|method\s*=\s*["\'](POST|PUT|PATCH|DELETE)["\']|\.(post|put|patch|delete)\s*\(|--data(-raw|-binary)?\b|(^|\s)-d\s|\bDELETE\b', re.I)


def main():
    cmd = command(read())
    if CRM.search(cmd) and WRITE.search(cmd) and not EXEMPT.match(cmd.strip()):
        return block('CRM WRITE GUARD: CRM target and a write verb in the same command. Rule 2: never delete; only scripts/crm_claim.py may write.')
    for seg in re.split(r'[;&|]+|\n', cmd):
        s = seg.strip()
        if not s or EXEMPT.match(s): continue
        if CRM.search(s) and WRITE.search(s):
            return block('CRM WRITE GUARD: no POST/PUT/PATCH/DELETE to the CRM from ad-hoc commands. Rule 2: never delete; the only write path is scripts/crm_claim.py (when enabled).')
    return 0


run_closed(main)
