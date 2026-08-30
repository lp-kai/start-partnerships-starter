"""PreToolUse: keeps key VALUES out of the transcript.

Bash: blocks reading, sourcing or tracing the env file, dumping the environment, and expanding key
variables. Single-quoted text is literal, so printing a key NAME in single quotes stays allowed
while an expansion in double quotes does not. File tools: blocks access to the env file and me.json.
Fails CLOSED on malformed input.
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hook import read, block, run_closed
from _shell import segments, program, tokens, expanded

KEYS = r'(ESPO_API_KEY|IMAP_APP_PW|SLACK_TOKEN|MEMBERS_API_KEY)'
ENVFILE = re.compile(r'(^|[\s/"\'=])\.env(?!\.example)(\s|$|["\'])')
READERS = {'cat', 'less', 'more', 'head', 'tail', 'bat', 'type', 'get-content', 'strings', 'xxd',
           'od', 'nl', 'sed', 'awk', 'grep', 'rg', 'ugrep', 'cut', 'paste', 'tee', 'sort', 'jq'}
PRINTERS = {'echo', 'printf', 'print', 'write-host', 'write-output', 'tee', 'logger'}


def check_segment(seg):
    prog = program(seg)
    text = expanded(seg)          # what the shell would actually expand
    toks = tokens(seg)

    if prog in READERS and ENVFILE.search(seg):
        return 'SECRET GUARD: do not read the env file. Key values must never enter the transcript.'
    if (prog in ('source', '.') or (toks and toks[0] in ('source', '.'))) and ENVFILE.search(seg):
        return 'SECRET GUARD: sourcing the env file puts keys into the environment of the next command.'
    if prog == 'env':
        rest = [t for t in toks[1:] if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', t)]
        if not rest or all(t.startswith('-') for t in rest):
            return 'SECRET GUARD: dumping the environment prints keys.'
    if prog in ('printenv', 'set') and len(toks) <= 2:
        return f'SECRET GUARD: {prog} prints the environment, including keys.'
    if re.search(r'\b(set|bash|sh)\s+-x', seg) and re.search(r'\.env|_creds', seg):
        return 'SECRET GUARD: shell trace on a file holding keys would print them.'
    if prog in PRINTERS and re.search(r'\$\{?' + KEYS, text):
        return 'SECRET GUARD: this expansion would print a key value. Test presence with a length check instead.'
    if re.search(r'\$\{' + KEYS + r':[-+]', text):
        return 'SECRET GUARD: this expansion can print a key value.'
    if re.search(r'(open|read_text|readFileSync|Path)\s*\(\s*["\'][^"\']*\.env["\']', seg) and 'example' not in seg:
        return 'SECRET GUARD: reading the env file from inline code leaks keys. Use scripts/_creds.py.'
    if re.search(r'(?<![\w.])(python[0-9.]*|py)\b[^|;&]*\bsetup\.py\b', seg) or seg.strip().startswith('./setup.py'):
        return 'SECRET GUARD: setup.py is run by the human in a terminal, never via a tool call.'
    return None


def main():
    d = read()
    if d.get('_malformed'):
        return block('SECRET GUARD: could not parse the tool payload. Blocking to be safe.')
    tool = d.get('tool_name'); ti = d.get('tool_input') or {}
    if tool in ('Read', 'Grep', 'Glob', 'Edit', 'Write', 'MultiEdit', 'NotebookEdit'):
        target = ' '.join(str(ti.get(k, '')) for k in ('file_path', 'path', 'glob', 'notebook_path') if ti.get(k)).replace('\\', '/').strip()
        if re.search(r'(^|/)\.env(\.(?!example)|\s|$)|(^|/)me\.json', target) or \
           (tool == 'Grep' and re.search(KEYS, str(ti.get('pattern', '')))):
            return block('SECRET GUARD: the env file and me.json are never opened by tools. Run setup.py or health_check.py instead.')
        return 0
    if tool != 'Bash':
        return 0
    for seg in segments(ti.get('command') or ''):
        msg = check_segment(seg)
        if msg:
            return block(msg)
    return 0


run_closed(main)
