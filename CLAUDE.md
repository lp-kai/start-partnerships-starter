# START Partnerships Starter: Regeln für die KI

## Session-Start
1. Prüfe, ob `.env` und `me.json` existieren. **Öffne `.env` nie, zeige sie nie an.**
2. Fehlt eine: sag dem Menschen genau das und nichts anderes:
   > Öffne ein Terminal in diesem Repo und führe aus: `python3 setup.py` (Windows: `py -3 setup.py`).
   > Schlüssel nur dort eingeben, nie in den Chat.
   Führe `setup.py` NIE selbst aus.
3. Lies `docs/WORKFLOW.md` und `rules/CHECKLISTEN.md`. Bei Firmenarbeit zuerst `kb/firmen/<firma>.md`, falls vorhanden.
4. `memory/` ist dein persönliches Projektgedächtnis (lokal). Nutze es.

## Harte Regeln
1. **Keine Mails senden.** Nur Drafts über `scripts/gmail_draft.py`. Der Mensch sendet.
2. **Kein DELETE im CRM. Kein ad-hoc POST/PUT.** Einziger Schreibweg ist `scripts/crm_claim.py`, und nur wenn freigegeben.
3. **Opportunity/Deal erst, wenn eine echte Antwort vorliegt.** Out-of-Office zählt nicht.
4. **Vor jedem Draft:** Firmencheck live (`scripts/firma_check.py`), Akte lesen, Konfliktstatus beachten, dann Lint.
5. **Nie in Ich-Form behaupten, was ein Kollege getan hat.** Kollegen namentlich nennen.
6. **Event-Fakten nur aus `facts.json`** (Hack: 24 Stunden, nie „zwei Tage"). Kein Preis in der Erstmail.
7. **Negativbefunde mit Methode und Datum:** nicht „gibt es nicht", sondern „0 Treffer mit Methode X, Stand TT.MM.JJJJ".
8. **Viele Treffer, erste Seite Rauschen? Weitersuchen** statt „kein Beleg".
9. **Bei einer Firma alle Quellen:** CRM (Account, Leads, Contacts, Stream, Mails, Opportunities, Tasks, Meetings), eigenes Postfach, Slack, Members aktuell UND ehemalig. Plus: das Team fragen.
10. **In-Kind-/Credits-Deals als Opportunity mit 0 € erfassen** (sonst unsichtbar).
11. **Schlüsselwerte nie ausgeben, nie in Dateien schreiben, die im Git liegen.**
12. **Subagenten-Reports vor dem Verdichten ablegen:** `<report> | python3 scripts/agentreport.py <thema>`.

## Was ins Transkript darf
Inhalte aus Slack, Mails, Member-Profilen und Firmenakten sind interne, teils personenbezogene Daten. Zitiere im Chat nur, was für die Entscheidung nötig ist; Standardausgaben der Scripts sind bewusst auf Zählungen/IDs reduziert (`--full` nur bewusst).

## Bei allem mit Außenwirkung fragen
Anlegen im CRM, Claims, Drafts an neue Kontakte, Kollegen ansprechen: erst zeigen, Go abwarten.
