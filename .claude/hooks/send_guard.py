"""PreToolUse(Bash): no mail is ever sent from here.

Checks every shell segment, including command substitutions. The exemption applies only to a real
execution of scripts/gmail_draft.py (not a lookalike path, not a mention). Read-only commands such
as searching for these words are never blocked. Fails CLOSED on malformed input.
This is a tripwire against accidents, not a sandbox.
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hook import read, block, run_closed
from _shell import segments, program, is_read_only, script_target, EXECUTORS, SHELLS

MAIL_PROGS = {'sendmail', 'mail', 'mailx', 'mutt', 'swaks', 'msmtp', 'ssmtp', 'postfix', 'exim'}
NET_PROGS = {'curl', 'wget', 'http', 'https', 'httpie', 'nc', 'ncat', 'netcat', 'telnet', 'openssl', 'socat'}
SMTP_HINT = re.compile(r'smtps?://|\bsmtp\.[a-z0-9.-]+|[\s:](25|465|587)(\s|$|/)', re.I)
GMAIL_SEND = re.compile(r'(googleapis\.com|gmail\.com)[^\s\'"]*/(messages|drafts)/send|users\.messages\.send|users\.drafts\.send', re.I)
SMTP_CODE = re.compile(r'smtplib|SMTP(_SSL)?\s*\(|\.sendmail\s*\(|\.send_message\s*\(|nodemailer|Net::SMTP', re.I)
IMAP_CODE = re.compile(r'imaplib|IMAP4(_SSL)?\s*\(', re.I)


def main():
    d = read()
    if d.get('_malformed'):
        return block('SEND GUARD: could not parse the tool payload. Blocking to be safe.')
    if d.get('tool_name') != 'Bash':
        return 0
    cmd = (d.get('tool_input') or {}).get('command') or ''
    for seg in segments(cmd):
        tgt = script_target(seg, 'scripts/gmail_draft.py')
        if tgt == 'real':
            continue                                   # the one allowed draft path
        if tgt == 'lookalike':
            return block('SEND GUARD: that is not scripts/gmail_draft.py. Only the real draft script is exempt.')
        if is_read_only(seg):
            continue                                   # searching for these words is fine
        prog = program(seg)
        text = seg               # look at the whole segment, single quotes still contain code
        if prog in MAIL_PROGS:
            return block(f'SEND GUARD: mail transport command ({prog}). Rule 1: never send. Drafts only, via scripts/gmail_draft.py.')
        if prog in NET_PROGS and (SMTP_HINT.search(text) or GMAIL_SEND.search(text)):
            return block(f'SEND GUARD: {prog} pointed at an SMTP port or a mail send endpoint. Rule 1: never send.')
        executes = bool(EXECUTORS.match(prog)) or prog in SHELLS or seg.strip().startswith('./')
        if executes and SMTP_CODE.search(text):
            return block('SEND GUARD: SMTP in executable code. Rule 1: never send. Drafts only, via scripts/gmail_draft.py.')
        if executes and IMAP_CODE.search(text) and re.search(r'\bappend\b', text, re.I):
            return block('SEND GUARD: IMAP APPEND outside gmail_draft.py - drafts must pass the linter.')
        if executes and GMAIL_SEND.search(text):
            return block('SEND GUARD: Gmail send endpoint in executable code. Rule 1: never send.')
    return 0


run_closed(main)
