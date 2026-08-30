# Security

## Schlüssel
- Pro Person: eigener CRM-API-User, eigenes Gmail-App-Passwort, eigener Slack-Token, eigener Members-Key. **Nie teilen.**
- Eingabe nur über `setup.py` im Terminal (verdeckt). Nie im Chat, nie als Befehlsargument, nie in Dateien außer `.env`.
- `.env` ist git-ignoriert und lokal `0600`. `scripts/repo_guard.py` blockt Commits mit Schlüsselmustern (Pre-Commit).

## Wenn etwas passiert
| Fall | Sofort | Dann |
|---|---|---|
| Gerät verloren | CRM-Admin: API-User deaktivieren · Google: App-Passwort widerrufen · Slack-Admin: Token widerrufen | Neue Schlüssel, `setup.py` neu |
| Schlüssel im Chat/Commit gelandet | Denselben Schlüssel rotieren | `git log -p` prüfen, Historie bereinigen falls committed |
| Austritt | Admin sperrt API-User; Person löscht `.env`, `me.json`, `data/`, `kb/firmen/` | Inventar aktualisieren (`docs/ADMIN_RUNBOOK.md`) |

## Rotation
Mindestens halbjährlich oder bei Verdacht: neuen Schlüssel besorgen → `setup.py` → `health_check.py` grün → alten sperren.

## Was der Code NICHT enthält
Keinen Sende-Code (SMTP), keinen CRM-Delete, keinen Members-Vollabzug, keine Telemetrie. Gelesene Daten bleiben in ignorierten lokalen Ordnern.
