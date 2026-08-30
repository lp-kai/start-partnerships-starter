"""PreToolUse(Bash): blocks CRM writes from ad-hoc commands.

Per segment, so an external POST next to a CRM GET is fine. Variables that hold a CRM URL are
tracked across segments, so `URL=...; curl -X DELETE $URL` is still caught. The exemption applies
only to a real execution of scripts/crm_claim.py. Fails CLOSED on malformed input.
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hook import read, block, run_closed
from _shell import segments, program, is_read_only, script_target, expanded, tokens

CRM = re.compile(r'espo[a-z0-9.-]*\.|/api/v1/|X-Api-Key|ESPO_API_KEY|espocrm', re.I)
WRITE = re.compile(r'-X\s*["\']?(POST|PUT|PATCH|DELETE)|--request[= ]+["\']?(POST|PUT|PATCH|DELETE)'
                   r'|method\s*=\s*["\'](POST|PUT|PATCH|DELETE)|\.(post|put|patch|delete)\s*\('
                   r'|--data(-raw|-binary|-urlencode)?\b|--json\b|--upload-file\b|(^|\s)-d(\s|=)', re.I)
NET = {'curl', 'wget', 'http', 'httpie'}


def main():
    d = read()
    if d.get('_malformed'):
        return block('CRM WRITE GUARD: could not parse the tool payload. Blocking to be safe.')
    if d.get('tool_name') != 'Bash':
        return 0
    cmd = (d.get('tool_input') or {}).get('command') or ''
    crm_vars = set()
    for seg in segments(cmd):
        # remember variables that hold a CRM target
        for t in tokens(seg):
            m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)=(.*)$', t)
            if m and CRM.search(m.group(2)):
                crm_vars.add(m.group(1))
        tgt = script_target(seg, 'scripts/crm_claim.py')
        if tgt == 'real':
            continue
        if tgt == 'lookalike':
            return block('CRM WRITE GUARD: that is not scripts/crm_claim.py. Only the real claim script may write.')
        if is_read_only(seg):
            continue
        text = seg
        hits_crm = bool(CRM.search(text)) or any(re.search(r'\$\{?' + v + r'\b', expanded(seg)) for v in crm_vars)
        if hits_crm and WRITE.search(text):
            prog = program(seg)
            if prog in NET or prog not in ('', 'echo', 'printf'):
                return block('CRM WRITE GUARD: write verb against a CRM target. Rule 2: never delete; '
                             'the only write path is scripts/crm_claim.py (enabled by the CRM admin).')
    return 0


run_closed(main)
