"""_claims.py - one place that decides whether a CRM claim note belongs to me.

Used by firma_check.classify() and by crm_claim.py, so both answer identically. The owner is
parsed from the structured fields (owner=, api=), never guessed by looking for a name somewhere
in the free text: a foreign claim may well mention your name.
"""
import re, datetime

MARKER = '[PARTNERSHIPS-CLAIM]'


def parse(post):
    """Returns {'owner':str,'api':str,'until':str} for a claim note, else None."""
    if not post or MARKER not in post:
        return None
    owner = re.search(r'owner=(.+?)(?=\s+\w+=|$)', post)
    api = re.search(r'api=(\S+)', post)
    until = re.search(r'until=([\d:\- ]+)', post)
    return {'owner': (owner.group(1).strip() if owner else ''),
            'api': (api.group(1).strip() if api else ''),
            'until': (until.group(1).strip() if until else '')}


def is_mine(post, me_owner_name, me_api_id):
    c = parse(post)
    if not c:
        return False
    if c['api'] and me_api_id:
        return c['api'] == me_api_id
    return bool(c['owner']) and c['owner'].strip().lower() == (me_owner_name or '').strip().lower()


def is_active(created_at, ttl_hours=24, now=None):
    """A claim counts as active while it is younger than the TTL (with a small grace window)."""
    now = now or datetime.datetime.now().astimezone()
    if not created_at:
        return True                      # unknown age: treat as active, conservative on purpose
    cutoff = (now - datetime.timedelta(hours=ttl_hours)).strftime('%Y-%m-%d %H:%M:%S')
    return str(created_at)[:19] >= cutoff[:19]
