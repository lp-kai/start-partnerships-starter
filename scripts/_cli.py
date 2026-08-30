"""_cli.py - one error handler for every script: a clear cause and a next step, never a traceback."""
import sys, subprocess, shutil, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent

PY = 'py -3' if sys.platform.startswith('win') else 'python3'


def die(msg, code=2):
    print(f'\nABBRUCH: {msg}', file=sys.stderr); sys.exit(code)


def preflight(need_git=True, need_identity=False):
    if sys.version_info < (3, 10): die(f'Python 3.10+ needed, found {sys.version.split()[0]}.')
    if need_git and not shutil.which('git'): die('git is not installed. Install git, then run again.')
    if need_identity:
        for f in ('.env', 'me.json'):
            if not (ROOT / f).exists(): die(f'{f} missing. Run in a terminal: {PY} setup.py')


def git_ignored(rel):
    try:
        return subprocess.run(['git', 'check-ignore', '-q', rel], cwd=ROOT).returncode == 0
    except FileNotFoundError:
        return False


def run(main):
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        die('cancelled', 130)
    except SystemExit:
        raise
    except Exception as e:
        try:
            from _clients import SourceError
            if isinstance(e, SourceError): die(f'{e}\nNext: check the key and network for this source, then run {PY} scripts/health_check.py')
        except ImportError:
            pass
        die(f'{type(e).__name__}: {e}\nNext: run {PY} scripts/health_check.py and read the FAIL line.')
