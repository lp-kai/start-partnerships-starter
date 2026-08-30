# Wie eine Kampagne läuft

```
01 ICP + Signale → 02 Research → 03 Firmencheck (alle Quellen) → 04 Sortieren → 05 Outreach je Typ → 06 CRM-Nachtrag → Antwort → Call → Custom-Follow-up
```

**01 ICP + Signale.** Mit Menschen: welche Firmen wollen wir, was hätten sie von uns, welche Signale heißen „jetzt" (Hiring, Funding, Launch, Dev-Rel).

**02 Research.** Deep Research (Claude, Gemini, ChatGPT) gegen die Signale → Kandidatenliste, zusammengeführt und dedupliziert.

**03 Firmencheck.** `scripts/firma_check.py "Firma" --domain …` pro Firma. Liefert Akte + Status:
- **STOP**: offene Opportunity, aktiver fremder Claim oder aktive Kollegen. Finger weg oder mit dem Owner sprechen.
- **ABSTIMMEN**: fremder Owner mit alter Aktivität. Kurzer Ping an den Owner, dann weiter.
- **KEIN KONFLIKT GEFUNDEN**: keine Evidenz in den Quellen. Keine Garantie. Plus: **das Team fragen** (manches wurde nie getrackt).

**04 Sortieren.** Nach Draht und Kaufsignal: Warm-Intro (Member dort, aktuell oder ehemalig) · Re-engage (alter Faden im CRM/Postfach) · Kalt.

**05 Outreach je Typ.**
- Kalt → Draft in deinem Ton mit einer Research-Variable (Aufhänger). Keine Adresse? Lusha o.ä., nur für Firmen, die niemand kennt.
- LinkedIn → keine Mail, aber dokumentieren: wen, wann, wie.
- Warm → Custom-Reply auf den bestehenden Faden, bezieht sich auf das, was wirklich passiert ist.
- Member-Intro → den Member auf Slack fragen, dokumentieren, wen du gefragt hast.
Jeder Draft: `draft_lint.py` → `gmail_draft.py` → **du sendest**.

**06 CRM-Nachtrag.** Nach dem Senden: Account/Lead anlegen (nach Go), Kampagne verknüpfen, Research in die Profile, Wiedervorlage als Task. Claim-Mechanismus (`crm_claim.py`), sobald vom Admin freigegeben.

**Follow-up.** Touch 2 darf normal nachhaken. **Ab Touch 3 braucht es einen neuen Winkel oder Anlass** (Funding, neue Rolle, Hiring, Launch, Messe). Reaktivierung nach >60 Tagen = neuer Erstkontakt mit Anlass.

**Antwort → Call → Custom.** Out-of-Office ist keine Antwort. Echte Antwort → Deal im CRM. Call aufnehmen (Notion/Granola), Transkript der KI geben → Zusammenfassung + Action Items in den CRM-Stream, daraus Custom-Deck oder Follow-up-Mail mit ihren Worten.

**Send-Diff.** Wenn du den Draft vor dem Senden geändert hast: die Änderung ins Lern-Log deines Stilprofils. So lernt die KI deinen Ton.
