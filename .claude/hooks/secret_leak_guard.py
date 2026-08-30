"""PreToolUse(Bash): blocks commands that would print secret VALUES. Names, lengths, hashes stay allowed."""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); from _hook import read, command, block, run
def main():
    c = command(read())
    if not c: return 0
    if re.search(r'\b(cat|less|more|head|tail|bat|type|Get-Content)\b[^|;&]*(^|[\s/"\'])\.env\b', c) and '.env.example' not in c:
        return block('SECRET GUARD: do not display .env. Check names/lengths only (grep -c, ${#VAR}).')
    if re.search(r'(set|bash)\s+-x', c) and re.search(r'\.env|_creds', c):
        return block('SECRET GUARD: shell trace on a file holding keys would print them.')
    if re.search(r'echo\s+["\']?\$\{?(ESPO_API_KEY|IMAP_APP_PW|SLACK_TOKEN|MEMBERS_API_KEY)\b', c) or re.search(r'\$\{(ESPO_API_KEY|IMAP_APP_PW|SLACK_TOKEN|MEMBERS_API_KEY):[-+]', c):
        return block('SECRET GUARD: expanding a key variable prints its value. Use [ -n "${VAR:-}" ].')
    if re.search(r'\bsetup\.py\b', c):
        return block('SECRET GUARD: setup.py is run by the human in a terminal, never via a tool call.')
    return 0
run(main)
