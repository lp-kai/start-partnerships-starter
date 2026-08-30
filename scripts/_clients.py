"""_clients.py - small read-only clients: CRM (EspoCRM), IMAP, Slack, Members.
Timeouts, capped Retry-After, total deadline, 5xx retry, pagination, redaction of error bodies.
No write method exists here. Writes live only in crm_claim.py."""
import json, time, random, socket, imaplib, email, email.header, email.utils, re
import urllib.request, urllib.parse, urllib.error
from _creds import get, redact
from _config import team

T = team(); TO = T['limits']['http_timeout_s']
MAX_WAIT = 30          # seconds, cap for Retry-After
DEADLINE = 90          # seconds, total per request incl. retries
socket.setdefaulttimeout(TO)


class SourceError(Exception):
    """Typed failure with method, status and date, so a failure never reads as 'no results'."""
    def __init__(self, source, method, status, date=None):
        self.source, self.method, self.status = source, method, status
        self.date = date or time.strftime('%d.%m.%Y')
        super().__init__(f'{source}: {method} -> {status} (Stand {self.date})')


def _retry_after(h):
    v = (h.get('Retry-After') or '').strip()
    if not v: return 5.0
    if v.isdigit(): return min(float(v), MAX_WAIT)
    try:
        dt = email.utils.parsedate_to_datetime(v)
        return max(0.0, min((dt.timestamp() - time.time()), MAX_WAIT))
    except Exception:
        return 5.0


def _get_json(url, headers, source, method, retries=3):
    start = time.time()
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=TO) as r:
                raw = r.read().decode('utf-8', errors='replace')
            try:
                return json.loads(raw)
            except ValueError:
                raise SourceError(source, method, 'invalid JSON response')
        except urllib.error.HTTPError as e:
            retryable = e.code == 429 or e.code in (502, 503, 504)
            if retryable and attempt < retries - 1 and time.time() - start < DEADLINE:
                time.sleep(_retry_after(e.headers) + random.uniform(0, 1.5)); continue
            raise SourceError(source, method, f'HTTP {e.code}')
        except (urllib.error.URLError, socket.timeout, ConnectionError) as e:
            if attempt < retries - 1 and time.time() - start < DEADLINE:
                time.sleep(1 + attempt); continue
            raise SourceError(source, method, redact(f'network: {type(e).__name__}'))
    raise SourceError(source, method, 'deadline exceeded')


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

    def list(self, entity, where=None, select=None, max_size=50, max_total=200, **extra):
        """Pages until max_total; returns (rows, truncated)."""
        out, offset = [], 0
        while offset < max_total:
            p = {'maxSize': max_size, 'offset': offset}
            if select: p['select'] = select
            p.update(extra)
            for i, w in enumerate(where or []):
                for k, v in w.items(): p[f'where[{i}][{k}]'] = v
            d = self.get(f'/{entity}', **p); rows = d.get('list', [])
            out += rows
            if len(rows) < max_size: return out, False
            offset += max_size
        return out, True

    def related(self, entity, rid, link, select=None, max_total=100):
        out, offset, size = [], 0, 50
        while offset < max_total:
            p = {'maxSize': size, 'offset': offset}
            if select: p['select'] = select
            rows = self.get(f'/{entity}/{rid}/{link}', **p).get('list', [])
            out += rows
            if len(rows) < size: return out, False
            offset += size
        return out, True

    def stream(self, entity, rid, max_total=100):
        return self.related(entity, rid, 'stream', max_total=max_total)


# ---------------- IMAP (read-only) ----------------
def imap_quote(s):
    """IMAP quoted-string: escape backslash and quote; UTF-8 via CHARSET."""
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


class IMAP:
    def __init__(self, user):
        self.m = imaplib.IMAP4_SSL(T['imap']['host'], T['imap']['port'])
        self.m.login(user, get('IMAP_APP_PW'))
        self.folders = self._discover()

    def _discover(self):
        """Language-independent: read \\Sent and \\Drafts flags from LIST."""
        f = {'inbox': 'INBOX', 'sent': None, 'drafts': None}
        typ, boxes = self.m.list()
        for b in boxes or []:
            s = b.decode('utf-8', 'replace') if isinstance(b, bytes) else b
            m = re.match(r'\((?P<flags>[^)]*)\)\s+"?(?P<delim>[^"\s]*)"?\s+(?P<name>.+)$', s)
            if not m: continue
            name = m.group('name').strip().strip('"'); flags = m.group('flags')
            if '\\Sent' in flags: f['sent'] = name
            if '\\Drafts' in flags: f['drafts'] = name
        return f

    def examine(self, key):
        box = self.folders.get(key)
        if not box: raise SourceError('imap', f'LIST {key}', 'folder not found')
        typ, _ = self.m.select(imap_quote(box) if ' ' in box else box, readonly=True)
        if typ != 'OK': raise SourceError('imap', f'EXAMINE {box}', typ)
        return box

    def search(self, key, term, limit):
        """Header-only search; returns (count, rows, truncated)."""
        box = self.examine(key)
        q = imap_quote(term)
        try:
            typ, data = self.m.search('UTF-8', 'OR', 'FROM', q, 'TO', q)
        except (imaplib.IMAP4.error, UnicodeEncodeError):
            typ, data = self.m.search(None, 'OR', 'FROM', q.encode('ascii', 'ignore').decode(), 'TO', q.encode('ascii', 'ignore').decode())
        ids = data[0].split() if typ == 'OK' else []
        rows = []
        for i in ids[-limit:]:
            typ, msg = self.m.fetch(i, '(BODY.PEEK[HEADER.FIELDS (DATE FROM TO SUBJECT)])')
            if typ != 'OK' or not msg or not msg[0]: continue
            hdr = email.message_from_bytes(msg[0][1])
            rows.append({k.lower(): str(email.header.make_header(email.header.decode_header(hdr.get(k, '')))) for k in ('Date', 'From', 'To', 'Subject')})
        return len(ids), rows, len(ids) > limit

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

    def search(self, query, max_hits):
        """Pages search.messages up to max_hits; returns (total, rows, truncated)."""
        rows, page, total = [], 1, 0
        while len(rows) < max_hits:
            d = self.call('search.messages', query=query, count=min(100, max_hits - len(rows)), page=page, sort='timestamp')
            ms = d.get('messages', {}); total = ms.get('total', 0)
            for m in ms.get('matches', []):
                rows.append({'channel': (m.get('channel') or {}).get('name'), 'user': m.get('username'),
                             'ts': m.get('ts'), 'permalink': m.get('permalink'), 'text': (m.get('text') or '')[:280]})
            pg = ms.get('paging', {}) or ms.get('pagination', {})
            if page >= (pg.get('pages') or pg.get('page_count') or 1): break
            page += 1
        return total, rows[:max_hits], total > len(rows)


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
