#!/usr/bin/env python3
"""setup.py - one-time local onboarding. Keys are typed HERE, hidden, never in a chat.

Run from the repo root in a real terminal:
    macOS/Linux:  python3 setup.py
    Windows:      py -3 setup.py

Asks for your name, mail and keys (hidden input), verifies every key live (read-only calls),
then writes .env and me.json atomically with 0600. Both are git-ignored; the script stops if not.
Refuses: piped/non-interactive input, ANY command-line argument, wrong cwd, missing git/python.
"""
import sys, os, io, json, getpass, subprocess, datetime, socket, shutil, urllib.request, urllib.parse, urllib.error, imaplib, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'scripts'))
socket.setdefaulttimeout(20)
PY = 'py -3' if sys.platform.startswith('win') else 'python3'


def die(msg):
    print(f'\nABBRUCH: {msg}', file=sys.stderr); sys.exit(2)


def check_preconditions():
    if sys.argv[1:]:
        die('setup.py takes no arguments. Keys are typed in, never passed on the command line.')
    if not sys.stdin.isatty():
        die('setup.py needs an interactive terminal (no pipes, no AI tool call). Open a terminal and run it yourself.')
    if sys.version_info < (3, 10): die(f'Python 3.10+ needed, found {sys.version.split()[0]}.')
    if not shutil.which('git'): die('git is not installed. Install git first (it protects your keys via check-ignore).')
    if Path.cwd().resolve() != ROOT: die(f'run from the repo root: cd "{ROOT}"')
    if not (ROOT / '.git').exists(): die('this folder is not a git clone. Clone the repo instead of copying files.')
    for f in ('.env', 'me.json'):
        if subprocess.run(['git', 'check-ignore', '-q', f], cwd=ROOT).returncode != 0:
            die(f'{f} is NOT git-ignored - .gitignore is broken. Do not continue.')
    if not shutil.which('node'):
        print('  note: node not found. The Claude Code guard hooks need node; everything else works without it.')


def team():
    return json.load(io.open(ROOT / 'config' / 'team.json', encoding='utf-8'))


def http_json(url, headers, what):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as r:
            return json.loads(r.read().decode('utf-8', 'replace'))
    except urllib.error.HTTPError as e:
        die(f'{what}: HTTP {e.code}. ' + ('Key rejected - check it with the admin.' if e.code in (401, 403) else 'Service problem, try again later.'))
    except (urllib.error.URLError, socket.timeout) as e:
        die(f'{what}: no connection ({type(e).__name__}). Check network/VPN and try again.')
    except ValueError:
        die(f'{what}: unexpected response (not JSON).')


def choose(items, label):
    while True:
        print(f'\nSeveral {label} match. Pick yours:')
        for i, x in enumerate(items, 1): print(f'  {i}. {x}')
        a = input('Number: ').strip()
        if a.isdigit() and 1 <= int(a) <= len(items): return int(a) - 1
        print('  please type a number from the list')


def verify_crm(base, key, email):
    h = {'X-Api-Key': key}
    u = http_json(base + '/App/user', h, 'CRM /App/user').get('user', {})
    if u.get('type') != 'api':
        die('this key belongs to a regular user, not a dedicated API user. Ask the CRM admin for your own API user.')
    sel = 'id,name,userName,emailAddress,type,isActive'
    q = urllib.parse.urlencode({'where[0][type]': 'equals', 'where[0][attribute]': 'emailAddress', 'where[0][value]': email, 'select': sel, 'maxSize': 20})
    hits = [x for x in http_json(base + '/User?' + q, h, 'CRM user lookup').get('list', []) if x.get('type') != 'api' and x.get('isActive')]
    hits = [x for x in hits if (x.get('emailAddress') or '').lower() == email]
    if not hits:
        q = urllib.parse.urlencode({'textFilter': email.split('@')[0].split('.')[-1], 'select': sel, 'maxSize': 20})
        cand = [x for x in http_json(base + '/User?' + q, h, 'CRM user search').get('list', []) if x.get('type') != 'api' and x.get('isActive')]
        if not cand: die('no active human CRM user found for your mail. Check the address or ask the admin to add your mail to your CRM user.')
        print('\n  No user with exactly your mail. Candidates by name (verify carefully):')
        owner = cand[choose([f'{x.get("name")}  <{x.get("emailAddress") or "no mail"}>  ({x.get("userName")})' for x in cand], 'CRM users')]
    elif len(hits) > 1:
        owner = hits[choose([f'{x.get("name")}  ({x.get("userName")})' for x in hits], 'CRM users')]
    else:
        owner = hits[0]
    return {'api_user_id': u.get('id'), 'api_user_name': u.get('userName'), 'owner_user_id': owner['id'], 'owner_user_name': owner.get('name')}


def verify_imap(host, port, user, pw):
    try:
        m = imaplib.IMAP4_SSL(host, port); m.login(user, pw)
    except imaplib.IMAP4.error:
        die('IMAP login failed. Use a Google APP password (16 chars, without spaces), not your normal password, and check that IMAP is enabled in Gmail settings.')
    except (socket.timeout, OSError) as e:
        die(f'IMAP: no connection ({type(e).__name__}).')
    found = {'sent': None, 'drafts': None}
    typ, boxes = m.list()
    for b in boxes or []:
        s = b.decode('utf-8', 'replace')
        mm = re.match(r'\((?P<flags>[^)]*)\)\s+"?[^"\s]*"?\s+(?P<name>.+)$', s)
        if not mm: continue
        if '\\Sent' in mm.group('flags'): found['sent'] = mm.group('name').strip().strip('"')
        if '\\Drafts' in mm.group('flags'): found['drafts'] = mm.group('name').strip().strip('"')
    for key, box in [('inbox', 'INBOX')] + list(found.items()):
        if not box: die(f'IMAP: no folder with the {key} flag found. Enable "Show in IMAP" for that folder in Gmail settings.')
        if m.select(('"%s"' % box) if ' ' in box else box, readonly=True)[0] != 'OK': die(f'IMAP folder {box} not readable')
    m.logout()


def verify_slack(token):
    h = {'Authorization': 'Bearer ' + token}
    d = http_json('https://slack.com/api/auth.test', h, 'Slack auth.test')
    if not d.get('ok'): die(f'Slack token rejected ({d.get("error")}).')
    s = http_json('https://slack.com/api/search.messages?' + urllib.parse.urlencode({'query': 'START Munich', 'count': 1}), h, 'Slack search')
    if not s.get('ok'): die(f'Slack search scope missing ({s.get("error")}). Ask the Slack admin for a token with search:read.')


def verify_members(base, key):
    http_json(base + '/api/v1/internal/companies?' + urllib.parse.urlencode({'q': 'START Munich'}), {'Authorization': 'Bearer ' + key, 'Accept': 'application/json'}, 'Members API')


def write_secret(path: Path, text: str):
    """Create the temp file with 0600 from the first byte, then rename atomically."""
    tmp = path.with_name(path.name + '.tmp')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(text); f.flush(); os.fsync(f.fileno())
    tmp.replace(path)
    if os.name != 'nt': os.chmod(path, 0o600)


def install_precommit():
    hook = ROOT / '.git' / 'hooks' / 'pre-commit'
    hook.write_text('#!/bin/sh\npython3 scripts/repo_guard.py --staged 2>/dev/null || py -3 scripts/repo_guard.py --staged\n', encoding='utf-8')
    if os.name != 'nt': os.chmod(hook, 0o755)


def main():
    check_preconditions()
    T = team()
    print('START Partnerships Starter - local setup.\nNothing you type here leaves this machine except the live verification calls to CRM, Gmail, Slack and Members.\n')
    name = input('Your display name: ').strip()
    if not name: die('name needed')
    email = input('Your @startmunich.de address: ').strip().lower()
    if not email.endswith('@startmunich.de') or '@' not in email[1:]: die('needs a valid startmunich.de address')

    print('\n[1/4] EspoCRM API key (your OWN API user, from the CRM admin). Input is hidden; paste and press Enter.')
    espo = getpass.getpass('ESPO_API_KEY: ').strip()
    if not espo: die('empty key')
    crm = verify_crm(T['crm']['base_url'], espo, email); print(f'  CRM PASS (you are {crm["owner_user_name"]})')

    print('\n[2/4] Gmail app password (Google account > Security > 2-step > App passwords). Spaces are removed automatically.')
    imap_pw = getpass.getpass('IMAP_APP_PW: ').replace(' ', '')
    if not imap_pw: die('empty password')
    verify_imap(T['imap']['host'], T['imap']['port'], email, imap_pw); print('  IMAP PASS')

    print('\n[3/4] Slack user token (xoxp-..., read scopes only, via the Slack admin)')
    slack = getpass.getpass('SLACK_TOKEN: ').strip()
    if not slack: die('empty token')
    verify_slack(slack); print('  Slack PASS')

    print('\n[4/4] Members platform API key (optional - press Enter to skip)')
    members = getpass.getpass('MEMBERS_API_KEY: ').strip()
    if members: verify_members(T['members']['base_url'], members); print('  Members PASS')
    else: print('  Members SKIP')

    write_secret(ROOT / '.env', f'ESPO_API_KEY={espo}\nIMAP_APP_PW={imap_pw}\nSLACK_TOKEN={slack}\nMEMBERS_API_KEY={members}\n')
    me = {'schema_version': 1, 'display_name': name, 'email': email, 'crm': crm,
          'setup_completed_at': datetime.datetime.now().astimezone().isoformat(timespec='seconds')}
    write_secret(ROOT / 'me.json', json.dumps(me, indent=2, ensure_ascii=False) + '\n')
    del espo, imap_pw, slack, members
    for f in ('.env', 'me.json'):
        if subprocess.run(['git', 'check-ignore', '-q', f], cwd=ROOT).returncode != 0:
            die(f'{f} written but NOT ignored - delete it now and fix .gitignore')
    install_precommit()
    if os.name == 'nt':
        print('\n  Windows note: file permissions are not restricted automatically. Keep this folder in your user profile, not on a shared drive.')
    print(f'\nDone. .env and me.json written (git-ignored, pre-commit guard installed).')
    print(f'Next:  {PY} scripts/health_check.py   then   {PY} scripts/firma_check.py --tutorial')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        die('cancelled')
    except (EOFError,):
        die('input ended unexpectedly')
    except Exception as e:
        die(f'{type(e).__name__}: {e}')
