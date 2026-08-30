"""_config.py - team.json, facts.json, me.json with light schema checks. Never touches secrets."""
import io, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent

def _load(p, required_keys):
    if not p.exists():
        raise RuntimeError(f'{p.name} missing' + (' - run setup.py' if p.name == 'me.json' else ''))
    d = json.load(io.open(p, encoding='utf-8'))
    miss = [k for k in required_keys if k not in d]
    if miss:
        raise RuntimeError(f'{p.name}: missing keys {miss}')
    return d

def team():  return _load(ROOT / 'config' / 'team.json', ['crm', 'imap', 'members', 'required_sources', 'features', 'limits'])
def facts(): return _load(ROOT / 'facts.json', ['version', 'rtsh', 'rtss', 'anti_patterns'])
def me():    return _load(ROOT / 'me.json', ['display_name', 'email', 'crm'])
