# START Partnerships Starter

Dein eigener KI-Copilot für Sponsor-Outreach bei START Munich: prüft Firmen gegen CRM, dein
Postfach, Slack und die Members-Plattform, schreibt Drafts in deinem Ton, und hält sich an
Regeln, die als Werkzeuge gebaut sind, nicht als Bitte.

**Jede Person hat eigene Schlüssel. Nichts wird geteilt. Nichts wird gesendet, außer von dir.**

## In 10 Minuten startklar

1. **Repo holen** und in Claude Code oder Cowork öffnen (aus DIESEM Ordner starten, sonst greifen die Guards nicht).
2. **Zugänge besorgen** (einmalig):
   - EspoCRM: eigenen **API-User** beim CRM-Admin anfordern (`docs/ADMIN_RUNBOOK.md`)
   - Gmail: **App-Passwort** erzeugen (Google-Konto → Sicherheit → App-Passwörter)
   - Slack: **User-Token** mit Lese-Scopes über den Slack-Admin (Niklas)
   - Members-Plattform: **API-Key** unter my.startmunich.de → Admin → API Access (optional)
3. **Setup im Terminal**, nie im Chat:
   ```
   macOS/Linux:  python3 setup.py
   Windows:      py -3 setup.py
   ```
   Eingaben sind verdeckt, jeder Schlüssel wird live geprüft, danach liegen `.env` und `me.json` lokal (git-ignoriert).
4. **Prüfen:** `python3 scripts/health_check.py` → alle Pflichtquellen PASS.
5. **Tutorial:** `python3 scripts/firma_check.py --tutorial`: eine Firma, alle Quellen, deine erste Akte.

## Was du danach kannst

| Befehl | Was passiert |
|---|---|
| `scripts/firma_check.py "Firma" --domain firma.de` | Live-Check über alle Quellen → `kb/firmen/<firma>.md` mit Beleg je Aussage + Konfliktstatus |
| `scripts/slack_search.py "Firma"` | Slack durchsuchen (nur lesen) |
| `scripts/members_search.py "Firma"` | Wer arbeitet(e) dort: aktuelle UND ehemalige Members zählen als Intro-Weg |
| `scripts/draft_lint.py drafts/x.md` | Draft gegen Event-Fakten und Stil-Tabus prüfen |
| `scripts/gmail_draft.py --to … --subject … --body-file …` | Draft in DEIN Gmail legen (nach bestandenem Lint). Senden tust du |
| `scripts/health_check.py` | Alle Datenwege unter deiner Identität prüfen |
| `scripts/hub_build.py` | Deine Akten als lokale Hub-Seite (`data/hub.html`), sortiert nach Konfliktstatus |

Der Ablauf einer Kampagne: `docs/WORKFLOW.md`. Checklisten pro Schritt: `rules/CHECKLISTEN.md`.

## Was die KI hier NICHT darf (und technisch nicht kann)

- **Nie senden.** Es gibt keinen Sende-Code. Ein Hook stolpert über SMTP-Versuche.
- **Nie im CRM löschen oder ad hoc schreiben.** Der einzige Schreibweg (Account-Claim) ist aus, bis der Admin ihn freigibt.
- **Nie Schlüssel anzeigen oder committen.** Hook + Pre-Commit-Guard + `.gitignore`.
- **Nie eine Firma anschreiben, an der jemand dran ist.** Der Firmencheck liefert STOP / ABSTIMMEN / KEIN KONFLIKT GEFUNDEN.

Details: `docs/GUARDRAILS_API_KEYS.md`, `SECURITY.md`.

## Wo was liegt

`CLAUDE.md` Regeln für die KI · `docs/CRM_GUIDE.md` was im CRM steckt und was 403 liefert · `docs/QUELLEN.md` welche Quelle gilt ·
`facts.json` freigegebene Event-Fakten · `rules/STIL_TEMPLATE.md` eigenes Stilprofil aufbauen · `rules/REPLY_PLAYBOOK.md` wenn jemand antwortet.

Lokal und nie im Git: `.env`, `me.json`, `data/`, `drafts/`, `kb/firmen/*`, `memory/`, `state/`.

## Tests
`python3 tests/test_all.py` (synthetisch, ohne Schlüssel, ohne Live-Aufrufe).
