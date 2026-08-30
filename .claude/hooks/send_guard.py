"""PreToolUse(Bash): no mail is ever sent. Blocks SMTP and IMAP-APPEND outside gmail_draft.py. Tripwire, not a sandbox."""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); from _hook import read, command, block, run
def main():
    c = command(read())
    if not c: return 0
    if not re.search(r'(?<![\w.])(python[0-9.]*|py)(?=\s|$)|\b(sh|bash|zsh)\s+-c\b|(?<![\w.])(node|perl|ruby)\b|<<', c): return 0
    if re.search(r'smtplib|\bsendmail\b|SMTP\s*\(|\.sendmail\(|send_message\(', c): return block('SEND GUARD: SMTP in an executable context. Rule 1: never send. Drafts only, via scripts/gmail_draft.py.')
    if re.search(r'imaplib', c) and re.search(r'append', c, re.I) and 'gmail_draft' not in c: return block('SEND GUARD: IMAP APPEND outside gmail_draft.py - drafts must pass the linter.')
    return 0
run(main)
