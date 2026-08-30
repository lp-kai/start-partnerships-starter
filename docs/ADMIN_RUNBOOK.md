# CRM-Admin: API-User pro Person

## Anlegen (ca. 10 Minuten pro Person)
1. Administration → Users → Create → Type **API**, Username `api_<vorname>`, Team **Partnerships**.
2. Rolle: Kopie der Partnerships-API-Rolle mit: Read team-weit auf Account/Contact/Lead/Opportunity/Email/Meeting/Task/Note; **DELETE nein** überall; Assignment nur **eigener User**; `Note:create` erlaubt (für Claims); Attachment/Case/KB kein Zugriff.
3. API-Key erzeugen, der Person **persönlich** übergeben (nicht in einen Kanal).
4. Eintrag ins Key-Inventar (außerhalb dieses Repos): Person, API-User-ID, Datum, Owner-User.

## Vor dem Team-Rollout entscheiden
- Kann der API-User auf seinen **menschlichen** Owner assignen? Falls nein: Assignments bleiben deaktiviert.
- Least-Privilege statt `edit: all`: Feld-/Entity-Minimierung oder Write-Gateway?
- Rate-Limits pro API-User bei 6 parallelen Nutzern; `Retry-After`?
- Claim-Notes (`[PARTNERSHIPS-CLAIM]` am Account, 24h TTL) freigeben → `config/team.json` `crm_claim_enabled: true`.

## Sperren
Users → API-User → **Deactivate**. Sofort wirksam. Inventar aktualisieren.

## Tests
Nur an einem Wegwerf-Account („ZZ TEST …"), nie an echten Datensätzen.
