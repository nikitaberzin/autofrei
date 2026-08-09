# PLAN: Autofreie Bike-Tage — Scheduled Skill

> Abgeleitet aus SPEC.md. Von oben nach unten abarbeiten. Häkchen erst setzen,
> wenn der Verify-Schritt bestanden ist. Wenn eine Aufgabe eine Entscheidung
> braucht, die nicht in SPEC.md steht: **stoppen und nachfragen — nicht raten.**

Arbeitsverzeichnis für alle Pfade: `~/claude/01 Projects/autofrei/`

## Prerequisites

- [x] `python3 --version` → 3.9 oder neuer
- [x] `gh auth status` → eingeloggt als `nikitaberzin`
- [x] SPEC.md gelesen, insbesondere „Datenquelle — verifizierte Struktur"

---

## Phase 1 — Datenbeschaffung

- [x] **1. Projektstruktur anlegen**
  - Files: `scripts/`, `data/`, `docs/`, `assets/`, `skills/autofrei-check/`
  - Details: Nur leere Ordner. Noch kein Git.
  - Depends on: none
  - Verify: `ls -d scripts data docs assets skills/autofrei-check` → alle 5 existieren

- [x] **2. robots.txt von freipass.ch prüfen**
  - Files: keine
  - Details: `curl -s https://www.freipass.ch/robots.txt` abrufen. Prüfen, ob
    `/index.php` oder `/fpscripts3.js` für User-Agent `*` gesperrt sind.
    **Wenn gesperrt: hier stoppen und den User fragen** — nicht einfach
    weitermachen.
  - Depends on: 1
  - Verify: Ergebnis dokumentiert; kein `Disallow` für die zwei Pfade

- [x] **3. Parser schreiben**
  - Files: `scripts/fetch_events.py`
  - Details: Funktionen exakt nach SPEC.md „Data model / contracts".
    Die beiden Regexe aus SPEC.md „Datenquelle" **wörtlich übernehmen** — sie
    sind gegen die echte Seite verifiziert. User-Agent setzen:
    `Mozilla/5.0 (compatible; autofrei-bot/1.0; +https://github.com/nikitaberzin/autofrei)`.
    Timeout 30 s. Alle Edge Cases aus SPEC.md implementieren, besonders die
    50-Event-Untergrenze und „bei Fehler nichts überschreiben".
  - Depends on: 2
  - Verify: `python3 scripts/fetch_events.py` → Exit 0, `data/events.json`
    existiert

- [x] **4. Parser-Ergebnis prüfen**
  - Files: `data/events.json`
  - Details: Die Zahlen gegen SPEC.md „Acceptance criteria" prüfen.
  - Depends on: 3
  - Verify:
    ```bash
    python3 -c "
    import json; d=json.load(open('data/events.json'))
    from collections import Counter
    assert d['eventCount']==len(d['events'])
    print('Events:', d['eventCount'])
    print('Länder:', Counter(e['country'] for e in d['events']))
    print('ohne Koords:', sum(1 for e in d['events'] if e['lat'] is None))
    print('ohne Datum:', sum(1 for e in d['events'] if e['dateStart'] is None))
    s=[e for e in d['events'] if 'Sellaronda Bike Day'==e['name']][0]
    assert s['dateStart']=='2026-06-06', s
    assert abs(s['lat']-46.5499)<0.01
    print('Sellaronda OK')
    assert not any(e['country']=='de' for e in d['events'])
    print('kein DE OK')
    "
    ```
    → 102 Events, Länder nur `it/at/fr/ch`, „Sellaronda OK", „kein DE OK"

- [x] **5. Fehlerpfade testen**
  - Files: keine (temporäre Kopie)
  - Details: `data/events.json` sichern. Dann (a) mit unerreichbarer URL
    laufen lassen, (b) mit absichtlich kaputtem `EVENT_RE`. In beiden Fällen
    muss `data/events.json` **unverändert** bleiben.
  - Depends on: 4
  - Verify: beide Läufe Exit-Code 1; `md5 data/events.json` vor und nach
    identisch

---

## Phase 2 — Outputs

- [x] **6. ICS-Generator**
  - Files: `scripts/build_ics.py`
  - Details: Format exakt nach SPEC.md „ICS-Format". Achtung: `DTEND` ist
    exklusiv (`dateEnd + 1 Tag`), CRLF-Zeilenenden, Zeilen auf 75 Oktetts
    falten, TEXT-Escaping. Events mit `dateStart == null` überspringen.
  - Depends on: 4
  - Verify:
    ```bash
    python3 scripts/build_ics.py && python3 -c "
    d=open('docs/autofrei.ics','rb').read()
    assert d.startswith(b'BEGIN:VCALENDAR')
    assert d.rstrip().endswith(b'END:VCALENDAR')
    assert b'\r\n' in d and d.count(b'\n')==d.count(b'\r\n')
    assert not d.startswith(b'\xef\xbb\xbf'), 'BOM gefunden'
    print('VEVENTs:', d.count(b'BEGIN:VEVENT'))
    "
    ```
    → keine Assertion-Fehler, VEVENT-Anzahl == Events mit Datum

- [x] **6b. Karten-Seite + GeoJSON-Generator**
  - Files: `scripts/build_map.py` → `docs/karte.html`, `docs/autofrei.geojson`
  - Details: Nach SPEC.md „Karten-Seite" und „GeoJSON-Export". **Zwei
    Stolperfallen, die im Spec stehen:** Esri-Tiles brauchen `{z}/{y}/{x}`
    (nicht `{z}/{x}/{y}`), GeoJSON braucht `[lng, lat]` (nicht `[lat, lng]`).
    Leaflet 1.9.4 vom CDN mit SRI-Hashes. Kein API-Key.
  - Depends on: 4
  - Verify:
    ```bash
    python3 scripts/build_map.py && python3 -c "
    import json; g=json.load(open('docs/autofrei.geojson'))
    assert g['type']=='FeatureCollection'
    s=[f for f in g['features'] if f['properties']['name']=='Sellaronda Bike Day'][0]
    lng,lat=s['geometry']['coordinates']
    assert 11<lng<12 and 46<lat<47, ('lng/lat vertauscht!', lng, lat)
    print('Features:', len(g['features']), '— Koordinatenreihenfolge OK')
    "
    grep -c '{z}/{y}/{x}' docs/karte.html
    ```
    → „Koordinatenreihenfolge OK"; grep findet ≥ 1 Treffer

- [x] **7. HTML-Generator**
  - Files: `scripts/build_html.py`
  - Details: Darstellung exakt nach SPEC.md „HTML-Artifact — Darstellung".
    **Kein `<!DOCTYPE>`, `<html>`, `<head>`, `<body>`** — das Artifact-Tool
    wrappt selbst. `<title>` setzen. Alles inline, keine externen Ressourcen.
    Beide Theme-Signale (`prefers-color-scheme` **und** `[data-theme]`).
    Output nach `data/artifact.html`.
  - Depends on: 4
  - Verify:
    ```bash
    python3 scripts/build_html.py && python3 -c "
    import re; h=open('data/artifact.html',encoding='utf-8').read()
    assert '<!doctype' not in h.lower() and '<body' not in h.lower()
    assert '<title>' in h
    ext=re.findall(r'(?:src|href)=\"https?://[^\"]+', h)
    print('externe Refs (nur Event-Links erlaubt):', len(ext))
    assert 'data-theme' in h and 'prefers-color-scheme' in h
    print('OK')
    "
    ```
    → „OK"; externe Refs ausschließlich Event-Organisator-Links

- [x] **8. HTML visuell prüfen**
  - Files: keine
  - Details: `data/artifact.html` im Browser bei 375 px und 1280 px Breite
    ansehen, hell und dunkel.
  - Depends on: 7
  - Verify: kein horizontales Scrollen bei 375 px; in beiden Themes lesbar;
    Land-Filter funktionieren; nächstes Event oben hervorgehoben

---

## Phase 3 — GitHub + Hosting

- [x] **9a. Git-Identität lokal anonymisieren (VOR dem ersten Commit)**
  - Files: `.git/config` (nur lokal, nicht im Repo-Inhalt)
  - Details: Siehe SPEC.md „Datenschutz". `git init`, dann:
    ```bash
    ID=$(gh api user --jq .id)
    git config user.email "${ID}+nikitaberzin@users.noreply.github.com"
    git config user.name "nikitaberzin"
    ```
    **Ohne `--global`.** Muss vor dem ersten Commit passieren — nachträglich
    ist die E-Mail in der History und nur per Rewrite zu entfernen.
  - Depends on: 6, 6b, 7
  - Verify: `git config user.email` → enthält `users.noreply.github.com`,
    **nicht** `outlook.com`

- [x] **9b. Repo anlegen, Leak-Check, dann pushen**
  - Files: `.gitignore`, `README.md`
  - Details: `.gitignore` für `__pycache__/`, `*.pyc`. README mit
    Kurzbeschreibung + Abo-Anleitung (**ohne** E-Mail-Adressen). Erst
    committen, dann **vor dem Push** den Leak-Check unten laufen lassen.
    Erst wenn der sauber ist:
    `gh repo create nikitaberzin/autofrei --public --source=. --remote=origin --push`
  - Depends on: 9a
  - Verify — **alle drei müssen leer ausgeben**:
    ```bash
    # 1. E-Mail-Adressen im Inhalt
    git grep -nIE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' -- . \
      | grep -v 'users.noreply.github.com' | grep -v '@autofrei.freipass'
    # 2. Credentials im Inhalt
    git grep -nIiE '(password|passwort|secret|api[_-]?key|token|bearer)' -- .
    # 3. E-Mail in Commit-Metadaten
    git log --format='%ae %an' | grep -viE 'users\.noreply\.github\.com'
    ```
    Danach: `gh repo view nikitaberzin/autofrei --json visibility` → `PUBLIC`

    **Wenn Check 3 etwas findet: NICHT pushen.** Stattdessen stoppen, den
    User informieren und Repo/History neu aufsetzen.

- [x] **10. GitHub Pages aktivieren**
  - Files: `docs/index.html`
  - Details: Landing-Page mit Abo-Anleitung für Outlook / Google / Apple.
    Pages auf Branch `main`, Ordner `/docs` stellen (über
    `gh api -X POST repos/nikitaberzin/autofrei/pages` oder Web-UI).
  - Depends on: 9b
  - Verify: nach ~2 Min
    `curl -sI https://nikitaberzin.github.io/autofrei/autofrei.ics | head -3`
    → `HTTP/2 200` und `content-type: text/calendar`

    **Wenn der Content-Type nicht `text/calendar` ist: stoppen und den User
    informieren** — dann schlagen Outlook-Abos fehl (SPEC-Decision zum
    Hosting).

- [x] **11. Artifact veröffentlichen**
  - Files: `data/artifact-url.txt`
  - Details: `data/artifact.html` über das `Artifact`-Tool publishen.
    `favicon`: `🚲`. Zurückgegebene URL in `data/artifact-url.txt` speichern.
  - Depends on: 8
  - Verify: `cat data/artifact-url.txt` → eine `https://`-URL; Seite lädt

- [ ] **12. ICS-Abo real testen**
  - Files: keine
  - Details: **Der User** abonniert die Pages-URL in Google Calendar
    („Über URL hinzufügen"). Der Implementer kann das nicht selbst tun —
    das ist ein manueller Check.
  - Depends on: 10
  - Verify: User bestätigt, dass Events im Kalender erscheinen

---

## Phase 4 — Skill + Automatisierung

- [x] **13. SKILL.md schreiben**
  - Files: `skills/autofrei-check/SKILL.md`
  - Details: Orchestriert den Ablauf aus SPEC.md „Behaviour" Schritt 1–11.
    Frontmatter mit `name` und `description`. Muss enthalten: Artifact-Update
    **immer** mit der URL aus `data/artifact-url.txt` (sonst entsteht jede
    Woche ein neues Artifact). Karte und GeoJSON werden bei jedem Lauf
    mitgeneriert.
  - Depends on: 11
  - Verify: Skill manuell aufrufen → läuft durch, Artifact behält dieselbe URL

- [ ] **14. Karte live prüfen + ArcGIS-Import**
  - Files: keine
  - Details: `https://nikitaberzin.github.io/autofrei/karte.html` im Browser
    öffnen (mobil + desktop). Danach **der User**: `autofrei.geojson` in
    ArcGIS Online als Layer importieren.
  - Depends on: 6b, 10
  - Verify: Basemap lädt (keine grauen Kacheln), Marker sichtbar, Popups mit
    Link funktionieren, Land-Layer umschaltbar; User bestätigt den
    ArcGIS-Import

- [ ] **15. Wöchentliche Routine einrichten** — BLOCKIERT (2026-08-09)
  - Blocker: Die Cloud-Routine wurde vom API abgelehnt:
    „Connect your GitHub account before saving a routine that uses a
    GitHub repository." Nikita muss GitHub einmalig verbinden
    (`/web-setup` oder https://claude.ai/code/onboarding?magic=github-app-setup),
    danach kann die Routine mit `0 5 * * 1` angelegt werden.
  - Files: keine
  - Details: Cloud-Routine, die den Skill aus Task 13 aufruft. Rhythmus:
    wöchentlich. **Vorschlag Montag 07:00** — vom User bestätigen lassen,
    falls er einen anderen Zeitpunkt will.
  - Depends on: 13
  - Verify: Routine erscheint in der Liste der geplanten Tasks

---

## Final verification

- [ ] Alle Acceptance Criteria aus SPEC.md abgehakt
- [ ] `python3 scripts/fetch_events.py && python3 scripts/build_ics.py && python3 scripts/build_map.py && python3 scripts/build_html.py` → alle Exit 0
- [ ] `karte.html` zeigt die Esri-Basemap; GeoJSON in ArcGIS Online importiert
- [ ] Zweiter Lauf direkt danach → kein Commit (nichts geändert), Artifact-URL unverändert
- [ ] `https://nikitaberzin.github.io/autofrei/autofrei.ics` liefert 200 + `text/calendar`
- [ ] User hat das ICS-Abo in mindestens einem Kalender bestätigt
- [ ] Datenschutz-Check (SPEC „Datenschutz") — alle vier leer:
  ```bash
  git log --format='%ae' | grep -viE 'users\.noreply\.github\.com'
  git grep -nIE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' -- . | grep -vE 'noreply\.github\.com|@autofrei\.freipass'
  git grep -nIiE '(password|passwort|secret|api[_-]?key|token|bearer)' -- .
  grep -iE '(ORGANIZER|ATTENDEE)' docs/autofrei.ics
  ```
