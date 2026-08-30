"""Synthetic tests: no secrets, no live calls, no network. Run: python3 tests/test_all.py

Every bypass and every false alarm reproduced in the three security review rounds is a regression
test here. Tests assert behaviour (exit codes, classification), not wording.
"""
import subprocess, sys, json, os, tempfile, shutil, importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
H = ROOT / '.claude' / 'hooks'
sys.path.insert(0, str(ROOT / 'scripts'))
fails = []
KEY = 'ESPO_' + 'API_KEY'          # assembled so this file never looks like a leak
ENVF = '.' + 'env'
TOK = 'xoxp-' + '1234567890-abcdefghijk'
BLOCK, ALLOW = 2, 0


def check(name, ok):
    print(('PASS ' if ok else 'FAIL ') + name)
    if not ok: fails.append(name)


def hook(script, payload, raw=None, arg=None):
    cmd = [sys.executable, str(H / script)] + ([arg] if arg else [])
    data = raw if raw is not None else json.dumps(payload)
    return subprocess.run(cmd, input=data, capture_output=True, text=True).returncode


B = lambda c: {'tool_name': 'Bash', 'tool_input': {'command': c}}
F = lambda tool, path: {'tool_name': tool, 'tool_input': {'file_path': path}}

print('--- draft lint ---')
check('lint selftest 8/8', subprocess.run([sys.executable, str(ROOT / 'scripts' / 'draft_lint.py'), '--selbsttest'], capture_output=True).returncode == 0)

print('--- send guard: must block ---')
for name, cmd in [
    ('smtplib inline', 'python3 -c "import smtplib"'),
    ('compound cat then python', 'cat x; python3 -c "import smtplib"'),
    ('curl smtp scheme', 'curl smtp://smtp.gmail.com --mail-from a@b.c'),
    ('openssl to 465', 'openssl s_client -connect smtp.gmail.com:465'),
    ('nc to port 25', 'nc mx.example.com 25'),
    ('sendmail', 'sendmail -t < mail.txt'),
    ('imap append inline', 'python3 -c "import imaplib; m.append(x)"'),
    ('gmail api messages send', 'curl https://gmail.googleapis.com/gmail/v1/users/me/messages/send -d @m.json'),
    ('gmail api drafts send via www', 'curl https://www.googleapis.com/gmail/v1/users/me/drafts/send -d @m.json'),
    ('lookalike path evil dir', 'python3 evil/scripts/gmail_draft.py'),
    ('lookalike suffix', 'python3 scripts/gmail_draft.py.evil -c "import smtplib"'),
    ('exemption only mentioned', 'echo gmail_draft.py; python3 -c "import smtplib"'),
    ('substitution behind exempt call', 'python3 scripts/gmail_draft.py --to a@b.c --subject "$(python3 -c \'import smtplib\')" --body-file f'),
]:
    check(f'send blocks: {name}', hook('send_guard.py', B(cmd)) == BLOCK)

print('--- send guard: must allow ---')
for name, cmd in [
    ('grep smtplib', 'grep -rn smtplib scripts/'),
    ('grep gmail api host', 'grep -rn gmail.googleapis.com docs/'),
    ('echo endpoint path', 'echo /messages/send'),
    ('real draft call', 'python3 scripts/gmail_draft.py --to a@b.c --subject s --body-file f'),
    ('git status', 'git status'),
    ('curl normal api', 'curl https://api.example.com/v1/things'),
]:
    check(f'send allows: {name}', hook('send_guard.py', B(cmd)) == ALLOW)

print('--- secret guard: must block ---')
for name, cmd in [
    ('cat env file', 'cat ' + ENVF),
    ('cat env then echo example', 'cat ' + ENVF + '; echo .env.example'),
    ('source env then dump', 'source ' + ENVF + '; env'),
    ('env -0', 'env -0'),
    ('printenv', 'printenv'),
    ('python open env file', 'python3 -c "print(open(\'' + ENVF + '\').read())"'),
    ('grep on env file', 'grep KEY ' + ENVF),
    ('echo expanded key', 'echo "$' + KEY + '"'),
    ('printf expanded key', 'printf "%s" "$' + KEY + '"'),
    ('default expansion', 'echo ${' + KEY + ':-x}'),
    ('run setup.py via tool', 'python3 setup.py'),
]:
    check(f'secret blocks: {name}', hook('secret_leak_guard.py', B(cmd)) == BLOCK)

print('--- secret guard: must allow ---')
for name, cmd in [
    ('cat env example', 'cat .env.example'),
    ('literal name in single quotes', "printf '$" + KEY + "'"),
    ('length check only', 'test -n "${#' + KEY + '}" && echo set'),
    ('git diff setup.py', 'git diff -- setup.py'),
    ('env with assignment prefix', 'env FOO=1 python3 scripts/health_check.py'),
]:
    check(f'secret allows: {name}', hook('secret_leak_guard.py', B(cmd)) == ALLOW)

check('secret blocks Read on env file', hook('secret_leak_guard.py', F('Read', str(ROOT / ENVF))) == BLOCK)
check('secret blocks Read on me.json', hook('secret_leak_guard.py', F('Read', 'me.json')) == BLOCK)
check('secret allows Read on README', hook('secret_leak_guard.py', F('Read', 'README.md')) == ALLOW)
check('secret blocks Grep for key names', hook('secret_leak_guard.py', {'tool_name': 'Grep', 'tool_input': {'pattern': KEY, 'path': '.'}}) == BLOCK)

print('--- crm guard ---')
crm = 'https://espo.dedicated.startmunich.de/api/v1/Account/1'
for name, cmd, want in [
    ('DELETE', f'curl -X DELETE {crm} -H "X-Api-Key: x"', BLOCK),
    ('lowercase delete', f'curl -X delete {crm}', BLOCK),
    ('request PUT', f'curl --request PUT {crm} -d x', BLOCK),
    ('curl --json', f'curl --json @x.json {crm}', BLOCK),
    ('python requests post', 'python3 -c "import requests; requests.post(\'https://espo.dedicated.startmunich.de/api/v1/Note\')"', BLOCK),
    ('url in variable then write', f'URL={crm}\ncurl -X DELETE $URL', BLOCK),
    ('exemption only mentioned', f'echo crm_claim.py; curl -X DELETE {crm}', BLOCK),
    ('lookalike claim script', f'python3 scripts/crm_claim.py.evil; curl -X DELETE {crm}', BLOCK),
    ('plain GET', f'curl {crm}?maxSize=1 -H "X-Api-Key: x"', ALLOW),
    ('real claim call', 'python3 scripts/crm_claim.py 123', ALLOW),
    ('external POST next to CRM GET', f'curl {crm} -H "X-Api-Key: x"; curl -X POST https://hooks.example.com/x -d ok', ALLOW),
    ('grep for api path', 'grep -rn "/api/v1/" docs/', ALLOW),
]:
    check(f'crm {"blocks" if want == BLOCK else "allows"}: {name}', hook('crm_write_guard.py', B(cmd)) == want)

print('--- malformed payloads ---')
for g in ('send_guard.py', 'secret_leak_guard.py', 'crm_write_guard.py'):
    check(f'{g} blocks malformed payload', hook(g, None, raw='{') == BLOCK)
    check(f'{g} allows empty payload', hook(g, None, raw='') == ALLOW)

print('--- gitignore ---')
ign = lambda f: subprocess.run(['git', 'check-ignore', '-q', f], cwd=ROOT).returncode == 0
for f in (ENVF, ENVF + '.bak', 'me.json', 'me.json.tmp', 'data/x.json', 'drafts/x.md',
          'kb/firmen/acme.md', 'memory/MEMORY.md', 'state/t.json', 'docs/agentreports/r.json'):
    check(f'gitignore {f}', ign(f))
check('gitignore keeps template', not ign('kb/firmen/_TEMPLATE.md'))
check('gitignore keeps env example', not ign('.env.example'))

print('--- repo guard ---')


def temp_repo():
    tmp = Path(tempfile.mkdtemp())
    subprocess.run(['git', 'init', '-q', str(tmp)], check=True)
    subprocess.run(['git', 'config', 'user.email', 't@example.com'], cwd=tmp, check=True)
    subprocess.run(['git', 'config', 'user.name', 'T'], cwd=tmp, check=True)
    (tmp / 'scripts').mkdir()
    shutil.copy(ROOT / 'scripts' / 'repo_guard.py', tmp / 'scripts' / 'repo_guard.py')
    return tmp


def guard_in(tmp):
    return subprocess.run([sys.executable, str(tmp / 'scripts' / 'repo_guard.py'), '--staged'],
                          cwd=tmp, capture_output=True, text=True)


try:
    t1 = temp_repo()
    (t1 / 'note.txt').write_text('SLACK_TOKEN=' + TOK + '\n')
    subprocess.run(['git', 'add', 'note.txt'], cwd=t1, check=True)
    (t1 / 'note.txt').write_text('clean now\n')          # worktree clean, index still dirty
    check('repo_guard: staged secret with clean worktree', guard_in(t1).returncode == 1)
    shutil.rmtree(t1)

    t2 = temp_repo()
    (t2 / 'my file.md').write_text('hello ' + 'ext@' + 'company.io\n')
    subprocess.run(['git', 'add', 'my file.md'], cwd=t2, check=True)
    r = guard_in(t2)
    check('repo_guard: space in name + external mail flagged', r.returncode == 1 and 'PII' in r.stderr)
    shutil.rmtree(t2)

    t3 = temp_repo()
    (t3 / 'ok.md').write_text('internal person@' + 'startmunich.de and person@' + 'example.com\n')
    subprocess.run(['git', 'add', 'ok.md'], cwd=t3, check=True)
    check('repo_guard: internal and example addresses allowed', guard_in(t3).returncode == 0)
    (t3 / 'evil.md').write_text('person@' + 'startmunich.de' + '.evil\n')
    subprocess.run(['git', 'add', 'evil.md'], cwd=t3, check=True)
    check('repo_guard: lookalike internal domain flagged', guard_in(t3).returncode == 1)
    shutil.rmtree(t3)

    t4 = Path(tempfile.mkdtemp()); (t4 / 'scripts').mkdir()
    shutil.copy(ROOT / 'scripts' / 'repo_guard.py', t4 / 'scripts' / 'repo_guard.py')
    r = subprocess.run([sys.executable, str(t4 / 'scripts' / 'repo_guard.py'), '--staged'], cwd=t4, capture_output=True, text=True)
    check('repo_guard: blocks when git cannot read the index', r.returncode == 1)
    shutil.rmtree(t4)
except Exception as e:
    check(f'repo_guard tests ran ({type(e).__name__}: {e})', False)

print('--- classification ---')
spec = importlib.util.spec_from_file_location('fc', ROOT / 'scripts' / 'firma_check.py')
fc = importlib.util.module_from_spec(spec); spec.loader.exec_module(fc)
ME = {'crm': {'owner_user_name': 'me person', 'api_user_id': 'apime'}, 'email': 'x@startmunich.de'}
mk = lambda blocks: {'blocks': [dict(source=s, rows=r, error=e, truncated=t) for s, r, e, t in blocks]}
today = fc.NOW.strftime('%Y-%m-%d %H:%M:%S')
for name, blocks, want in [
    ('open opp', [('crm.opportunities', [{'name': 'o', 'stage': 'Qualification'}], None, False)], 'STOP'),
    ('closed opp', [('crm.opportunities', [{'name': 'o', 'stage': 'Closed Lost'}], None, False)], 'KEIN KONFLIKT GEFUNDEN'),
    ('missing stage', [('crm.opportunities', [{'name': 'o'}], None, False)], 'ABSTIMMEN'),
    ('empty stage', [('crm.opportunities', [{'name': 'o', 'stage': ''}], None, False)], 'ABSTIMMEN'),
    ('unknown stage', [('crm.opportunities', [{'name': 'o', 'stage': 'Contracting'}], None, False)], 'ABSTIMMEN'),
    ('foreign open task', [('crm.tasks', [{'name': 't', 'status': 'Not Started', 'assignedUserName': 'Other One'}], None, False)], 'STOP'),
    ('own task', [('crm.tasks', [{'name': 't', 'status': 'Not Started', 'assignedUserName': 'me person'}], None, False)], 'KEIN KONFLIKT GEFUNDEN'),
    ('foreign meeting without date', [('crm.meetings', [{'name': 'm', 'assignedUserName': 'Other'}], None, False)], 'STOP'),
    ('cancelled meeting without date', [('crm.meetings', [{'name': 'm', 'status': 'Canceled', 'assignedUserName': 'Other'}], None, False)], 'KEIN KONFLIKT GEFUNDEN'),
    ('foreign claim', [('crm.stream', [{'type': 'Post', 'by': 'Other', 'at': today, 'post': '[PARTNERSHIPS-CLAIM] owner=other person api=apiother'}], None, False)], 'STOP'),
    ('foreign claim mentioning me', [('crm.stream', [{'type': 'Post', 'by': 'Other', 'at': today, 'post': '[PARTNERSHIPS-CLAIM] owner=other person api=apiother note took over from me person'}], None, False)], 'STOP'),
    ('own claim', [('crm.stream', [{'type': 'Post', 'by': 'me person', 'at': today, 'post': '[PARTNERSHIPS-CLAIM] owner=me person api=apime'}], None, False)], 'KEIN KONFLIKT GEFUNDEN'),
    ('foreign lead', [('crm.leads', [{'name': 'l', 'status': 'New', 'assignedUserName': 'Other'}], None, False)], 'ABSTIMMEN'),
    ('dead foreign lead', [('crm.leads', [{'name': 'l', 'status': 'Dead', 'assignedUserName': 'Other'}], None, False)], 'KEIN KONFLIKT GEFUNDEN'),
    ('source error', [('slack', [], 'slack: search -> HTTP 500', False)], 'ABSTIMMEN'),
    ('truncated source', [('crm.emails', [], None, True)], 'ABSTIMMEN'),
    ('slack hits', [('slack', [{'ts': '1'}], None, False)], 'ABSTIMMEN'),
    ('nothing anywhere', [('crm.account', [], None, False)], 'KEIN KONFLIKT GEFUNDEN'),
]:
    check(f'classify: {name}', fc.classify(mk(blocks), ME)[0] == want)
check('slug: unicode safe and unique', fc.slug('Müller & Söhne') != fc.slug('Мюллер') and len(fc.slug('北京公司')) > 6)

print('--- claim helper ---')
import _claims
check('claim: parses owner', _claims.parse('[PARTNERSHIPS-CLAIM] owner=a b api=x until=2026-01-01')['owner'] == 'a b')
check('claim: none for plain post', _claims.parse('just a note') is None)
check('claim: mine by api id', _claims.is_mine('[PARTNERSHIPS-CLAIM] owner=someone api=apime', 'me person', 'apime'))
check('claim: not mine when only mentioned', not _claims.is_mine('[PARTNERSHIPS-CLAIM] owner=other api=apiother re me person', 'me person', 'apime'))
check('claim: expired is inactive', not _claims.is_active('2020-01-01 00:00:00', 24))

print('--- clients and scripts ---')
os.environ.setdefault(KEY, 'x'); os.environ.setdefault('IMAP_' + 'APP_PW', 'x'); os.environ.setdefault('SLACK_' + 'TOKEN', 'x')
import _clients as cl
check('retry-after: seconds capped', cl._retry_after({'Retry-After': '600'}) == cl.MAX_WAIT)
check('retry-after: garbage default', cl._retry_after({'Retry-After': 'soon'}) == 5.0)
check('retry-after: http-date parsed', 0 <= cl._retry_after({'Retry-After': 'Wed, 21 Oct 2015 07:28:00 GMT'}) <= cl.MAX_WAIT)
check('imap quote escapes', cl.imap_quote('a"b\\c') == '"a\\"b\\\\c"')
src = (ROOT / 'scripts' / '_clients.py').read_text()
check('clients: all 5xx retried', '500 <= e.code < 600' in src)
check('clients: timeout bounded by deadline', 'min(TO, left)' in src)
check('clients: imap FETCH failure raises', 'FETCH headers' in src)
claim_src = (ROOT / 'scripts' / 'crm_claim.py').read_text()
check('crm_claim: unpacks stream tuple', 'stream_rows, _tr = c.stream(' in claim_src)
check('crm_claim: shared claim ownership', 'is_mine(' in claim_src)
fc_src = (ROOT / 'scripts' / 'firma_check.py').read_text()
check('firma_check: marks >5 accounts truncated', 'crm.account.deep' in fc_src)
check('firma_check: records opportunity meeting errors', "block('crm.opp_meetings'" in fc_src and 'error=str(e)' in fc_src)
hc_src = (ROOT / 'scripts' / 'health_check.py').read_text()
check('health: probes all three guards', hc_src.count('_guard.py') >= 3)
check('health: quiet hides identities', "'' if QUIET else" in hc_src)

print('--- agentreport ---')
r = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'agentreport.py'), 't'], input='SLACK_TOKEN=' + TOK, capture_output=True, text=True)
check('agentreport refuses secrets', r.returncode != 0)

print(f'\n{len(fails)} failures' + (': ' + '; '.join(fails) if fails else ''))
sys.exit(1 if fails else 0)
