"""_shell.py - shared command analysis for the guards.

Regex over a whole command line is either leaky or noisy: it misses `evil/scripts/x.py` and
`$(...)` substitutions, and it fires on `grep gmail.googleapis.com`. So the guards tokenize:
split into segments (quote-aware), then look at the PROGRAM of each segment.

Two different views on the text:
  raw(seg)      - everything, including single-quoted code. Use it to find WHAT a command targets.
  expanded(seg) - single-quoted parts removed. Use it only to decide whether the shell would
                  EXPAND a variable (printing a key value).
"""
import re, shlex

READ_ONLY = {'grep', 'rg', 'ugrep', 'ack', 'cat', 'less', 'more', 'head', 'tail', 'wc', 'diff',
             'find', 'ls', 'file', 'stat', 'sed', 'awk', 'cut', 'sort', 'uniq', 'echo', 'printf',
             'git', 'nl', 'column', 'jq', 'tree', 'which', 'type', 'man'}
EXECUTORS = re.compile(r'^(python[0-9.]*|py|node|nodejs|perl|ruby|php|osascript|deno|bun)$')
SHELLS = {'sh', 'bash', 'zsh', 'dash', 'ksh', 'fish'}
ASSIGN = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*=')


def split_top_level(cmd):
    """Split on ; && || | and newlines, but never inside quotes."""
    out, buf, quote, i = [], '', None, 0
    while i < len(cmd):
        c = cmd[i]
        if quote:
            buf += c
            if c == quote and cmd[i - 1] != '\\':
                quote = None
        elif c in '"\'':
            quote = c; buf += c
        elif c in ';\n':
            out.append(buf); buf = ''
        elif c in '|&' and i + 1 < len(cmd) and cmd[i + 1] == c:
            out.append(buf); buf = ''; i += 1
        elif c in '|&':
            out.append(buf); buf = ''
        else:
            buf += c
        i += 1
    out.append(buf)
    return [s.strip() for s in out if s.strip()]


def substitutions(cmd):
    """Text inside $( ), ` ` and <( ) - these run as their own commands."""
    out = []
    out += re.findall(r'\$\(([^()]*(?:\([^()]*\)[^()]*)*)\)', cmd)
    out += re.findall(r'`([^`]*)`', cmd)
    out += re.findall(r'<\(([^()]*)\)', cmd)
    return out


def segments(cmd):
    segs = split_top_level(cmd)
    for sub in substitutions(cmd):
        segs += split_top_level(sub)
    return [s for s in segs if s]


def tokens(seg):
    try:
        return shlex.split(seg, posix=True)
    except ValueError:
        return seg.split()


def program(seg):
    """The command word: skips VAR=x prefixes and wrappers, but only when a real command follows."""
    toks = tokens(seg)
    i = 0
    while i < len(toks):
        t = toks[i]
        if ASSIGN.match(t):
            i += 1; continue
        if t in ('sudo', 'command', 'nohup', 'time', 'exec', 'env'):
            rest = toks[i + 1:]
            # `env` alone or with flags only is itself the command (it dumps the environment)
            if not rest or all(r.startswith('-') for r in rest):
                return t.split('/')[-1].lower()
            if t == 'env' and not any(ASSIGN.match(r) or not r.startswith('-') for r in rest):
                return 'env'
            i += 1; continue
        return t.split('/')[-1].lower()
    return ''


def is_read_only(seg):
    return program(seg) in READ_ONLY


def expanded(seg):
    """Only what the shell would expand: single-quoted strings removed."""
    return re.sub(r"'[^']*'", '', seg)


def script_target(seg, rel_path):
    """Returns 'real' if the segment runs exactly this repo script, 'lookalike' if it runs
    something that merely looks like it, or None."""
    toks = [t for t in tokens(seg) if not ASSIGN.match(t)]
    if not toks:
        return None
    i = 1 if toks[0] in ('sudo', 'nohup', 'time', 'command', 'env') else 0
    if i >= len(toks):
        return None
    prog = toks[i].split('/')[-1].lower()
    name = rel_path.split('/')[-1]
    if EXECUTORS.match(prog):
        args = [a for a in toks[i + 1:] if not a.startswith('-')]
        if not args:
            return None
        target = args[0].replace('\\', '/')
    elif name in toks[i]:
        target = toks[i].replace('\\', '/')
    else:
        return None
    if name not in target:
        return None
    if target in (rel_path, './' + rel_path) or (target.startswith('/') and target.endswith('/' + rel_path)):
        return 'real'
    return 'lookalike'


def runs_script(seg, rel_path):
    return script_target(seg, rel_path) == 'real'
