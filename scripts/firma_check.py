#!/usr/bin/env python3
"""firma_check.py - ONE company, every source, live. READ-ONLY.
    python3 scripts/firma_check.py "Acme GmbH" [--domain acme.com]
    python3 scripts/firma_check.py --tutorial
Writes raw findings to data/checks/ and a readable file to kb/firmen/<slug>.md (both git-ignored).
Every source block records: time, exact method, hit count, truncation. Zero hits are reported as
'0 hits with method X on date Y' - never as 'does not exist'. Conflict status is deterministic.
"""
import sys, io, json, re, datetime, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parent.parent
from _config import team, me
from _clients import CRM, IMAP, Slack, Members, SourceError

T = team(); L = T['limits']
NOW = datetime.datetime.now().astimezone()
STAMP = NOW.strftime('%d.%m.%Y %H:%M')

def slug(s): return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:50]

def block(source, method, hits, rows, truncated=False, note=None, error=None):
    return {'source': source, 'method': method, 'time': STAMP, 'hits': hits, 'truncated': truncated,
            'rows': rows, 'note': note, 'error': error}

def check(name, domain):
    ME = me(); out = {'company': name, 'domain': domain, 'checked_at': NOW.isoformat(timespec='seconds'), 'by': ME['email'], 'blocks': []}
    # ---- CRM ----
    try:
        c = CRM()
        accs = c.list('Account', [{'type': 'equals', 'attribute': 'name', 'value': name}], select='id,name,assignedUserName,modifiedAt') \
            or c.list('Account', select='id,name,assignedUserName,modifiedAt', textFilter=name, max_size=10, max_pages=1)
        out['blocks'].append(block('crm.account', f'GET /Account name="{name}" + textFilter', len(accs), accs[:10]))
        for a in accs[:3]:
            aid = a['id']
            for ent, path in (('contacts', f'/Account/{aid}/contacts'), ('opportunities', f'/Account/{aid}/opportunities'), ('meetings', f'/Account/{aid}/meetings'), ('tasks', f'/Account/{aid}/tasks')):
                try:
                    rows = c.get(path, maxSize=20).get('list', [])
                    out['blocks'].append(block(f'crm.{ent}', f'GET {path}', len(rows), rows[:20]))
                except SourceError as e:
                    out['blocks'].append(block(f'crm.{ent}', f'GET {path}', 0, [], error=str(e)))
            try:
                st = c.stream('Account', aid)
                out['blocks'].append(block('crm.stream', f'GET /Account/{aid}/stream', len(st), [{'type': s.get('type'), 'by': s.get('createdByName'), 'at': s.get('createdAt'), 'post': (s.get('post') or '')[:200]} for s in st]))
            except SourceError as e:
                out['blocks'].append(block('crm.stream', 'GET stream', 0, [], error=str(e)))
            mails = c.list('Email', [{'type': 'equals', 'attribute': 'parentId', 'value': aid}], select='id,name,dateSent,fromString,status', max_size=25, max_pages=2)
            out['blocks'].append(block('crm.emails', f'GET /Email parentId={aid} (metadata only)', len(mails), mails, truncated=len(mails) >= 50))
        leads = c.list('Lead', select='id,name,accountName,status,assignedUserName,modifiedAt', textFilter=name, max_size=10, max_pages=1)
        out['blocks'].append(block('crm.leads', f'GET /Lead textFilter="{name}"', len(leads), leads))
    except SourceError as e:
        out['blocks'].append(block('crm', 'GET', 0, [], error=str(e)))
    # ---- IMAP ----
    try:
        m = IMAP(ME['email']); term = domain or name
        for box in ('INBOX', '[Gmail]/Sent Mail'):
            n, rows = m.search(box, term, L['imap_max_hits'])
            out['blocks'].append(block(f'imap.{box}', f'SEARCH OR FROM/TO "{term}" (headers only)', n, rows, truncated=n > len(rows)))
        m.close()
    except Exception as e:
        out['blocks'].append(block('imap', 'SEARCH', 0, [], error=str(e) if isinstance(e, SourceError) else type(e).__name__))
    # ---- Slack ----
    try:
        s = Slack(); q = f'"{name}"' + (f' OR {domain}' if domain else '')
        total, rows = s.search(q, L['slack_max_hits'])
        out['blocks'].append(block('slack', f'search.messages q={q}', total, rows, truncated=total > len(rows),
                                  note='first page may be noise - read all rows before concluding'))
    except Exception as e:
        out['blocks'].append(block('slack', 'search.messages', 0, [], error=str(e) if isinstance(e, SourceError) else type(e).__name__))
    # ---- Members ----
    try:
        mem = Members(); rows = mem.companies(name, L['members_max_hits'])
        if rows is None: out['blocks'].append(block('members', 'skipped (no key)', 0, [], note='SKIP'))
        else: out['blocks'].append(block('members', f'GET /internal/companies q="{name}" (current AND former)', len(rows), rows))
    except Exception as e:
        out['blocks'].append(block('members', 'GET', 0, [], error=str(e) if isinstance(e, SourceError) else type(e).__name__))
    out['status'] = classify(out, ME)
    return out

def classify(out, ME):
    B = {b['source']: b for b in out['blocks']}
    opps = [o for b in out['blocks'] if b['source'] == 'crm.opportunities' for o in b['rows']]
    if any(o.get('stage') not in ('Closed Won', 'Closed Lost') for o in opps):
        return 'STOP', 'open opportunity in CRM'
    accs = B.get('crm.account', {}).get('rows', [])
    six = (NOW - datetime.timedelta(days=182)).strftime('%Y-%m-%d')
    for a in accs:
        owner = a.get('assignedUserName') or ''
        if owner and owner != ME['crm']['owner_user_name']:
            recent = (a.get('modifiedAt') or '') >= six
            return ('STOP', f'account owned by {owner}, active in last 6 months') if recent else ('ABSTIMMEN', f'account owned by {owner}, older activity')
    if any(b.get('error') for b in out['blocks']):
        return 'ABSTIMMEN', 'at least one source failed - result is incomplete'
    return 'KEIN KONFLIKT GEFUNDEN', 'no evidence in the checked sources - not a guarantee'

def write(out):
    (ROOT / 'data' / 'checks').mkdir(parents=True, exist_ok=True); (ROOT / 'kb' / 'firmen').mkdir(parents=True, exist_ok=True)
    s = slug(out['company']); raw = ROOT / 'data' / 'checks' / f'{NOW.strftime("%Y%m%d-%H%M")}-{s}.json'
    io.open(raw, 'w', encoding='utf-8').write(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    st, why = out['status']
    md = [f'# {out["company"]}', f'', f'> Checked {STAMP} by {out["by"]} · raw: `{raw.relative_to(ROOT)}`', f'',
          f'## Status: **{st}** - {why}', '']
    for b in out['blocks']:
        line = f'- **{b["source"]}** · {b["method"]} · {b["time"]} · '
        line += f'ERROR {b["error"]}' if b.get('error') else (f'{b["hits"]} hits' + (' (truncated)' if b['truncated'] else '') if b['hits'] else f'0 hits with this method on {b["time"]}')
        if b.get('note'): line += f' · {b["note"]}'
        md.append(line)
        for r in b['rows'][:8]:
            md.append('    - ' + json.dumps(r, ensure_ascii=False, default=str)[:220])
    md += ['', '## Next step', '- (fill in after human review; see rules/CHECKLISTEN.md W1)', '']
    p = ROOT / 'kb' / 'firmen' / f'{s}.md'; io.open(p, 'w', encoding='utf-8').write('\n'.join(md))
    return p

def tutorial():
    print('Guided first company check. Everything is read-only; nothing is written to the CRM.\n')
    name = input('Company name: ').strip(); domain = input('Official domain (optional): ').strip() or None
    if input(f'You may check "{name}" in the Partnerships context? [y/N] ').lower() != 'y': return 2
    out = check(name, domain); p = write(out)
    st, why = out['status']
    print(f'\nStatus: {st} - {why}\nFile: {p.relative_to(ROOT)}')
    for b in out['blocks']:
        print(f'  {b["source"]:20} {("ERROR " + b["error"]) if b.get("error") else str(b["hits"]) + " hits"}')
    print('\nRead the file. Note: a zero is "0 hits with that method today", not "they do not exist".')
    if input('Understood sources, status and limits? [y/N] ').lower() == 'y':
        (ROOT / 'state').mkdir(exist_ok=True)
        io.open(ROOT / 'state' / 'tutorial.json', 'w').write(json.dumps({'done_at': NOW.isoformat(), 'company': name}))
        print('Tutorial complete. Normal flow: check -> human review -> (claim, once enabled) -> draft -> lint -> gmail draft -> you send.')
    return 0

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('company', nargs='?'); ap.add_argument('--domain'); ap.add_argument('--tutorial', action='store_true')
    a = ap.parse_args()
    if a.tutorial: sys.exit(tutorial())
    if not a.company: ap.error('company name or --tutorial')
    out = check(a.company, a.domain); p = write(out); st, why = out['status']
    print(f'{st} - {why}\n{p.relative_to(ROOT)}')
