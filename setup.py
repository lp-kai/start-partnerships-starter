#!/usr/bin/env python3
"""setup.py - one-time local onboarding. Keys are entered HERE, hidden, never in a chat.

Run from the repo root in a real terminal:
    macOS/Linux:  python3 setup.py
    Windows:      py -3 setup.py

What it does: asks for your name, mail and four keys (hidden input), verifies every
key live (read-only calls), then writes .env and me.json atomically. Both files are
git-ignored; the script refuses to continue if they are not.
Refuses: piped/non-interactive input, key arguments on the command line, wrong cwd.
"""
import sys, os, io, json, getpass, subprocess, datetime, socket, urllib.request, urllib.parse, imaplib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'scripts'))
socket.setdefaulttimeout(20)


def die(msg):
    print(f'\nABBRUCH: {msg}', file=sys.stderr); sys.exit(2)


def check_preconditions():
    if any(a.startswith('--') for a in sys.argv[1:]):
        die('setup.py takes no arguments. Keys are typed in, never passed on the command line.')
    if not sys.stdin.isatty():
        die('setup.py needs an interactive terminal (no pipes, no AI tool call). Open a terminal and run it yourself.')
    if Path.cwd().resolve() != ROOT:
        die(f'run from the repo root: cd "{ROOT}"')
    for f in ('.env', 'me.json'):
        r = subprocess.run(['git', 'check-ignore', '-q', f], cwd=ROOT)
        if r.returncode != 0:
            die(f'{f} is NOT git-ignored - .gitignore is broken. Do not continue.')


def team():
    return json.load(io.open(ROOT / 'config' / 'team.json', encoding='utf-8'))


def http_json(url, headers, timeout=20):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def verify_crm(base, key, email):
    h = {'X-Api-Key': key}
    me = http_json(base + '/App/user', h)
    u = me.get('user', {})
    api_id, api_name, utype = u.get('id'), u.get('userName'), u.get('type')
    if utype != 'api':
        die('this key belongs to a regular user, not a dedicated API user. Ask the CRM admin for your own API user.')
    q = urllib.parse.urlencode({'where[0][type]': 'equals', 'where[0][attribute]': 'emailAddress', 'where[0][value]': email, 'select': 'id,name,userName,isActive'})
    hits = http_json(base + '/User?' + q, h).get('list', [])
    if not hits:
        q = urllib.parse.urlencode({'textFilter': email.split('@')[0].split('.')[-1], 'select': 'id,name,userName,isActive', 'maxSize': 10})
        hits = http_json(base + '/User?' + q, h).get('list', [])
    if not hits:
        die('no human CRM user found for your mail. Check the address or ask the admin.')
    if len(hits) > 1:
        print('\nSeveral CRM users match. Pick yours:')
        for i, x in enumerate(hits, 1):
            print(f'  {i}. {x.get("name")}  ({x.get("id")})')
        n = int(input('Number: ').strip() or '0')
        if not 1 <= n <= len(hits): die('invalid choice')
        owner = hits[n - 1]
    else:
        owner = hits[0]
    return {'api_user_id': api_id, 'api_user_name': api_name, 'owner_user_id': owner['id'], 'owner_user_name': owner.get('name')}


def verify_imap(host, port, user, pw):
    m = imaplib.IMAP4_SSL(host, port)
    m.login(user, pw)
    for box in ('INBOX', '[Gmail]/Sent Mail', '[Gmail]/Drafts'):
        typ, _ = m.select(box, readonly=True)
        if typ != 'OK': die(f'IMAP folder {box} not readable')
    m.logout()


def verify_slack(token):
    d = http_json('https://slack.com/api/auth.test', {'Authorization': 'Bearer ' + token})
    if not d.get('ok'): die('Slack auth.test failed')
    q = urllib.parse.urlencode({'query': 'START Munich', 'count': 1})
    s = http_json('https://slack.com/api/search.messages?' + q, {'Authorization': 'Bearer ' + token})
    if not s.get('ok'): die(f'Slack search scope missing ({s.get("error")}). Ask the Slack admin for a token with search:read.')
    return d.get('user'), d.get('team')


def verify_members(base, key):
    q = urllib.parse.urlencode({'q': 'START Munich'})
    http_json(base + '/api/v1/internal/companies?' + q, {'Authorization': 'Bearer ' + key, 'Accept': 'application/json'})


def write_atomic(path: Path, text: str, mode=0o600):
    tmp = path.with_suffix(path.suffix + '.tmp')
    with io.open(tmp, 'w', encoding='utf-8') as f:
        f.write(text); f.flush(); os.fsync(f.fileno())
    tmp.replace(path)
    if os.name != 'nt':
        os.chmod(path, mode)


def install_precommit():
    hook = ROOT / '.git' / 'hooks' / 'pre-commit'
    if not hook.parent.exists(): return False
    hook.write_text('#!/bin/sh\npython3 scripts/repo_guard.py --staged || py -3 scripts/repo_guard.py --staged\n', encoding='utf-8')
    if os.name != 'nt': os.chmod(hook, 0o755)
    return True


def main():
    check_preconditions()
    T = team()
    print('START Partnerships Starter - local setup. Nothing you type here leaves this machine except for live verification calls.\n')
    name = input('Your display name: ').strip()
    email = input('Your @startmunich.de address: ').strip().lower()
    if not email.endswith('@startmunich.de'): die('needs a startmunich.de address')

    print('\n[1/4] EspoCRM API key (your OWN API user, from the CRM admin) - input is hidden')
    espo = getpass.getpass('ESPO_API_KEY: ').strip()
    crm = verify_crm(T['crm']['base_url'], espo, email); print('  CRM PASS')

    print('\n[2/4] Gmail app password (Google account > Security > App passwords; enter WITHOUT spaces)')
    imap_pw = getpass.getpass('IMAP_APP_PW: ').replace(' ', '')
    verify_imap(T['imap']['host'], T['imap']['port'], email, imap_pw); print('  IMAP PASS')

    print('\n[3/4] Slack user token (xoxp-..., read scopes only, via the Slack admin)')
    slack = getpass.getpass('SLACK_TOKEN: ').strip()
    verify_slack(slack); print('  Slack PASS')

    print('\n[4/4] Members platform API key (optional - press Enter to skip)')
    members = getpass.getpass('MEMBERS_API_KEY: ').strip()
    if members:
        verify_members(T['members']['base_url'], members); print('  Members PASS')
    else:
        print('  Members SKIP')

    env = f'ESPO_API_KEY={espo}\nIMAP_APP_PW={imap_pw}\nSLACK_TOKEN={slack}\nMEMBERS_API_KEY={members}\n'
    write_atomic(ROOT / '.env', env)
    me = {'schema_version': 1, 'display_name': name, 'email': email, 'crm': crm,
          'setup_completed_at': datetime.datetime.now().astimezone().isoformat(timespec='seconds')}
    write_atomic(ROOT / 'me.json', json.dumps(me, indent=2, ensure_ascii=False) + '\n', 0o644)
    del espo, imap_pw, slack, members, env
    for f in ('.env', 'me.json'):
        if subprocess.run(['git', 'check-ignore', '-q', f], cwd=ROOT).returncode != 0:
            die(f'{f} written but NOT ignored - remove it now and fix .gitignore')
    hook = install_precommit()
    print(f'\nDone. .env and me.json written (git-ignored{", pre-commit guard installed" if hook else ""}).')
    print('Next: python3 scripts/health_check.py   then   python3 scripts/firma_check.py --tutorial')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        die('cancelled')
