#!/bin/sh
# macOS/Linux helper: ./run.sh health | check "Firma" [--domain x.de] | tutorial | lint drafts/x.md | hub | tests
cd "$(dirname "$0")" || exit 1
PY=python3; command -v python3 >/dev/null || PY=python
case "$1" in
  health)   exec $PY scripts/health_check.py ;;
  tutorial) exec $PY scripts/firma_check.py --tutorial ;;
  check)    shift; exec $PY scripts/firma_check.py "$@" ;;
  lint)     exec $PY scripts/draft_lint.py "$2" ;;
  hub)      exec $PY scripts/hub_build.py ;;
  tests)    exec $PY tests/test_all.py ;;
  *) echo "usage: ./run.sh health | tutorial | check \"Firma\" [--domain x.de] | lint file.md | hub | tests"; echo "setup: python3 setup.py   (run this one yourself, in this terminal)" ;;
esac
