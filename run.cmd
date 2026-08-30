@echo off
rem Windows helper: run.cmd health | check "Firma" | tutorial | lint drafts\x.md | tests
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
if "%1"=="health"   %PY% scripts\health_check.py & goto :eof
if "%1"=="tutorial" %PY% scripts\firma_check.py --tutorial & goto :eof
if "%1"=="check"    %PY% scripts\firma_check.py %2 %3 %4 & goto :eof
if "%1"=="lint"     %PY% scripts\draft_lint.py %2 & goto :eof
if "%1"=="hub"      %PY% scripts\hub_build.py & goto :eof
if "%1"=="tests"    %PY% tests\test_all.py & goto :eof
echo usage: run.cmd health ^| tutorial ^| check "Firma" [--domain x.de] ^| lint file.md ^| hub ^| tests
echo setup: py -3 setup.py   (run this one yourself, in this terminal)
