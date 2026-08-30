"""PreToolUse (Bash, Read, Grep, Glob, Edit, Write): keeps key VALUES out of the transcript.
Bash: blocks displaying/sourcing/tracing .env and expanding key variables, per shell segment.
File tools: blocks any access to .env / me.json. Fails CLOSED on its own errors (secrets are not worth a fail-open)."""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); from _hook import read, block, run_closed

KEYS = r'(ESPO_API_KEY|IMAP_APP_PW|SLACK_TOKEN|MEMBERS_API_KEY)'
ENV = r'(^|[\s/"\'=])\.env(?!\.example)\b'


def check_segment(seg):
    seg = seg.strip()
    if not seg: return None
    if re.search(r'\b(cat|less|more|head|tail|bat|type|Get-Content|strings|xxd|od|nl|sed|awk|grep|rg|cut|paste|tee)\b', seg) and re.search(ENV, seg):
        return 'SECRET GUARD: do not read .env in a command. Check names/lengths only (e.g. grep -c "=" is fine via scripts, not here).'
    if re.search(r'(^|[\s;&|])(source|\.)\s+\S*\.env\b', seg) or re.search(r'\bexport\b.*\.env', seg) or re.search(r'\benv\b\s*($|>)', seg) or re.search(r'\bprintenv\b', seg) or re.search(r'\bset\b\s*($|\|)', seg):
        return 'SECRET GUARD: sourcing .env or dumping the environment prints keys.'
    if re.search(r'(set|bash|sh)\s+-x', seg) and re.search(r'\.env|_creds', seg):
        return 'SECRET GUARD: shell trace on a file holding keys would print them.'
    if re.search(r'\b(echo|printf|print|write-host|Write-Output)\b.*\$\{?' + KEYS, seg, re.I) or re.search(r'\$\{' + KEYS + r':[-+]', seg) or re.search(r'\$\{' + KEYS + r'\}', seg):
        return 'SECRET GUARD: expanding a key variable prints its value. Use [ -n "${VAR:-}" ] or ${#VAR}.'
    if re.search(r'(open|read_text|Path)\s*\(\s*["\'][^"\']*\.env["\']', seg) and 'example' not in seg:
        return 'SECRET GUARD: reading .env from inline code prints or leaks keys. Use scripts/_creds.py.'
    if re.search(r'(?<![\w.])(python[0-9.]*|py)\b.*\bsetup\.py\b', seg) or re.match(r'\./setup\.py', seg):
        return 'SECRET GUARD: setup.py is run by the human in a terminal, never via a tool call.'
    return None


def main():
    d = read(); tool = d.get('tool_name'); ti = d.get('tool_input') or {}
    if tool in ('Read', 'Grep', 'Glob', 'Edit', 'Write', 'MultiEdit', 'NotebookEdit'):
        target = ' '.join(str(ti.get(k, '')) for k in ('file_path', 'path', 'pattern', 'glob', 'notebook_path') if ti.get(k)).replace('\\', '/').strip()
        if re.search(r'(^|/)\.env(\.(?!example)|\s|$)|(^|/)me\.json', target) or (tool == 'Grep' and re.search(KEYS, str(ti.get('pattern', '')))):
            return block('SECRET GUARD: .env and me.json are never opened by tools. Ask the human to run setup.py or health_check.py.')
        return 0
    if tool != 'Bash': return 0
    cmd = ti.get('command') or ''
    for seg in re.split(r'[;&|]+|\n', cmd):
        msg = check_segment(seg)
        if msg: return block(msg)
    return 0


run_closed(main)
