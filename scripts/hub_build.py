#!/usr/bin/env python3
"""hub_build.py - renders YOUR local company files into one HTML page: data/hub.html (git-ignored).
No login, no account, no cloud: open the file in a browser. Rebuild any time.
    python3 scripts/hub_build.py
Sorted by conflict status (STOP / ABSTIMMEN / KEIN KONFLIKT GEFUNDEN), newest check first."""
import io, re, html, datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
FILES = sorted((ROOT / 'kb' / 'firmen').glob('*.md'))
ORDER = {'STOP': 0, 'ABSTIMMEN': 1, 'KEIN KONFLIKT GEFUNDEN': 2}
COLOR = {'STOP': '#ff5c7a', 'ABSTIMMEN': '#ffb648', 'KEIN KONFLIKT GEFUNDEN': '#3ddc97'}

def parse(p):
    t = p.read_text(encoding='utf-8')
    if p.name.startswith('_'): return None
    name = (re.search(r'^# (.+)$', t, re.M) or [None, p.stem])[1]
    st = (re.search(r'## Status: \*\*(.+?)\*\*', t) or [None, 'UNGEPRUEFT'])[1]
    why = (re.search(r'\*\*.+?\*\*[:\s-]+(.+)', t) or [None, ''])[1]
    checked = (re.search(r'> Checked (.+?) by', t) or [None, ''])[1]
    nxt = (re.search(r'## Next step\n((?:- .*\n?)+)', t) or [None, ''])[1]
    return {'name': name, 'status': st, 'why': why, 'checked': checked, 'next': nxt.strip(), 'file': p.name, 'body': t}

rows = [r for r in (parse(p) for p in FILES) if r]
rows.sort(key=lambda r: (ORDER.get(r['status'], 9), r['checked']), reverse=False)
now = datetime.datetime.now().strftime('%d.%m.%Y %H:%M')
cards = ''.join(f'''<details class="c"><summary><span class="st" style="background:{COLOR.get(r['status'],'#888')}22;color:{COLOR.get(r['status'],'#ccc')}">{html.escape(r['status'])}</span>
<b>{html.escape(r['name'])}</b> <span class="meta">{html.escape(r['checked'])} · {html.escape(r['why'])}</span></summary>
<pre>{html.escape(r['body'])}</pre></details>''' for r in rows)
page = f'''<!doctype html><meta charset="utf-8"><title>Partnerships Hub</title>
<style>body{{background:#00002c;color:#f4f4fc;font-family:-apple-system,"Segoe UI",sans-serif;margin:0;padding:32px clamp(16px,4vw,56px)}}
h1{{text-transform:uppercase;font-weight:900;margin:0 0 4px}} h1 i{{color:#d0006f;font-style:normal}} .eb{{font-family:ui-monospace,monospace;font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#8eeeff}}
.c{{background:#011152;border:1px solid rgba(255,255,255,.12);border-radius:3px;margin:10px 0;padding:10px 14px}} summary{{cursor:pointer;display:flex;gap:12px;align-items:center}}
.st{{font-family:ui-monospace,monospace;font-size:11px;padding:3px 8px;border-radius:2px;white-space:nowrap}} .meta{{color:#b8badf;font-size:13px}} pre{{white-space:pre-wrap;font-size:13px;color:#d8d9ee;margin-top:10px}}
.sum{{color:#b8badf;margin:0 0 20px}}</style>
<p class="eb">Partnerships · Hub · Stand {now} · {len(rows)} Firmen · lokal</p><h1>Outreach-Kommando<i>.</i></h1>
<p class="sum">STOP {sum(r['status']=='STOP' for r in rows)} · ABSTIMMEN {sum(r['status']=='ABSTIMMEN' for r in rows)} · KEIN KONFLIKT {sum(r['status']=='KEIN KONFLIKT GEFUNDEN' for r in rows)}. Quelle: kb/firmen/*.md (aus firma_check.py). Neu bauen: python3 scripts/hub_build.py</p>
{cards or '<p class="sum">Noch keine Akten. Erst: python3 scripts/firma_check.py --tutorial</p>'}'''
(ROOT / 'data').mkdir(exist_ok=True)
out = ROOT / 'data' / 'hub.html'; io.open(out, 'w', encoding='utf-8').write(page)
print(f'{out.relative_to(ROOT)}: {len(rows)} companies')
