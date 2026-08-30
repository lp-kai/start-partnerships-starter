# EspoCRM: was drin steckt, was geht, was 403 liefert

Base: `https://espo.dedicated.startmunich.de/api/v1`, Auth `X-Api-Key` (dein API-User). Jede Aussage hier trägt **Methode + Stand**, damit sie nicht zur Naturkonstante wird.

## Entity-Modell
```
Lead ──convert──▶ Account (Firma) ◀── Contact (Person)
                     ├──▶ Opportunity (Deal, mit campaignId)
                     └──▶ Meeting / Task / Email / Note (Stream)
```
Faustregel: Firma = Account, Sponsoring-Paket = Opportunity (Kampagne RtSH27 / RtSS27, IDs in `config/team.json`), Ansprechpartner = Contact. Lead nur für unqualifizierte Einzelpersonen.

## Was der Firmencheck liest (alles GET)
Account (Name + `textFilter`) · `/Account/{id}/contacts|opportunities|meetings|tasks` · `/Account/{id}/stream` · `/Email?where parentId=` (Metadaten, paginiert; `total` ist unzuverlässig) · `/Lead?textFilter=`.
**Tasks (Wiedervorlagen) und Meetings sind aktiv genutzte Entities**: immer prüfen. Meetings hängen oft an der Opportunity, nicht am Account.

## Aktiv-Checkliste (arbeitet jemand an der Firma?)
AKTIV: offene Opportunity (Prospecting…Negotiation) · Owner ist ein echter User · echte Stream-Aktivität < 6 Monate (Post, Mail, Meeting, nicht Bot-Creates).
VERALTET-ÜBERNEHMBAR: belegt, aber >6 Monate still und kein offener Deal → mit dem Owner abstimmen. FREI: nur Platzhalter oder kein Eintrag, **trotzdem das Team fragen**.

## Rechte des API-Users (Stand 30.08.2026, Methode: GET/PUT/POST live getestet)
| Operation | Ergebnis |
|---|---|
| GET auf Account/Contact/Lead/Opportunity/Email/Meeting/Task/Stream | ✅ |
| `POST /Note` mit `parentType: Account` | ✅ (einziger vorgesehener Schreibweg, via `crm_claim.py`) |
| `POST /Note` mit `parentType: Opportunity` oder `Lead` | ❌ 403 (`stream: no`) |
| `PUT assignedUserId` auf fremden User | ❌ 403 „Assignment failure", Rolle erlaubt nur Selbstzuweisung |
| `PUT /Email/{id}` parent umhängen | ❌ 403 |
| `DELETE` | ❌ nicht erlaubt, im Starter nicht implementiert |
| Attachment-Listing, Case, KnowledgeBase | ❌ 403 |

## Fallen
- `where[...]`-Parameter MÜSSEN URL-encoded sein, sonst liefert die API **leer statt Fehler**. So entstand einmal „Task=0", tatsächlich sind es hunderte.
- Dubletten durch Migrations-Bots (`roboweek_migrator`): den menschlich angelegten Account führen.
- Ein 403 ist ein Befund mit Datum, keine Naturkonstante. Rechte ändern sich.
