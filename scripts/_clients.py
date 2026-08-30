"""_clients.py - small read-only clients: CRM (EspoCRM), IMAP, Slack, Members.
Timeouts everywhere, 429 handling with Retry-After, pagination, redaction of error bodies.
No write method exists here on purpose (except nothing). Writes live only in crm_claim.py."""
import json, time, random, socket, imaplib, email, email.header, urllib.request, urllib.parse, urllib.error
from _creds import get, redact
from _config import team

T = team(); TO = T['limits']['http_timeout_s']
socket.setdefaulttimeout(TO)


class SourceError(Exception):
    """Typed failure: carries method, status and date so a failure never reads as 'no results'."""
    def __init__(self, source, method, status, date=None):
        self.source, self.method, self.status = source, method, status
        self.date = date or time.strftime('%d.%m.%Y')
        super().__init__(f'{source}: {method} -> {status} (Stand {self.date})')


def _get_json(url, headers, source, method, retries=3):
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=TO) as r:
                return json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                wait = float(e.headers.get('Retry-After') or 5) + random.uniform(0, 1.5)
                time.sleep(wait); continue
            raise SourceError(source, method, f'HTTP {e.code}')
        except (urllib.error.URLError, socket.timeout) as e:
            if attempt < retries - 1:
                time.sleep(1 + attempt); continue
            raise SourceError(source, method, redact(f'network: {e}'))


# ---------------- CRM ----------------
class CRM:
    def __init__(self):
        self.base = T['crm']['base_url']
        self.h = {'X-Api-Key': get('ESPO_API_KEY')}

    def get(self, path, **params):
        url = self.base + path + ('?' + urllib.parse.urlencode(params, doseq=True) if params else '')
        return _get_json(url, self.h, 'crm', f'GET {path}')

    def me(self):
        return self.get('/App/user').get('user', {})

    def list(self, entity, where=None, select=None, max_size=50, max_pages=4, **extra):
        out, offset = [], 0
        for _ in range(max_pages):
            p = {'maxSize': max_size, 'offset': offset}
            if select: p['select'] = select
            p.update(extra)
            for i, w in enumerate(where or []):
                for k, v in w.items(): p[f'where[{i}][{k}]'] = v
            d = self.get(f'/{entity}', **p)
            out += d.get('list', [])
            if len(d.get('list', [])) < max_size: break
            offset += max_size
        return out

    def stream(self, entity, rid, max_size=30):
        return self.get(f'/{entity}/{rid}/stream', maxSize=max_size).get('list', [])


# ---------------- IMAP (read-only) ----------------
class IMAP:
    def __init__(self, user):
        self.m = imaplib.IMAP4_SSL(T['imap']['host'], T['imap']['port'])
        self.m.login(user, get('IMAP_APP_PW'))

    def search(self, box, term, limit):
        """Header-only search; returns (count, [ {date, from, to, subject} ])."""
        typ, _ = self.m.select(box, readonly=True)
        if typ != 'OK': raise SourceError('imap', f'EXAMINE {box}', typ)
        typ, data = self.m.search(None, 'OR', f'FROM "{term}"', f'TO "{term}"')
        ids = data[0].split() if typ == 'OK' else []
        rows = []
        for i in ids[-limit:]:
            typ, msg = self.m.fetch(i, '(BODY.PEEK[HEADER.FIELDS (DATE FROM TO SUBJECT)])')
            if typ != 'OK': continue
            hdr = email.message_from_bytes(msg[0][1])
            rows.append({k.lower(): str(email.header.make_header(email.header.decode_header(hdr.get(k, '')))) for k in ('Date', 'From', 'To', 'Subject')})
        return len(ids), rows

    def close(self):
        try: self.m.logout()
        except Exception: pass


# ---------------- Slack (read-only) ----------------
class Slack:
    def __init__(self):
        self.h = {'Authorization': 'Bearer ' + get('SLACK_TOKEN')}

    def call(self, method, **params):
        d = _get_json('https://slack.com/api/' + method + '?' + urllib.parse.urlencode(params), self.h, 'slack', method)
        if not d.get('ok'): raise SourceError('slack', method, d.get('error', 'not ok'))
        return d

    def auth(self): return self.call('auth.test')

    def search(self, query, count):
        d = self.call('search.messages', query=query, count=count, sort='timestamp')
        ms = d.get('messages', {})
        return ms.get('total', 0), [{'channel': m.get('channel', {}).get('name'), 'user': m.get('username'),
                                    'ts': m.get('ts'), 'text': (m.get('text') or '')[:280]} for m in ms.get('matches', [])[:count]]


# ---------------- Members (read-only, search only, no full export) ----------------
class Members:
    def __init__(self):
        key = get('MEMBERS_API_KEY', required=False)
        self.enabled = bool(key)
        self.h = {'Authorization': 'Bearer ' + (key or ''), 'Accept': 'application/json'}
        self.base = T['members']['base_url']

    def companies(self, q, limit):
        if not self.enabled: return None
        d = _get_json(self.base + '/api/v1/internal/companies?' + urllib.parse.urlencode({'q': q}), self.h, 'members', 'GET /internal/companies')
        rows = d if isinstance(d, list) else d.get('data', d.get('list', []))
        return rows[:limit]
