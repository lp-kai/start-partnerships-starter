# Guardrails: API-Keys und CRM-Zugriff

| Regel | Warum | Wie erzwungen |
|---|---|---|
| Ein Schlüssel an genau einer Stelle (`.env`), nie im Code, nie im Git | Kopien vervielfachen jedes Leak | `.gitignore` + `repo_guard.py` (Pre-Commit) |
| Werte nie ausgeben, nur Namen, Längen, Hashes | Alles im Chat landet im Transkript | `secret_leak_guard.py` |
| Schlüssel nur im Terminal eingeben, nie im Chat, nie als Argument | dito | `setup.py` verweigert Pipes und Argumente; Hook blockt Tool-Aufrufe von setup.py |
| Nie senden, nur Drafts | Eine falsche Mail ist nicht zurückholbar | kein SMTP-Code; `send_guard.py` |
| Kein DELETE, kein ad-hoc Schreiben im CRM | Team-CRM, Fehler treffen alle | `crm_write_guard.py`; einziger Schreibweg `crm_claim.py` (aus bis Admin-Freigabe) |
| Anlegen/Umhängen nur nach explizitem Go | Ungefragte Datensätze sind Aufräumarbeit für andere | `CLAUDE.md` + Claim mit Bestätigung |
| Deal erst nach echter Antwort | Sonst Pipeline-Müll | `CLAUDE.md` Regel 3 |
| Schreibtests nur an Wegwerf-Datensätzen | Produktionsdaten überschreibt man nicht zum Testen | `docs/ADMIN_RUNBOOK.md` |
| Massenänderungen nur mit Dry-run | Ein falscher Schlüssel ordnet hunderte Datensätze falsch zu | `crm_claim.py --write` explizit |
| Read-only als Default (Slack, Members, IMAP) | Der Token könnte mehr, die Scripts tun es nicht | nur lesende Methoden implementiert |
| Pro Person eigene Schlüssel | Audit-Trail und Sperrbarkeit | `SECURITY.md` |

**Ehrlich:** Hooks sind Stolperdrähte gegen Versehen, kein Sandboxing. Die Garantie bleibt organisatorisch: der Mensch sendet, der Mensch gibt frei.
