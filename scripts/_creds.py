"""_creds.py - the ONLY way scripts read secrets. Sources: process env, then .env in the repo root.
No personal defaults, no ~/dotfiles fallback, fully lazy. Never prints a value."""
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
_cache = None

def _load():
    global _cache
    if _cache is None:
        vals = {}
        p = ROOT / '.env'
        if p.exists():
            for line in p.read_text(encoding='utf-8', errors='ignore').splitlines():
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1); vals[k.strip()] = v.strip().strip('"').strip("'")
        _cache = vals
    return _cache

def get(name, required=True):
    v = os.environ.get(name) or _load().get(name)
    if required and not v:
        raise RuntimeError(f'{name} missing. Run setup.py in a terminal (never type keys into the chat).')
    return v

def redact(text):
    """Remove any known secret value from a string before it is printed or stored."""
    for v in list(_load().values()) + [os.environ.get(k, '') for k in ('ESPO_API_KEY','IMAP_APP_PW','SLACK_TOKEN','MEMBERS_API_KEY')]:
        if v and len(v) >= 8:
            text = text.replace(v, '<REDACTED>')
    return text
