#!/usr/bin/env python3
"""draft_lint.py - prueft einen Mail-Draft mechanisch gegen die Fakten und Stil-Tabus.

Checks a mail draft mechanically against facts.json (event facts) and style taboos.
Covers EVENT facts and known anti-patterns - NOT every START number. Exit 1 = violation.

Facts come from facts.json at the repo root (versioned, see docs/FACTS_UPDATE.md).

Aufruf:
    py -3 scripts/draft_lint.py drafts/<datei>.md [weitere ...]
    py -3 scripts/draft_lint.py --text "Hey Alex, ..."     (roher Mailtext, z.B. aus gmail_draft)
    py -3 scripts/draft_lint.py --selbsttest               (Positiv- UND Negativtest je Regel)

Exit 0 = sauber. Exit 1 = mindestens ein Verstoss. Exit 2 = Bedienfehler.

Was gelintet wird: bei .md-Dateien NUR der Mailtext (Abschnitt '## Text...' bis zur
naechsten '## '-Ueberschrift) - Metadaten und Datenlage-Abschnitte duerfen Preise und
Konkurrenzformate nennen, die Mail nicht. Ohne '## Text'-Abschnitt wird die ganze Datei
geprueft (mit Hinweis).

Unterdrueckung im Einzelfall: eine Zeile 'lint-ok: <regel-id>[, <regel-id>]' irgendwo in
der DATEI (nicht im Mailtext) schaltet die Regel fuer diese Datei ab - gedacht fuer
belegte Ausnahmen wie eine echte Ich-Form-Historie. Regel-IDs siehe REGELN unten.
"""
import json, re, sys, io
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
FAKTEN_PFAD = WURZEL / 'facts.json'


def lade_fakten():
    return json.load(io.open(FAKTEN_PFAD, encoding='utf-8'))


def mailtext_aus_md(inhalt):
    """Nur den Mailtext linten: '## Text...'-Abschnitt bis zur naechsten '## '-Ueberschrift."""
    m = re.search(r'^## Text[^\n]*\n(.*?)(?=^## |\Z)', inhalt, re.M | re.S)
    if m:
        return m.group(1), True
    return inhalt, False


def unterdrueckt(inhalt_gesamt, mailtext=''):
    """lint-ok-Zeilen zaehlen nur AUSSERHALB des Mailtexts - sonst koennte der Text
    seine eigene Pruefung abschalten (Codex-Audit 30.08., Befund 5)."""
    metadaten = inhalt_gesamt.replace(mailtext, '') if mailtext else inhalt_gesamt
    ids = set()
    for m in re.finditer(r'^lint-ok:\s*(.+)$', metadaten, re.M):
        ids.update(x.strip() for x in m.group(1).split(','))
    return ids & {r[0] for r in REGELN}


# ---------------------------------------------------------------- Regeln
# Jede Regel: (id, beschreibung, funktion(text, fakten) -> liste von Meldungen)

def r_dauer(text, f):
    tref = [m for m in f['rtsh']['falsche_dauer_muster'] if re.search(re.escape(m), text, re.I)]
    return [f'Hack-Dauer falsch: „{m}“ - der Hack ist {f["rtsh"]["dauer"]} (facts.json rtsh.dauer)'
            for m in tref]


def r_datum(text, f):
    """Positiv-Validierung: JEDES Nov/Dez-2026-Datum im Text muss auf einen erlaubten Tag
    fallen (Hack 21./22.11., Summit 07.12.). Blacklists uebersehen Schreibweisen -
    genau so rutschten 2026-12-09 und 9.12. durch (Codex-Audit 30.08., Befund 2)."""
    erlaubt = {f['rtsh']['monat']: set(f['rtsh']['erlaubte_tage']),
               f['rtss']['monat']: set(f['rtss']['erlaubte_tage'])}
    monatsname = {'november': 11, 'dezember': 12, 'december': 12}
    meldungen = []

    def pruefe(tag, monat, fund):
        if monat in erlaubt and tag not in erlaubt[monat]:
            soll = f['rtsh']['datum_text'] if monat == 11 else f['rtss']['datum']
            meldungen.append(f'Datum falsch: „{fund}“ - richtig ist {soll} (facts.json)')

    for m in re.finditer(r'\b(\d{1,2})\.\s?(11|12)\.(?:\s?20\d\d)?', text):
        pruefe(int(m.group(1)), int(m.group(2)), m.group(0))
    for m in re.finditer(r'\b20\d\d-(11|12)-(\d{2})\b', text):
        pruefe(int(m.group(2)), int(m.group(1)), m.group(0))
    for m in re.finditer(r'\b(\d{1,2})\.\s?(November|Dezember|December)\b', text, re.I):
        pruefe(int(m.group(1)), monatsname[m.group(2).lower()], m.group(0))
    for m in re.finditer(r'\b(November|December)\s(\d{1,2})\b', text, re.I):
        pruefe(int(m.group(2)), monatsname[m.group(1).lower()], m.group(0))
    # Zusatz-Blacklist fuer Schreibweisen ohne Tag-Monats-Muster
    for muster in f['rtss']['falsche_datums_muster']:
        if muster in text and not any(muster in me for me in meldungen):
            meldungen.append(f'Summit-Datum falsch: „{muster}“ - entschieden ist {f["rtss"]["datum"]}')
    return meldungen


def r_gaeste(text, f):
    meldungen = []
    gastwort = r'(Gäste|Gaeste|guests?|Teilnehmer|attendees|Besucher)'
    for m in f['rtss']['falsche_gaeste_muster']:
        if re.search(r'\b' + m + r'\s*' + gastwort, text, re.I):
            meldungen.append(f'Gästezahl falsch: „{m} Gäste“ - entschieden ist '
                             f'„{f["rtss"]["gaeste_formulierung"]}“ (facts.json)')
    # 500 ohne Qualifizierer: die Zahl ist eine Planung, kein Fakt
    for m in re.finditer(r'(.{0,30})\b500\s*' + gastwort, text, re.I):
        vorlauf = m.group(1).lower()
        if not any(q.lower() in vorlauf for q in f['rtss']['gaeste_qualifizierer']):
            meldungen.append('„500 Gäste“ ohne Qualifizierer - Formulierung ist '
                             f'„{f["rtss"]["gaeste_formulierung"]}“ (das „aktuell geplant“ hält es offen)')
    return meldungen


def r_preis(text, f):
    tref = re.findall(r'\b\d{1,3}(?:[.,]\d{3})+\s*(?:€|EUR|Euro)|\b\d+\s*(?:€|EUR|Euro)\b|\b\d{1,3}[kK]\b(?!\w)|\$\s?\d[\d.,]*', text)
    return [f'Preis im Mailtext: „{t}“ - kein Preis in der ERSTMAIL, Pricing im Call '
            '(facts.json preise). Ist das bewusst eine Pricing-/Follow-up-Mail '
            'mit Preis: „lint-ok: preis“ in die Draft-Metadaten bzw. --lint-ok preis' for t in tref]


def r_emdash(text, f):
    n = text.count('—')
    return [f'{n}x Em-Dash (—) im Mailtext - hartes Tabu (CLAUDE.md §2)'] if n else []


def r_ichform(text, f):
    muster = re.compile(
        r'\bich\s+(hatte|habe|hab)\s+(?:\w+\s+){0,6}?(geschrieben|gesprochen|telefoniert|gemailt|gepitcht|vorgestellt|kontaktiert|angeschrieben|angerufen)'
        r'|\bich war\s+(?:\w+\s+){0,4}?(bei euch|vor Ort|im Call|im Gespräch)'
        r'|\bwie (ich\s+)?(besprochen|damals sagte)'
        r"|\bI\s+(had|have)\s+(?:\w+\s+){0,5}?(written|spoken|talked|pitched|reached out|contacted|emailed|called)",
        re.I)
    tref = [m.group(0) for m in muster.finditer(text)]
    return [f'Ich-Form für Kontakt-Historie: „{t}“ - wenn der Kontakt von einem Kollegen war, '
            'den Kollegen namentlich nennen (CLAUDE.md rule 5). Was it really you: '
            '„lint-ok: ichform“ in die Draft-Metadaten' for t in tref]


def r_antipattern(text, f):
    tref = [m for m in f['anti_patterns'] if re.search(re.escape(m), text, re.I)]
    tref += [m for m in f['superlativ_tabus'] if re.search(re.escape(m), text, re.I)]
    return [f'Anti-Pattern aus rules/STIL_TEMPLATE.md / Fakten-Tabus: „{m}“' for m in tref]


def r_konkurrenz(text, f):
    tref = [m for m in f['konkurrenzformate'] if re.search(re.escape(m), text, re.I)]
    return [f'Konkurrenzformat im Mailtext: „{m}“ - Recherche über Fremdauftritte fließt in die '
            'Einschätzung, nie in den Text (rules/CHECKLISTEN.md)' for m in tref]


REGELN = [
    ('dauer',        'Hack ist 24 Stunden, nie „zwei Tage“', r_dauer),
    ('datum',        'Summit-Datum wie in 1.2 entschieden', r_datum),
    ('gaeste',       'Gästezahl wie in 1.2 entschieden, mit Qualifizierer', r_gaeste),
    ('preis',        'kein Preis in der Erstmail', r_preis),
    ('emdash',       'keine Em-Dashes', r_emdash),
    ('ichform',      'keine Ich-Form für Kollegen-Historie', r_ichform),
    ('antipattern',  'Anti-Patterns aus §5b + Fakten-Tabus', r_antipattern),
    ('konkurrenz',   'keine Konkurrenzformate nennen', r_konkurrenz),
]


def linte(text, fakten, skip=()):
    befunde = []
    for rid, _, fn in REGELN:
        if rid in skip:
            continue
        for meldung in fn(text, fakten):
            befunde.append((rid, meldung))
    return befunde


def linte_datei(pfad, fakten):
    inhalt = io.open(pfad, encoding='utf-8').read()
    text, hatte_abschnitt = mailtext_aus_md(inhalt) if pfad.endswith('.md') else (inhalt, True)
    skip = unterdrueckt(inhalt, text if hatte_abschnitt else '')
    befunde = linte(text, fakten, skip)
    print(f'{pfad}' + ('' if hatte_abschnitt else '  (kein "## Text"-Abschnitt - ganze Datei geprüft)'))
    for rid, meldung in befunde:
        print(f'  [{rid}] {meldung}')
    if skip:
        print(f'  (unterdrückt per lint-ok: {", ".join(sorted(skip))})')
    if not befunde:
        print('  sauber')
    return len(befunde)


# ---------------------------------------------------------------- Selbsttest
# Je Regel ein Negativbeispiel (MUSS anschlagen) und ein Positivbeispiel (DARF NICHT anschlagen).
TESTS = {
    'dauer': ('Beim Hack seht ihr die Leute zwei Tage lang beim Bauen, volle 48h.',
              '250 Leute von TUM und LMU, 24 Stunden bauen.'),
    'datum': ('Der Summit am 09.12.2026, oder am 9.12., als ISO 2026-12-09, und der Hack am 20.–21.11.2026.',
              'Der Summit findet am 07.12.2026 statt, der Hack am 21. und 22. November, genauer 21.–22.11.2026.'),
    'gaeste': ('Der Summit mit 350 Gästen ist unser Jahresabschluss. Diesmal 500 Gäste fix.',
               'Wir planen dort aktuell 500 Gäste ein, around 500 guests.'),
    'preis': ('Das Challenge-Paket liegt bei 10.000 € bzw. 10k oder $10,000.',
              'Pakete besprechen wir am besten kurz im Call.'),
    'emdash': ('Wir bauen — und zwar richtig.',
               'Wir bauen richtig, mit En-Dash-Datum 21.–22.11.'),
    'ichform': ('Ich hatte dir im Mai geschrieben, ich habe euch letztes Jahr kontaktiert und ich war damals bei euch im Call.',
                'Kollegin A hatte dir im Mai geschrieben, und Kollege B war bei euch im Call.'),
    'antipattern': ('Genau da kommen wir ins Spiel: der direkteste Zugang zum Talent-Pool.',
                    'Ich hab direkt an Testfirma gedacht, weil da die Leute sitzen, die selbst bauen.'),
    'konkurrenz': ('Ihr wart dieses Jahr ja bei CDTM und TUM.ai, dieselbe Zielgruppe.',
                   'Beim Hack seht ihr die Leute live beim Bauen, nicht nur von der Bühne aus.'),
}


def selbsttest(fakten):
    fehler = 0
    for rid, beschreibung, fn in REGELN:
        schlecht, gut = TESTS[rid]
        schlaegt_an = bool(fn(schlecht, fakten))
        bleibt_still = not fn(gut, fakten)
        status = 'PASS' if (schlaegt_an and bleibt_still) else 'FAIL'
        if status == 'FAIL':
            fehler += 1
            detail = []
            if not schlaegt_an:
                detail.append('Negativbeispiel NICHT erkannt')
            if not bleibt_still:
                detail.append(f'Fehlalarm auf Positivbeispiel: {fn(gut, fakten)}')
            print(f'[{status}] {rid:12} {beschreibung} - {"; ".join(detail)}')
        else:
            print(f'[{status}] {rid:12} {beschreibung}')
    print(f'\n{len(REGELN)} Regeln, {len(REGELN)-fehler} bestanden, {fehler} durchgefallen')
    return 1 if fehler else 0


def main(argv):
    fakten = lade_fakten()
    if '--selbsttest' in argv:
        return selbsttest(fakten)
    if '--text' in argv:
        text = argv[argv.index('--text') + 1]
        befunde = linte(text, fakten)
        for rid, meldung in befunde:
            print(f'  [{rid}] {meldung}')
        print('sauber' if not befunde else f'{len(befunde)} Verstoss/Verstoesse')
        return 1 if befunde else 0
    dateien = [a for a in argv if not a.startswith('-')]
    if not dateien:
        print(__doc__.split('Aufruf:')[1].split('Exit')[0], file=sys.stderr)
        return 2
    gesamt = sum(linte_datei(d, fakten) for d in dateien)
    return 1 if gesamt else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
