#!/usr/bin/env python3
"""gmail_draft.py - creates a DRAFT in your own Gmail via IMAP APPEND. There is no send code here.
Identity from me.json, app password from .env (lazy). Subject AND body are linted first.
    python3 scripts/gmail_draft.py --to x@y.com --subject "..." --body-file drafts/x.txt [--lint-ok preis]"""
import sys, io, time, argparse, imaplib, email.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _config import team, me
from _creds import get

def find_drafts_folder(m):
    typ, boxes = m.list()
    for b in boxes or []:
        s = b.decode() if isinstance(b, bytes) else b
        if '\\Drafts' in s: return s.split(' "/" ')[-1].strip().strip('"')
    return '[Gmail]/Drafts'

def create_draft(to, subject, body, lint_ok=()):
    from draft_lint import lade_fakten, linte, REGELN
    known = {r[0] for r in REGELN}; unk = set(lint_ok) - known
    if unk: sys.exit(f'unknown lint rule ids: {sorted(unk)} (valid: {sorted(known)})')
    issues = linte(subject + '\n' + body, lade_fakten(), skip=set(lint_ok))
    if issues:
        print('DRAFT NOT CREATED - draft_lint:', file=sys.stderr)
        for rid, msg in issues: print(f'  [{rid}] {msg}', file=sys.stderr)
        sys.exit(1)
    T, ME = team(), me()
    msg = MIMEMultipart('alternative'); msg['From'] = ME['email']; msg['To'] = to; msg['Subject'] = subject
    msg['Date'] = email.utils.formatdate(); msg.attach(MIMEText(body, 'plain', 'utf-8'))
    m = imaplib.IMAP4_SSL(T['imap']['host'], T['imap']['port']); m.login(ME['email'], get('IMAP_APP_PW'))
    folder = find_drafts_folder(m); m.append(folder, '', imaplib.Time2Internaldate(time.time()), msg.as_bytes()); m.logout()
    print(f'Draft created in {folder}: {to} | {subject}' + (f'  (lint exceptions: {", ".join(lint_ok)})' if lint_ok else ''))

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--to', required=True); ap.add_argument('--subject', required=True)
    ap.add_argument('--body-file', required=True); ap.add_argument('--lint-ok', default=''); a = ap.parse_args()
    create_draft(a.to, a.subject, io.open(a.body_file, encoding='utf-8').read(), [x.strip() for x in a.lint_ok.split(',') if x.strip()])
