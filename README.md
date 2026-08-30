# START Partnerships Starter

Ein KI-Copilot für Sponsor-Outreach bei START Munich, den jede Person **mit eigenen Schlüsseln**
fährt: prüft eine Firma live gegen CRM, dein Postfach, Slack und die Members-Plattform, hält die
Event-Fakten in jedem Draft mechanisch sauber, und legt Drafts nur in **dein** Postfach. Gesendet
wird von dir.

Was drin ist, ist ehrlich benannt: die Guards sind Stolperdrähte gegen Versehen, kein Sandkasten.
Was das System an Konflikten meldet, ist eine Vorstufe für deine Prüfung, keine Freigabe.

## Phase 0: Voraussetzungen (einmalig, vor dem Repo)

| Was | Woher |
|---|---|
| Python 3.10+ und Git | python.org / git-scm.com (Mac: `brew install python git`) |
| Node 18+ | nur für die Claude-Code-Guards (nodejs.org). Ohne Node laufen die Scripts, aber keine Hooks |
| Eigener **EspoCRM-API-User** | beim CRM-Admin anfordern, `docs/ADMIN_RUNBOOK.md`. Dauert je nach Admin |
| **Gmail-App-Passwort** | Google-Konto → Sicherheit → 2-Schritt → App-Passwörter. IMAP in Gmail aktivieren |
| **Slack-User-Token** mit Lese-Scopes | über den Slack-Admin |
| **Members-API-Key** (optional) | my.startmunich.de → Admin → API Access |

## Phase 1: Setup (10 Minuten, wenn Phase 0 erledigt ist)

1. Repo **klonen** (nicht kopieren) und Claude Code oder Cowork **in diesem Ordner** starten.
2. Im Terminal, nie im Chat:
   ```
   macOS/Linux:  python3 setup.py
   Windows:      py -3 setup.py
   ```
   Eingaben sind verdeckt, jeder Schlüssel wird live geprüft, danach liegen `.env` und `me.json` lokal (git-ignoriert, 0600).
3. Prüfen: `./run.sh health` (Mac) bzw. `run.cmd health` (Windows). Pflichtquellen müssen PASS sein.
4. Tutorial: `./run.sh tutorial` / `run.cmd tutorial`. Eine Firma, alle Quellen, deine erste Akte.
5. Stilprofil: `rules/STIL_TEMPLATE.md` ausfüllen und als `memory/STIL.md` ablegen. Ohne das schreibt die KI generisch.

## Was du danach kannst

| Mac / Windows | Was passiert |
|---|---|
| `./run.sh check "Firma" --domain firma.de` / `run.cmd check …` | Live-Check über alle Quellen → `kb/firmen/<firma>.md` mit Methode+Datum je Befund und Konfliktstatus |
| `./run.sh lint drafts/x.md` | Draft gegen Event-Fakten und Stil-Tabus (8 Regeln) |
| `python3 scripts/gmail_draft.py --to … --subject … --body-file …` | Draft in DEIN Gmail (nach bestandenem Lint, APPEND-Status geprüft) |
| `python3 scripts/slack_search.py "Firma"` / `members_search.py "Firma"` | Nur lesen; Standardausgabe ohne Nachrichtentexte/Personendaten, `--full` zeigt sie |
| `./run.sh hub` | Deine Akten als lokale HTML-Seite `data/hub.html` |
| `./run.sh tests` | 40+ synthetische Tests, ohne Schlüssel |

Konfliktstatus: **STOP** (offener Deal, fremder Claim, fremde offene Task/Meeting) · **ABSTIMMEN** (fremder Owner/Lead, kürzliche Aktivität, Slack/Mail/Member-Treffer, oder eine Quelle fehlte/war abgeschnitten) · **KEIN KONFLIKT GEFUNDEN** (keine Evidenz in den geprüften Quellen: keine Garantie, das Team fragen).

Ablauf einer Kampagne: `docs/WORKFLOW.md`. Checklisten: `rules/CHECKLISTEN.md`.

## Was die KI hier nicht tun soll, und wie das abgesichert ist

| Regel | Absicherung |
|---|---|
| Nie senden | Kein Sende-Code im Repo. Hook blockt SMTP/Mail-Transport-Befehle (fail-closed) |
| Nie im CRM löschen oder ad hoc schreiben | Hook blockt POST/PUT/PATCH/DELETE; einziger Schreibweg `crm_claim.py`, aus bis Admin-Freigabe |
| Schlüssel nie anzeigen, nie committen | Hook blockt Lesen von `.env`/`me.json` durch Bash UND Datei-Tools; Pre-Commit-Guard scannt den Index; `.gitignore` |
| Keine Firma anschreiben, an der jemand dran ist | Firmencheck-Status + Checkliste W1 + Team fragen. Das ist ein Prozess, keine technische Sperre |

Umgehbar ist alles davon durch absichtliches Vorbeiarbeiten (z.B. `git commit --no-verify`). Details: `docs/GUARDRAILS_API_KEYS.md`, `SECURITY.md`.

## Wo was liegt

`CLAUDE.md` Regeln für die KI · `docs/CRM_GUIDE.md` was im CRM steckt und was 403 liefert · `docs/QUELLEN.md` welche Quelle gilt ·
`facts.json` freigegebene Event-Fakten · `rules/REPLY_PLAYBOOK.md` wenn jemand antwortet · `docs/ADMIN_RUNBOOK.md` für den CRM-Admin.

Lokal und nie im Git: `.env`, `me.json`, `data/`, `drafts/`, `kb/firmen/*`, `memory/*`, `state/`.

Bekannte Grenzen: Cowork führt die Hooks nicht aus (nur Claude Code); unter Windows werden Dateirechte nicht automatisch eingeschränkt.
