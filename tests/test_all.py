"""Synthetic tests: no secrets, no live calls. Run: python3 tests/test_all.py"""
import subprocess, sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; H = ROOT / '.claude' / 'hooks'
fails = 0
KEY = 'ESPO_' + 'API_KEY'   # assembled so the file itself never looks like a leak


def check(name, ok):
    global fails; print(('PASS ' if ok else 'FAIL ') + name); fails += 0 if ok else 1


def hook(script, payload, arg=None):
    cmd = [sys.executable, str(H / script)] + ([arg] if arg else [])
    return subprocess.run(cmd, input=json.dumps(payload), capture_output=True, text=True).returncode


B = lambda c: {'tool_name': 'Bash', 'tool_input': {'command': c}}
check('lint selftest', subprocess.run([sys.executable, str(ROOT / 'scripts' / 'draft_lint.py'), '--selbsttest'], capture_output=True).returncode == 0)
check('send_guard blocks smtplib', hook('send_guard.py', B('python3 -c "import smtplib"')) == 2)
check('send_guard blocks compound', hook('send_guard.py', B('cat x; python3 -c "import smtplib"')) == 2)
check('send_guard allows grep', hook('send_guard.py', B('grep -rn smtplib scripts/')) == 0)
check('send_guard allows gmail_draft', hook('send_guard.py', B('python3 scripts/gmail_draft.py --to a@b.c --subject s --body-file f')) == 0)
check('secret_guard blocks cat env', hook('secret_leak_guard.py', B('cat ' + '.env')) == 2)
check('secret_guard allows env.example', hook('secret_leak_guard.py', B('cat .env.example')) == 0)
check('secret_guard blocks echo key', hook('secret_leak_guard.py', B('echo $' + KEY)) == 2)
check('secret_guard blocks setup.py via tool', hook('secret_leak_guard.py', B('python3 setup.py')) == 2)
check('crm_guard blocks DELETE', hook('crm_write_guard.py', B('curl -X DELETE https://espo.dedicated.startmunich.de/api/v1/Account/1 -H "X-Api-Key: x"')) == 2)
check('crm_guard allows GET', hook('crm_write_guard.py', B('curl https://espo.dedicated.startmunich.de/api/v1/Account?maxSize=1 -H "X-Api-Key: x"')) == 0)
check('crm_guard allows claim script', hook('crm_write_guard.py', B('python3 scripts/crm_claim.py 123')) == 0)
check('hook fails open on garbage', subprocess.run([sys.executable, str(H / 'send_guard.py')], input='not json', capture_output=True, text=True).returncode == 0)
ign = lambda f: subprocess.run(['git', 'check-ignore', '-q', f], cwd=ROOT).returncode == 0
for f in ('.env', '.env.bak', 'me.json', 'data/x.json', 'drafts/x.md', 'kb/firmen/acme.md', 'memory/MEMORY.md', 'state/t.json', 'docs/agentreports/r.json'):
    check(f'gitignore {f}', ign(f))
check('gitignore keeps template', not ign('kb/firmen/_TEMPLATE.md'))
check('gitignore keeps env.example', not ign('.env.example'))
r = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'agentreport.py'), 't'], input='SLACK_TOKEN=' + 'xoxp-' + '1234567890-abcdefghijk', capture_output=True, text=True)
check('agentreport refuses secrets', r.returncode != 0)
print(f'\n{fails} failures'); sys.exit(1 if fails else 0)
