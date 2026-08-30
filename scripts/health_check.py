#!/usr/bin/env python3
"""health_check.py - are the data paths reachable, under MY identity? READ-ONLY.
PASS / SKIP / FAIL per line. Exit 0 = every source in config required_sources works.
It does NOT mean 'everything is fine'. --quiet prints one summary line and no identities."""
import sys, io, json, subprocess, socket, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parent.parent
from _cli import run, git_ignored, PY
socket.setdefaulttimeout(15)
QUIET = '--quiet' in sys.argv
R = []


def rep(st, area, txt):
    R.append((st, area)); QUIET or print(f'[{st:4}] {area:14} {txt}')


def probe_hook(name, payload, expect):
    """Run a guard through the same node runner Claude Code uses; True if exit code matches."""
    runner = ROOT / '.claude' / 'hooks' / 'run_python.cjs'
    if not shutil.which('node'): return None
    r = subprocess.run(['node', str(runner), str(ROOT / '.claude' / 'hooks' / name)], input=json.dumps(payload), capture_output=True, text=True, timeout=30)
    return r.returncode == expect


def main():
    rep('PASS' if sys.version_info >= (3, 10) else 'FAIL', 'python', sys.version.split()[0])
    rep('PASS' if shutil.which('git') else 'FAIL', 'git', 'found' if shutil.which('git') else 'missing')
    for f in ('.env', 'me.json'):
        ex, ig = (ROOT / f).exists(), git_ignored(f)
        rep('PASS' if ex and ig else 'FAIL', 'local files', f'{f}: ' + ('exists' if ex else f'MISSING - run {PY} setup.py') + ', ' + ('git-ignored' if ig else 'NOT IGNORED'))
    try:
        from _config import team, facts, me
        T, F, ME = team(), facts(), me()
        rep('PASS', 'config', f'team.json, facts.json v{F["version"]}, me.json' + ('' if QUIET else f' for {ME["display_name"]}'))
    except Exception as e:
        rep('FAIL', 'config', str(e)); return finish([])
    req = set(T.get('required_sources', []))
    from _clients import CRM, IMAP, Slack, Members, SourceError
    if not T['crm']['base_url'].startswith('https://'): rep('FAIL', 'crm', 'base_url is not https')
    try:
        c = CRM(); u = c.me()
        same = u.get('id') == ME['crm']['api_user_id']
        rep('PASS' if same else 'FAIL', 'crm identity', 'API user matches me.json' if same else f'API user does not match me.json - rerun {PY} setup.py')
        owner = c.get(f'/User/{ME["crm"]["owner_user_id"]}', select='isActive,name')
        rep('PASS' if owner.get('isActive') else 'FAIL', 'crm owner', 'owner active' if owner.get('isActive') else 'owner inactive')
        for ent in ('Account', 'Contact', 'Lead', 'Opportunity', 'Email', 'Meeting', 'Task'):
            c.get(f'/{ent}', maxSize=1, select='id')
        rep('PASS', 'crm read', 'Account Contact Lead Opportunity Email Meeting Task')
    except SourceError as e: rep('FAIL', 'crm', str(e))
    except Exception as e: rep('FAIL', 'crm', type(e).__name__)
    try:
        m = IMAP(ME['email'])
        try:
            for k in ('inbox', 'sent', 'drafts'): m.examine(k)
            rep('PASS', 'imap', 'inbox/sent/drafts selected read-only' + ('' if QUIET else f' ({m.folders["sent"]}, {m.folders["drafts"]})'))
        finally: m.close()
    except Exception as e: rep('FAIL', 'imap', str(e) if isinstance(e, SourceError) else type(e).__name__)
    try:
        s = Slack(); a = s.auth(); s.search('START Munich', 1); rep('PASS', 'slack', 'auth + search ok' + ('' if QUIET else f' ({a.get("user")} @ {a.get("team")})'))
    except Exception as e: rep('FAIL', 'slack', str(e) if isinstance(e, SourceError) else type(e).__name__)
    mem = Members()
    if not mem.enabled: rep('FAIL' if 'members' in req else 'SKIP', 'members', 'no key' + (' (required by team config)' if 'members' in req else ' (optional)'))
    else:
        try: mem.companies('START Munich', 1); rep('PASS', 'members', 'company search ok')
        except Exception as e: rep('FAIL', 'members', str(e) if isinstance(e, SourceError) else type(e).__name__)
    r = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'draft_lint.py'), '--selbsttest'], capture_output=True, text=True)
    rep('PASS' if r.returncode == 0 else 'FAIL', 'draft lint', r.stdout.strip().splitlines()[-1] if r.stdout else 'no output')
    missing = [h for h in ('secret_leak_guard.py', 'send_guard.py', 'crm_write_guard.py', 'draft_file_lint.py', 'raw_report_gate.py', 'run_python.cjs') if not (ROOT / '.claude' / 'hooks' / h).exists()]
    rep('PASS' if not missing else 'FAIL', 'hooks files', 'all present' if not missing else f'missing {missing}')
    probes = [('send_guard.py', 'python3 -c "import smtplib"', 2), ('send_guard.py', 'git status', 0),
              ('secret_leak_guard.py', 'cat .env', 2), ('secret_leak_guard.py', 'cat README.md', 0),
              ('crm_write_guard.py', 'curl -X DELETE https://espo.example/api/v1/Account/1 -H "X-Api-Key: x"', 2),
              ('crm_write_guard.py', 'curl https://espo.example/api/v1/Account -H "X-Api-Key: x"', 0)]
    res = [probe_hook(h, {'tool_name': 'Bash', 'tool_input': {'command': c}}, e) for h, c, e in probes]
    if any(r is None for r in res): rep('FAIL', 'hooks runtime', 'node missing - Claude Code guards will NOT run. Install node.')
    else: rep('PASS' if all(res) else 'FAIL', 'hooks runtime', f'{sum(1 for r in res if r)}/{len(res)} guard probes correct' + ('' if all(res) else ' - a guard is not working'))
    pc = ROOT / '.git' / 'hooks' / 'pre-commit'
    rep('PASS' if pc.exists() else 'FAIL', 'pre-commit', 'repo_guard installed' if pc.exists() else f'not installed - run {PY} setup.py')
    return finish(req)


def finish(req):
    n = {k: sum(1 for s, _ in R if s == k) for k in ('PASS', 'SKIP', 'FAIL')}
    fails = [a for s, a in R if s == 'FAIL']
    print(f'health: {len(R)} checks, {n["PASS"]} PASS, {n["SKIP"]} SKIP, {n["FAIL"]} FAIL' + (f' -> {", ".join(fails)}' if fails else ''))
    return 1 if fails else 0


if __name__ == '__main__':
    run(main)
