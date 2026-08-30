"""PreToolUse(Bash): no mail is ever sent from here. Checks every shell segment; exemption only for an
exact call of scripts/gmail_draft.py. Fails CLOSED. Still a tripwire against accidents, not a sandbox."""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); from _hook import read, command, block, run_closed

EXEC = r'(?<![\w.])(python[0-9.]*|py|node|perl|ruby|php)\b|\b(sh|bash|zsh)\s+-c\b|<<|^\s*\./'
EXEMPT = re.compile(r'^\s*(python[0-9.]*|py(\s+-3)?)\s+(\S*/)?scripts/gmail_draft\.py\b')


def main():
    cmd = command(read())
    if re.search(EXEC, cmd) and re.search(r'imaplib', cmd) and re.search(r'append', cmd, re.I) and not re.search(r'scripts/gmail_draft\.py', cmd):
        return block('SEND GUARD: IMAP APPEND outside gmail_draft.py - drafts must pass the linter.')
    if re.search(EXEC, cmd) and re.search(r'smtplib', cmd) and not EXEMPT.match(cmd.strip()):
        return block('SEND GUARD: SMTP in executable code. Rule 1: never send.')
    for seg in re.split(r'[;&|]+|\n', cmd):
        s = seg.strip()
        if not s or EXEMPT.match(s): continue
        if re.search(r'\bcurl\b.*\bsmtps?://', s, re.I) or re.search(r'\b(sendmail|mailx?|mutt|swaks|msmtp)\b', s):
            return block('SEND GUARD: mail transport command. Rule 1: never send. Drafts only, via scripts/gmail_draft.py.')
        if re.search(EXEC, s) and re.search(r'smtplib|SMTP\s*\(|\.sendmail\(|send_message\(|nodemailer|smtp\.', s, re.I):
            return block('SEND GUARD: SMTP in executable code. Rule 1: never send. Drafts only, via scripts/gmail_draft.py.')
        if re.search(EXEC, s) and re.search(r'imaplib', s) and re.search(r'append', s, re.I):
            return block('SEND GUARD: IMAP APPEND outside gmail_draft.py - drafts must pass the linter.')
    return 0


run_closed(main)
