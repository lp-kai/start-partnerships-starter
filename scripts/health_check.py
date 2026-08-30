#!/usr/bin/env python3
"""health_check.py - are all data paths reachable, under MY identity? READ-ONLY.
PASS / SKIP / FAIL per line. Exit 0 = every required source works. It does NOT mean 'everything is fine'.
Never prints key values or HTTP bodies."""
import sys, os, io, json, subprocess, socket
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parent.parent
socket.setdefaulttimeout(15)
R = []
def rep(st, area, txt): R.append(st); print(f'[{st:4}] {area:14} {txt}')

def main():
    quiet = '--quiet' in sys.argv
    rep('PASS' if sys.version_info >= (3, 10) else 'FAIL', 'python', sys.version.split()[0])
    for f in ('.env', 'me.json'):
        ign = subprocess.run(['git', 'check-ignore', '-q', f], cwd=ROOT).returncode == 0
        rep('PASS' if (ROOT / f).exists() and ign else 'FAIL', 'local files', f'{f} ' + ('exists, git-ignored' if ign else 'NOT IGNORED or missing - run setup.py'))
    try:
        from _config import team, facts, me
        T, F, ME = team(), facts(), me()
        rep('PASS', 'config', f'team.json, facts.json v{F["version"]}, me.json for {ME["display_name"]}')
    except Exception as e:
        rep('FAIL', 'config', str(e)); return finish()
    from _clients import CRM, IMAP, Slack, Members, SourceError
    if not T['crm']['base_url'].startswith('https://'): rep('FAIL', 'crm', 'base_url is not https')
    try:
        c = CRM(); u = c.me()
        same = u.get('id') == ME['crm']['api_user_id']
        rep('PASS' if same else 'FAIL', 'crm identity', f'API user {u.get("userName")}' + ('' if same else ' does not match me.json - rerun setup.py'))
        owner = c.get(f'/User/{ME["crm"]["owner_user_id"]}', select='isActive,name')
        rep('PASS' if owner.get('isActive') else 'FAIL', 'crm owner', f'{owner.get("name")} active={owner.get("isActive")}')
        for ent in ('Account', 'Contact', 'Lead', 'Opportunity', 'Email', 'Meeting', 'Task'):
            c.get(f'/{ent}', maxSize=1, select='id')
        rep('PASS', 'crm read', 'Account Contact Lead Opportunity Email Meeting Task')
    except SourceError as e: rep('FAIL', 'crm', str(e))
    except Exception as e: rep('FAIL', 'crm', type(e).__name__)
    try:
        m = IMAP(ME['email']); m.close(); rep('PASS', 'imap', f'{ME["email"]} inbox/sent/drafts readable')
    except Exception as e: rep('FAIL', 'imap', type(e).__name__)
    try:
        s = Slack(); a = s.auth(); s.search('START Munich', 1); rep('PASS', 'slack', f'{a.get("user")} @ {a.get("team")}, search ok')
    except Exception as e: rep('FAIL', 'slack', str(e) if isinstance(e, SourceError) else type(e).__name__)
    mem = Members()
    if not mem.enabled: rep('SKIP', 'members', 'no key (optional)')
    else:
        try: mem.companies('START Munich', 1); rep('PASS', 'members', 'company search ok')
        except Exception as e: rep('FAIL', 'members', str(e) if isinstance(e, SourceError) else type(e).__name__)
    r = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'draft_lint.py'), '--selbsttest'], capture_output=True, text=True)
    rep('PASS' if r.returncode == 0 else 'FAIL', 'draft lint', r.stdout.strip().splitlines()[-1] if r.stdout else 'no output')
    hooks = [h for h in ('secret_leak_guard.py', 'send_guard.py', 'crm_write_guard.py', 'draft_file_lint.py', 'raw_report_gate.py') if not (ROOT / '.claude' / 'hooks' / h).exists()]
    rep('PASS' if not hooks else 'FAIL', 'hooks', 'all present' if not hooks else f'missing {hooks}')
    pc = ROOT / '.git' / 'hooks' / 'pre-commit'
    rep('PASS' if pc.exists() else 'SKIP', 'pre-commit', 'repo_guard installed' if pc.exists() else 'not installed (setup.py does it)')
    return finish()

def finish():
    n = {k: R.count(k) for k in ('PASS', 'SKIP', 'FAIL')}
    print(f'\n{len(R)} checks: {n["PASS"]} PASS, {n["SKIP"]} SKIP, {n["FAIL"]} FAIL')
    return 1 if n['FAIL'] else 0

if __name__ == '__main__':
    sys.exit(main())
