#!/usr/bin/env python3
"""crm_claim.py - the ONLY CRM write path, and it is OFF until the CRM admin enables it
(config/team.json features.crm_claim_enabled). Dry-run by default.
Purpose: before drafting, claim an account for 24h via a standardized Account note so two
people never contact the same company. Never creates/edits/deletes any other record."""
import sys, json, io, datetime, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parent.parent
from _config import team, me
from _clients import CRM
ap = argparse.ArgumentParser(); ap.add_argument('account_id'); ap.add_argument('--write', action='store_true'); a = ap.parse_args()
T, ME = team(), me()
if not T['features']['crm_claim_enabled']:
    sys.exit('Claims are disabled in config/team.json until the CRM admin approves the note-only role. Nothing written.')
c = CRM(); acc = c.get(f'/Account/{a.account_id}', select='name')
stream_rows, _tr = c.stream('Account', a.account_id)
recent = [s for s in stream_rows if '[PARTNERSHIPS-CLAIM]' in (s.get('post') or '')]
for s in recent:
    if ME['crm']['owner_user_name'] not in (s.get('post') or '') and (s.get('createdAt') or '') > (datetime.datetime.utcnow() - datetime.timedelta(hours=T['features']['claim_ttl_hours'])).isoformat():
        sys.exit(f'STOP: active claim by someone else on {acc["name"]}: {s["post"][:120]}')
post = f'[PARTNERSHIPS-CLAIM] owner={ME["crm"]["owner_user_name"]} api={ME["crm"]["api_user_id"]} until={(datetime.datetime.now()+datetime.timedelta(hours=T["features"]["claim_ttl_hours"])).strftime("%Y-%m-%d %H:%M")}'
print(('DRY-RUN would post: ' if not a.write else 'Posting: ') + post)
if a.write:
    if input('Confirm claim [y/N] ').lower() != 'y': sys.exit('cancelled')
    import urllib.request
    req = urllib.request.Request(c.base + '/Note', data=json.dumps({'type': 'Post', 'parentType': 'Account', 'parentId': a.account_id, 'post': post}).encode(), headers={**c.h, 'Content-Type': 'application/json'}, method='POST')
    urllib.request.urlopen(req, timeout=20)
    (ROOT / 'state' / 'claims').mkdir(parents=True, exist_ok=True)
    io.open(ROOT / 'state' / 'claims' / f'{a.account_id}.json', 'w').write(json.dumps({'post': post, 'at': datetime.datetime.now().isoformat()}))
    print('claimed')
