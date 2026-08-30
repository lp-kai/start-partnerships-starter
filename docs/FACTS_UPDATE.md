# facts.json pflegen

- `facts.json` ist die einzige Quelle für Event-Fakten und wird team-weit über dieses Repo verteilt.
- Änderungen nur durch den Fakten-Owner (`decision_owner`), mit `version` +1 und `stand` = Datum.
- Nach einem Update: `git pull`, dann `python3 scripts/draft_lint.py --selbsttest` (muss 8/8 sein).
- Lokal nie eigene Fakten „nachbessern": melden.
