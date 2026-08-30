#!/usr/bin/env python3
"""gmail_draft.py - creates a DRAFT in your own Gmail via IMAP APPEND. There is no send code here.
Identity from me.json, app password from .env (lazy). Subject AND body are linted first.
APPEND status is verified; on failure nothing is claimed.
    python3 scripts/gmail_draft.py --to name@example.com --subject "..." --body-file drafts/x.txt [--lint-ok preis]"""
import sys, io, time, argparse, email.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _cli import run, preflight, die


def create_draft(to, subject, body, lint_ok=()):
    from draft_lint import lade_fakten, linte, REGELN
    from _config import me
    from _clients import IMAP
    known = {r[0] for r in REGELN}; unk = set(lint_ok) - known
    if unk: die(f'unknown lint rule ids: {sorted(unk)} (valid: {sorted(known)})')
    issues = linte(subject + '\n' + body, lade_fakten(), skip=set(lint_ok))
    if issues:
        print('DRAFT NOT CREATED - draft_lint:', file=sys.stderr)
        for rid, msg in issues: print(f'  [{rid}] {msg}', file=sys.stderr)
        sys.exit(1)
    ME = me()
    msg = MIMEMultipart('alternative'); msg['From'] = ME['email']; msg['To'] = to; msg['Subject'] = subject
    msg['Date'] = email.utils.formatdate(); msg.attach(MIMEText(body, 'plain', 'utf-8'))
    m = IMAP(ME['email'])
    try:
        folder = m.folders.get('drafts')
        if not folder: die('no Drafts folder found via IMAP LIST. Enable "Show in IMAP" for Drafts in Gmail settings.')
        typ, resp = m.m.append(folder, '', time.strftime('"%d-%b-%Y %H:%M:%S +0000"', time.gmtime()), msg.as_bytes())
        if typ != 'OK': die(f'IMAP APPEND to {folder} failed: {typ} {resp[0].decode("utf-8", "ignore") if resp and resp[0] else ""}')
    finally:
        m.close()
    print(f'Draft created in {folder}: {to} | {subject}' + (f'  (lint exceptions: {", ".join(lint_ok)})' if lint_ok else ''))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--to', required=True); ap.add_argument('--subject', required=True)
    ap.add_argument('--body-file', required=True); ap.add_argument('--lint-ok', default=''); a = ap.parse_args()
    preflight(need_identity=True)
    if not Path(a.body_file).exists(): die(f'body file not found: {a.body_file}')
    create_draft(a.to, a.subject, io.open(a.body_file, encoding='utf-8').read(), [x.strip() for x in a.lint_ok.split(',') if x.strip()])
    return 0


if __name__ == '__main__':
    run(main)
