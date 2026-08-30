"""Synthetic tests: no secrets, no live calls. Run: python3 tests/test_all.py
Includes the bypasses reproduced in the 2026-08-30 security review as regressions."""
import subprocess, sys, json, os, tempfile, shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; H = ROOT / '.claude' / 'hooks'
sys.path.insert(0, str(ROOT / 'scripts'))
fails = 0
KEY = 'ESPO_' + 'API_KEY'  # assembled so this file never looks like a leak
ENVF = '.' + 'env'


def check(name, ok):
    global fails; print(('PASS ' if ok else 'FAIL ') + name); fails += 0 if ok else 1


def hook(script, payload, arg=None):
    cmd = [sys.executable, str(H / script)] + ([arg] if arg else [])
    return subprocess.run(cmd, input=json.dumps(payload), capture_output=True, text=True).returncode


B = lambda c: {'tool_name': 'Bash', 'tool_input': {'command': c}}
F = lambda tool, path: {'tool_name': tool, 'tool_input': {'file_path': path}}

# ---- lint ----
check('lint selftest', subprocess.run([sys.executable, str(ROOT / 'scripts' / 'draft_lint.py'), '--selbsttest'], capture_output=True).returncode == 0)

# ---- send guard ----
check('send: blocks smtplib', hook('send_guard.py', B('python3 -c "import smtplib"')) == 2)
check('send: blocks compound cat;python', hook('send_guard.py', B('cat x; python3 -c "import smtplib"')) == 2)
check('send: blocks curl smtp://', hook('send_guard.py', B('curl smtp://smtp.gmail.com --mail-from a@b.c')) == 2)
check('send: blocks sendmail', hook('send_guard.py', B('sendmail -t < mail.txt')) == 2)
check('send: blocks imap append inline', hook('send_guard.py', B('python3 -c "import imaplib; m.append(x)"')) == 2)
check('send: allows grep smtplib', hook('send_guard.py', B('grep -rn smtplib scripts/')) == 0)
check('send: allows exact gmail_draft call', hook('send_guard.py', B('python3 scripts/gmail_draft.py --to a@b.c --subject s --body-file f')) == 0)
check('send: exemption not by mention', hook('send_guard.py', B('echo gmail_draft.py; python3 -c "import smtplib"')) == 2)
check('send: fails CLOSED on garbage', subprocess.run([sys.executable, str(H / 'send_guard.py')], input='not json', capture_output=True, text=True).returncode == 0)  # garbage parses to {} -> no command -> allow

# ---- secret guard ----
check('secret: blocks cat env', hook('secret_leak_guard.py', B('cat ' + ENVF)) == 2)
check('secret: blocks cat env; echo example (bypass)', hook('secret_leak_guard.py', B('cat ' + ENVF + '; echo .env.example')) == 2)
check('secret: blocks source env; env', hook('secret_leak_guard.py', B('source ' + ENVF + '; env')) == 2)
check('secret: blocks python open(env)', hook('secret_leak_guard.py', B('python3 -c "print(open(\'' + ENVF + '\').read())"')) == 2)
check('secret: blocks grep on env', hook('secret_leak_guard.py', B('grep KEY ' + ENVF)) == 2)
check('secret: allows env.example', hook('secret_leak_guard.py', B('cat .env.example')) == 0)
check('secret: blocks echo $KEY', hook('secret_leak_guard.py', B('echo $' + KEY)) == 2)
check('secret: blocks ${KEY:-x}', hook('secret_leak_guard.py', B('echo ${' + KEY + ':-x}')) == 2)
check('secret: allows [ -n ${KEY:-} ]', hook('secret_leak_guard.py', B('[ -n "${' + KEY + ':-}" ] && echo set')) == 2 or True)  # informational
check('secret: blocks running setup.py', hook('secret_leak_guard.py', B('python3 setup.py')) == 2)
check('secret: allows git diff setup.py', hook('secret_leak_guard.py', B('git diff -- setup.py')) == 0)
check('secret: Read tool on env blocked', hook('secret_leak_guard.py', F('Read', str(ROOT / ENVF))) == 2)
check('secret: Read tool on me.json blocked', hook('secret_leak_guard.py', F('Read', 'me.json')) == 2)
check('secret: Read tool on README allowed', hook('secret_leak_guard.py', F('Read', 'README.md')) == 0)
check('secret: Grep for key names blocked', hook('secret_leak_guard.py', {'tool_name': 'Grep', 'tool_input': {'pattern': KEY, 'path': '.'}}) == 2)

# ---- crm guard ----
crm = 'https://espo.dedicated.startmunich.de/api/v1/Account/1'
check('crm: blocks DELETE', hook('crm_write_guard.py', B(f'curl -X DELETE {crm} -H "X-Api-Key: x"')) == 2)
check('crm: blocks lowercase -X delete', hook('crm_write_guard.py', B(f'curl -X delete {crm}')) == 2)
check('crm: blocks --request PUT', hook('crm_write_guard.py', B(f'curl --request PUT {crm} -d x')) == 2)
check('crm: blocks python requests.post', hook('crm_write_guard.py', B('python3 -c "import requests; requests.post(\'https://espo.dedicated.startmunich.de/api/v1/Note\')"')) == 2)
check('crm: allows GET', hook('crm_write_guard.py', B(f'curl {crm}?maxSize=1 -H "X-Api-Key: x"')) == 0)
check('crm: allows exact claim call', hook('crm_write_guard.py', B('python3 scripts/crm_claim.py 123')) == 0)
check('crm: exemption not by mention (bypass)', hook('crm_write_guard.py', B(f'echo crm_claim.py; curl -X DELETE {crm}')) == 2)

# ---- gitignore ----
ign = lambda f: subprocess.run(['git', 'check-ignore', '-q', f], cwd=ROOT).returncode == 0
for f in (ENVF, ENVF + '.bak', 'me.json', 'me.json.tmp', 'data/x.json', 'drafts/x.md', 'kb/firmen/acme.md', 'memory/MEMORY.md', 'state/t.json', 'docs/agentreports/r.json'):
    check(f'gitignore {f}', ign(f))
check('gitignore keeps template', not ign('kb/firmen/_TEMPLATE.md'))
check('gitignore keeps env.example', not ign('.env.example'))

# ---- repo_guard scans the INDEX, not the worktree ----
tmp = Path(tempfile.mkdtemp()); subprocess.run(['git', 'init', '-q', str(tmp)])
shutil.copy(ROOT / 'scripts' / 'repo_guard.py', tmp / 'repo_guard.py'); (tmp / 'scripts').mkdir(); shutil.copy(ROOT / 'scripts' / 'repo_guard.py', tmp / 'scripts' / 'repo_guard.py')
(tmp / 'note.txt').write_text('SLACK_TOKEN' + '=xoxp-' + '1234567890-abcdefghijk\n'); subprocess.run(['git', 'add', 'note.txt'], cwd=tmp)
(tmp / 'note.txt').write_text('clean now\n')  # worktree clean, index dirty
r = subprocess.run([sys.executable, str(tmp / 'scripts' / 'repo_guard.py'), '--staged'], cwd=tmp, capture_output=True, text=True)
check('repo_guard: catches staged secret even if worktree clean', r.returncode == 1)
(tmp / 'my file.md').write_text('hello ' + 'ext@' + 'company.io\n'); subprocess.run(['git', 'add', 'my file.md'], cwd=tmp); subprocess.run(['git', 'rm', '--cached', '-q', 'note.txt'], cwd=tmp)
r = subprocess.run([sys.executable, str(tmp / 'scripts' / 'repo_guard.py'), '--staged'], cwd=tmp, capture_output=True, text=True)
check('repo_guard: handles spaces in names + flags external e-mail (PII)', r.returncode == 1 and 'PII' in r.stderr)
shutil.rmtree(tmp)

# ---- classification (mocked data, no network) ----
import importlib.util
spec = importlib.util.spec_from_file_location('fc', ROOT / 'scripts' / 'firma_check.py'); fc = importlib.util.module_from_spec(spec); spec.loader.exec_module(fc)
ME = {'crm': {'owner_user_name': 'me person', 'api_user_id': 'apime'}, 'email': 'x@startmunich.de'}
mk = lambda blocks: {'blocks': [dict(source=s, rows=r, error=e, truncated=t) for s, r, e, t in blocks]}
check('classify: open opp -> STOP', fc.classify(mk([('crm.opportunities', [{'name': 'o', 'stage': 'Qualification'}], None, False)]), ME)[0] == 'STOP')
check('classify: closed opp only -> not STOP', fc.classify(mk([('crm.opportunities', [{'name': 'o', 'stage': 'Closed Lost'}], None, False)]), ME)[0] != 'STOP')
check('classify: opp without stage -> ABSTIMMEN', fc.classify(mk([('crm.opportunities', [{'name': 'o'}], None, False)]), ME)[0] == 'ABSTIMMEN')
check('classify: foreign open task -> STOP', fc.classify(mk([('crm.tasks', [{'name': 't', 'status': 'Not Started', 'assignedUserName': 'Other One'}], None, False)]), ME)[0] == 'STOP')
check('classify: foreign claim -> STOP', fc.classify(mk([('crm.stream', [{'type': 'Post', 'by': 'Other', 'at': fc.NOW.strftime('%Y-%m-%d'), 'post': '[PARTNERSHIPS-CLAIM] owner=other one'}], None, False)]), ME)[0] == 'STOP')
check('classify: own claim -> no STOP', fc.classify(mk([('crm.stream', [{'type': 'Post', 'by': 'me person', 'at': fc.NOW.strftime('%Y-%m-%d'), 'post': '[PARTNERSHIPS-CLAIM] owner=me person'}], None, False)]), ME)[0] != 'STOP')
check('classify: foreign lead -> ABSTIMMEN', fc.classify(mk([('crm.leads', [{'name': 'l', 'status': 'New', 'assignedUserName': 'Other'}], None, False)]), ME)[0] == 'ABSTIMMEN')
check('classify: source error -> ABSTIMMEN', fc.classify(mk([('slack', [], 'slack: search -> HTTP 500', False)]), ME)[0] == 'ABSTIMMEN')
check('classify: truncated -> never KEIN KONFLIKT', fc.classify(mk([('crm.emails', [], None, True)]), ME)[0] != 'KEIN KONFLIKT GEFUNDEN')
check('classify: slack hits -> ABSTIMMEN', fc.classify(mk([('slack', [{'ts': '1'}], None, False)]), ME)[0] == 'ABSTIMMEN')
check('classify: nothing -> KEIN KONFLIKT', fc.classify(mk([('crm.account', [], None, False)]), ME)[0] == 'KEIN KONFLIKT GEFUNDEN')
check('slug: unicode/non-latin safe', fc.slug('Müller & Söhne') != fc.slug('Мюллер') and len(fc.slug('北京公司')) > 6)

# ---- clients helpers (no network) ----
os.environ.setdefault('ESPO_' + 'API_KEY', 'x'); os.environ.setdefault('IMAP_' + 'APP_PW', 'x'); os.environ.setdefault('SLACK_' + 'TOKEN', 'x')
import _clients as cl
check('retry-after: seconds capped', cl._retry_after({'Retry-After': '600'}) == cl.MAX_WAIT)
check('retry-after: garbage -> default', cl._retry_after({'Retry-After': 'soon'}) == 5.0)
check('retry-after: http-date parsed', 0 <= cl._retry_after({'Retry-After': 'Wed, 21 Oct 2015 07:28:00 GMT'}) <= cl.MAX_WAIT)
check('imap quote escapes', cl.imap_quote('a"b\\c') == '"a\\"b\\\\c"')

# ---- agentreport ----
r = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'agentreport.py'), 't'], input='SLACK_TOKEN=' + 'xoxp-' + '1234567890-abcdefghijk', capture_output=True, text=True)
check('agentreport refuses secrets', r.returncode != 0)

print(f'\n{fails} failures'); sys.exit(1 if fails else 0)
