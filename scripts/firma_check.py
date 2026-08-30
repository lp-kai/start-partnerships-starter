#!/usr/bin/env python3
"""firma_check.py - ONE company, every source, live. READ-ONLY.
    python3 scripts/firma_check.py "Acme GmbH" [--domain acme.com]
    python3 scripts/firma_check.py --tutorial
Writes raw findings to data/checks/ and a readable file to kb/firmen/<slug>.md (both git-ignored).
Every block records time, exact method, hit count and truncation. Zero hits are reported as
'0 hits with method X on date Y', never as 'does not exist'.
Conflict status is deterministic and conservative: any other person's open task, meeting, lead,
recent post or claim => at least ABSTIMMEN; any failed or truncated source => never KEIN KONFLIKT.
"""
import sys, io, json, re, datetime, argparse, hashlib, unicodedata
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parent.parent
from _cli import run, preflight, die
from _claims import is_mine, is_active, MARKER

NOW = datetime.datetime.now().astimezone()
STAMP = NOW.strftime('%d.%m.%Y %H:%M')
SIX_MONTHS = (NOW - datetime.timedelta(days=182)).strftime('%Y-%m-%d')
OPEN_STAGES = {'Prospecting', 'Qualification', 'Proposal', 'Negotiation'}
CLOSED_STAGES = {'Closed Won', 'Closed Lost'}   # anything else counts as open/unknown


def slug(s):
    base = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    base = re.sub(r'[^a-z0-9]+', '-', base.lower()).strip('-')[:40] or 'firma'
    return base + '-' + hashlib.sha1(s.encode()).hexdigest()[:6]


def block(source, method, hits, rows, truncated=False, note=None, error=None):
    return {'source': source, 'method': method, 'time': STAMP, 'hits': hits, 'truncated': truncated,
            'rows': rows, 'note': note, 'error': error}


def check(name, domain):
    from _config import team, me
    from _clients import CRM, IMAP, Slack, Members, SourceError
    T, ME = team(), me(); L = T['limits']
    out = {'company': name, 'domain': domain, 'checked_at': NOW.isoformat(timespec='seconds'), 'by': ME['email'], 'blocks': []}
    B = out['blocks']
    # ---- CRM ----
    try:
        c = CRM()
        SEL_ACC = 'id,name,assignedUserId,assignedUserName,modifiedAt'
        exact, e_tr = c.list('Account', [{'type': 'equals', 'attribute': 'name', 'value': name}], select=SEL_ACC, max_total=50)
        text, t_tr = c.list('Account', select=SEL_ACC, textFilter=name, max_total=50)
        seen, accs = set(), []
        for a in exact + text:
            if a['id'] not in seen: seen.add(a['id']); accs.append(a)
        B.append(block('crm.account', f'GET /Account name="{name}" UNION textFilter', len(accs), accs, truncated=t_tr or e_tr))
        if len(accs) > 5:
            B.append(block('crm.account.deep', f'only the first 5 of {len(accs)} accounts were examined in depth', len(accs), [], truncated=True))
        for a in accs[:5]:
            aid = a['id']
            for link, sel in (('contacts', 'id,name,assignedUserName,modifiedAt'),
                              ('opportunities', 'id,name,stage,amount,closeDate,assignedUserName,assignedUsersNames,modifiedAt'),
                              ('meetings', 'id,name,dateStart,status,assignedUserName'),
                              ('tasks', 'id,name,status,dateEnd,assignedUserName')):
                try:
                    rows, tr = c.related('Account', aid, link, select=sel)
                    B.append(block(f'crm.{link}', f'GET /Account/{aid}/{link}', len(rows), rows, truncated=tr))
                except SourceError as e:
                    B.append(block(f'crm.{link}', f'GET /Account/{aid}/{link}', 0, [], error=str(e)))
            # meetings often hang on the opportunity, not the account
            for o in [r for b in B if b['source'] == 'crm.opportunities' for r in b['rows']]:
                try:
                    rows, tr = c.related('Opportunity', o['id'], 'meetings', select='id,name,dateStart,status,assignedUserName')
                    if rows: B.append(block('crm.opp_meetings', f'GET /Opportunity/{o["id"]}/meetings', len(rows), rows, truncated=tr))
                except SourceError as e:
                    B.append(block('crm.opp_meetings', f'GET /Opportunity/{o["id"]}/meetings', 0, [], error=str(e)))
            try:
                st, tr = c.stream('Account', aid)
                B.append(block('crm.stream', f'GET /Account/{aid}/stream', len(st), [{'type': s.get('type'), 'by': s.get('createdByName'), 'at': s.get('createdAt'), 'post': (s.get('post') or '')[:200]} for s in st], truncated=tr))
            except SourceError as e:
                B.append(block('crm.stream', 'GET stream', 0, [], error=str(e)))
            mails, tr = c.list('Email', [{'type': 'equals', 'attribute': 'parentId', 'value': aid}], select='id,name,dateSent,fromString,status', max_total=100)
            B.append(block('crm.emails', f'GET /Email parentId={aid} (metadata only)', len(mails), mails, truncated=tr))
        leads, tr = c.list('Lead', select='id,name,accountName,status,assignedUserName,modifiedAt', textFilter=name, max_total=50)
        B.append(block('crm.leads', f'GET /Lead textFilter="{name}"', len(leads), leads, truncated=tr))
    except SourceError as e:
        B.append(block('crm', 'GET', 0, [], error=str(e)))
    # ---- IMAP ----
    try:
        m = IMAP(ME['email']); term = domain or name
        try:
            for key in ('inbox', 'sent'):
                n, rows, tr = m.search(key, term, L['imap_max_hits'])
                B.append(block(f'imap.{key}', f'SEARCH OR FROM/TO "{term}" in {m.folders.get(key)} (headers only)', n, rows, truncated=tr))
        finally:
            m.close()
    except Exception as e:
        B.append(block('imap', 'SEARCH', 0, [], error=str(e) if isinstance(e, SourceError) else type(e).__name__))
    # ---- Slack: name and domain separately, deduped, paged ----
    try:
        s = Slack(); rows, seen, total, tr = [], set(), 0, False
        for q in [f'"{name}"'] + ([domain] if domain else []):
            t_, r_, tr_ = s.search(q, L['slack_max_hits']); total += t_; tr = tr or tr_
            for r in r_:
                if r['ts'] not in seen: seen.add(r['ts']); rows.append(r)
        B.append(block('slack', f'search.messages q="{name}"' + (f' + q={domain}' if domain else '') + ' (paged)', total, rows, truncated=tr, note='read all rows before concluding'))
    except Exception as e:
        B.append(block('slack', 'search.messages', 0, [], error=str(e) if isinstance(e, SourceError) else type(e).__name__))
    # ---- Members ----
    try:
        mem = Members(); rows = mem.companies(name, L['members_max_hits'])
        if rows is None: B.append(block('members', 'skipped (no key)', 0, [], note='SKIP'))
        else: B.append(block('members', f'GET /internal/companies q="{name}" (current AND former)', len(rows), rows))
    except Exception as e:
        B.append(block('members', 'GET', 0, [], error=str(e) if isinstance(e, SourceError) else type(e).__name__))
    out['status'] = classify(out, ME)
    return out


def classify(out, ME):
    """Returns (status, reason). Conservative on purpose."""
    me_name = (ME['crm'].get('owner_user_name') or '').lower(); me_api = ME['crm'].get('api_user_id')
    rows = lambda src: [r for b in out['blocks'] if b['source'] == src for r in b['rows']]
    other = lambda r: (r.get('assignedUserName') or '').lower() not in ('', me_name)
    errors = [b['source'] for b in out['blocks'] if b.get('error')]
    truncated = [b['source'] for b in out['blocks'] if b.get('truncated')]
    # STOP: open deal, or a foreign active claim, or another person's open task/meeting
    for o in rows('crm.opportunities'):
        st = (o.get('stage') or '').strip()
        if not st: return 'ABSTIMMEN', f'opportunity "{o.get("name")}" without a stage - incomplete data'
        if st in OPEN_STAGES: return 'STOP', f'open opportunity "{o.get("name")}" ({st})'
        if st not in CLOSED_STAGES: return 'ABSTIMMEN', f'opportunity "{o.get("name")}" in unknown stage "{st}" - treat as open until checked'
    for s in rows('crm.stream'):
        p = s.get('post') or ''
        if MARKER in p and is_active(s.get('at'), 48, NOW) and not is_mine(p, me_name, me_api):
            return 'STOP', f'active claim by someone else: {p[:80]}'
    for t in rows('crm.tasks'):
        if other(t) and t.get('status') not in ('Completed', 'Canceled'): return 'STOP', f'open task by {t.get("assignedUserName")}: {t.get("name")}'
    for m in rows('crm.meetings') + rows('crm.opp_meetings'):
        if m.get('status') in ('Canceled', 'Not Held'): continue
        if other(m) and (m.get('dateStart') or '9999') >= SIX_MONTHS: return 'STOP', f'meeting by {m.get("assignedUserName")}: {m.get("name")}' + ('' if m.get('dateStart') else ' (no date - treated as recent)')
    # ABSTIMMEN: foreign owner, foreign lead, recent foreign stream activity, any incomplete source
    for a in rows('crm.account'):
        if other(a): return 'ABSTIMMEN', f'account owned by {a.get("assignedUserName")}' + (' (activity in last 6 months)' if (a.get('modifiedAt') or '') >= SIX_MONTHS else '')
    for l in rows('crm.leads'):
        if other(l) and l.get('status') not in ('Dead', 'Converted'): return 'ABSTIMMEN', f'lead "{l.get("name")}" owned by {l.get("assignedUserName")}'
    for s in rows('crm.stream'):
        if s.get('type') in ('Post', 'EmailSent', 'EmailReceived') and (s.get('at') or '') >= SIX_MONTHS and (s.get('by') or '').lower() != me_name:
            return 'ABSTIMMEN', f'recent {s.get("type")} by {s.get("by")} in the account stream'
    if errors: return 'ABSTIMMEN', f'source failed: {", ".join(errors)} - result is incomplete'
    if truncated: return 'ABSTIMMEN', f'source truncated: {", ".join(truncated)} - read the raw file before deciding'
    if rows('slack') or rows('members') or rows('imap.inbox') or rows('imap.sent'):
        return 'ABSTIMMEN', 'no CRM conflict, but there are Slack/mail/member hits - read them before reaching out'
    return 'KEIN KONFLIKT GEFUNDEN', 'no evidence in the checked sources - not a guarantee, ask the team'


def write(out):
    (ROOT / 'data' / 'checks').mkdir(parents=True, exist_ok=True); (ROOT / 'kb' / 'firmen').mkdir(parents=True, exist_ok=True)
    s = slug(out['company']); raw = ROOT / 'data' / 'checks' / f'{NOW.strftime("%Y%m%d-%H%M%S")}-{s}.json'
    io.open(raw, 'w', encoding='utf-8').write(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    st, why = out['status']
    md = [f'# {out["company"]}', '', f'> Checked {STAMP} by {out["by"]} · raw: `{raw.relative_to(ROOT)}`', '',
          f'## Status: **{st}**: {why}', '']
    for b in out['blocks']:
        line = f'- **{b["source"]}** · {b["method"]} · {b["time"]} · '
        line += f'ERROR {b["error"]}' if b.get('error') else (f'{b["hits"]} hits' + (' (TRUNCATED)' if b['truncated'] else '') if b['hits'] else f'0 hits with this method on {b["time"]}')
        if b.get('note'): line += f' · {b["note"]}'
        md.append(line)
        for r in b['rows'][:8]: md.append('    - ' + json.dumps(r, ensure_ascii=False, default=str)[:220])
    md += ['', '## Next step', '- (fill in after human review; see rules/CHECKLISTEN.md W1)', '']
    p = ROOT / 'kb' / 'firmen' / f'{s}.md'
    if p.exists():  # keep history instead of overwriting
        hist = ROOT / 'kb' / 'firmen' / '_history'; hist.mkdir(exist_ok=True)
        p.rename(hist / f'{s}.{NOW.strftime("%Y%m%d-%H%M%S")}.md')
    io.open(p, 'w', encoding='utf-8').write('\n'.join(md))
    return p


def ask_yes(q):
    while True:
        a = input(q + ' [y/n] ').strip().lower()
        if a in ('y', 'yes', 'j', 'ja'): return True
        if a in ('n', 'no', 'nein', ''): return False


def tutorial():
    print('Guided first company check. Everything is read-only; nothing is written to the CRM.\n')
    name = input('Company name: ').strip()
    if not name: die('no company name')
    domain = input('Official domain (optional): ').strip() or None
    if not ask_yes(f'You may check "{name}" in the Partnerships context?'): return 2
    out = check(name, domain); p = write(out); st, why = out['status']
    print(f'\nStatus: {st}: {why}\nFile: {p.relative_to(ROOT)}')
    for b in out['blocks']:
        print(f'  {b["source"]:20} {("ERROR " + b["error"]) if b.get("error") else str(b["hits"]) + " hits" + (" (truncated)" if b["truncated"] else "")}')
    print('\nRead the file. A zero means "0 hits with that method today", not "they do not exist".')
    if ask_yes('Understood sources, status and limits?'):
        (ROOT / 'state').mkdir(exist_ok=True)
        io.open(ROOT / 'state' / 'tutorial.json', 'w').write(json.dumps({'done_at': NOW.isoformat(), 'company': name}))
        print('Tutorial complete. Flow: check -> human review -> (claim, once enabled) -> draft -> lint -> gmail draft -> you send.')
    return 0


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('company', nargs='?'); ap.add_argument('--domain'); ap.add_argument('--tutorial', action='store_true')
    a = ap.parse_args()
    preflight(need_identity=True)
    if a.tutorial: return tutorial()
    if not a.company: ap.error('company name or --tutorial')
    out = check(a.company, a.domain); p = write(out); st, why = out['status']
    print(f'{st}: {why}\n{p.relative_to(ROOT)}'); return 0


if __name__ == '__main__':
    run(main)
