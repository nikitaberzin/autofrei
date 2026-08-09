# SPEC: Autofreie Bike-Tage — Scheduled Skill

> Audience: the implementer model. It follows this literally and does not
> re-derive reasoning. Decide things here so it doesn't have to.

## Goal

Ein wöchentlich laufender Skill liest die Event-Liste von
[freipass.ch](https://www.freipass.ch/) (autofreie Pass-/Straßentage in den
Alpen), filtert auf Italien/Dolomiten, Österreich, Frankreich und Schweiz und
erzeugt drei Outputs:

1. **HTML-Artifact** — responsive Übersicht (Desktop + Mobile), veröffentlicht
   über das `Artifact`-Tool.
2. **`autofrei.ics`** — abonnierbarer Kalender-Feed für Outlook, Google
   Calendar, Apple Kalender.
3. **Karten-Seite** — `karte.html` auf GitHub Pages mit echter Esri-Basemap.
4. **`autofrei.geojson`** — Export zum Import in ArcGIS Online (Esri-Account
   des Users).

Nutzer-Ergebnis: Nikita (und eine zweite Person) sehen alle autofreien Tage in
einer Übersicht und haben sie automatisch aktuell im eigenen Kalender.

## Assumptions

Der User soll diese zuerst prüfen und Falsches melden — bevor Code entsteht.

- [ ] Das GitHub-Repo `autofrei` ist **public**. Begründung: GitHub Pages
      braucht für kostenloses Hosting ein public Repo, und die Daten stammen
      ohnehin aus einer öffentlichen Quelle. Es liegen **keine** Credentials
      oder privaten Daten im Repo.
- [x] **Bestätigt vom User (2026-08-09):** GitHub-Account ist `nikitaberzin`.
      Zielrepo: `github.com/nikitaberzin/autofrei`, Pages-URL:
      `https://nikitaberzin.github.io/autofrei/autofrei.ics`.
      `gh` CLI ist dort eingeloggt und darf Repos anlegen und pushen.
- [ ] freipass.ch darf automatisiert wöchentlich (1×/Woche, 1 Request) gelesen
      werden. Das ist eine sehr geringe Last; es existiert keine robots.txt-
      Sperre für den Pfad `/`. **Vor dem ersten Lauf ist `robots.txt` zu
      prüfen** (siehe PLAN Task 2).
- [ ] Die HTML-Struktur von freipass.ch bleibt stabil. Sie wurde am
      2026-08-09 verifiziert (siehe „Datenquelle"). Bei Strukturänderung
      schlägt der Parser bewusst laut fehl statt still leere Daten zu liefern.
- [ ] Deutsch ist die Ausgabesprache für Artifact und Kalendereinträge.

## Decisions

Der Implementer darf diese **nicht** neu aufrollen.

- **Datenquelle ist ausschließlich freipass.ch** — der User hat sie explizit
  als Hauptquelle benannt; sie aggregiert bereits ~103 Events aus 6 Ländern.
- **Keine handkuratierte Event-Liste** — freipass.ch *ist* die kuratierte
  Quelle; eine zweite Liste würde nur auseinanderlaufen.
- **Parser in Python 3 (stdlib only)** — kein `pip install` nötig, läuft
  überall; `re` + `urllib` reichen für die verifizierte Struktur.
- **Zwei Quelldateien werden gelesen** — `index.php` (Datum, Name, Link,
  Land, Marker-ID) und `fpscripts3.js` (Koordinaten je Marker-ID). Die
  Koordinaten stehen nur im JS.
- **Kalender-Anbindung via ICS-Abo, nicht via OAuth** — vom User gewählt
  („weg a reicht vorerst"); die zweite Person abonniert denselben Feed. Es
  werden **keine** Einladungs-Mails verschickt und **kein** Kalenderkonto
  verbunden.
- **ICS-Hosting über GitHub Pages, nicht Gist** — Pages liefert `.ics` mit
  MIME-Type `text/calendar`; Gist-Raw liefert `text/plain` + `nosniff`, was
  Outlook-Abos ablehnen können.
- **Events sind ICS-Ganztagestermine (`VALUE=DATE`)** — freipass.ch nennt nur
  Tage, keine Uhrzeiten; erfundene Uhrzeiten wären falsche Daten.
- **`events.json` wird versioniert** — dient als Snapshot für den
  „Neu seit letztem Lauf"-Diff und als Koordinaten-Cache.
- **Ausführung als Cloud-Routine** — vom User gewählt; läuft auch bei
  ausgeschaltetem Mac.
- **Karte liegt auf GitHub Pages, NICHT als Artifact** — die Artifact-CSP
  blockiert jeden externen Host, also auch alle Tile-Server; auf Pages gibt es
  diese Beschränkung nicht. Damit ist eine echte Basemap möglich.
- **Esri-Tiles über `services.arcgisonline.com` ohne API-Key** — am
  2026-08-09 mit HTTP 200 verifiziert. Bewusst **nicht** die neue ArcGIS
  Location Platform: deren API-Key läge im public Repo offen.
- **Karte wird bei jedem Lauf mitgeneriert** — sie ist eine eigene Seite unter
  eigener URL und bläht die Liste nicht auf; „nur auf Anfrage" ist damit
  hinfällig.
- **Zusätzlich GeoJSON-Export für ArcGIS Online** — vom User gewählt; er hat
  einen Esri-Account und will dort eine eigene Web Map bauen.

## Datenschutz — harte Regel: keine Account-Daten im Repo

Vom User explizit gefordert (2026-08-09). Das Repo ist **public**, also gilt
ausnahmslos:

**Verboten im Repo — auch in der Git-History:**

- E-Mail-Adressen jeglicher Art (Nikita, zweite Person, Dritte)
- Die E-Mail der zweiten Person, die den ICS-Feed abonniert
- Esri-/ArcGIS-Credentials, API-Keys, Tokens, Passwörter
- Kalender-URLs mit eingebettetem Token (z. B. private Outlook-/Google-
  Feed-URLs)
- Klarname in Commit-Metadaten, sofern der User das nicht will

**Konkrete Maßnahmen:**

- **Git-Commit-E-Mail:** vor dem ersten Commit **lokal** (nur dieses Repo) auf
  die GitHub-Noreply-Adresse setzen:
  `git config user.email "<ID>+nikitaberzin@users.noreply.github.com"`.
  Die numerische `<ID>` kommt aus `gh api user --jq .id`.
  **Niemals `git config --global` ändern** — das würde Nikitas andere
  Projekte betreffen.
- **ICS:** **kein** `ORGANIZER`- und **kein** `ATTENDEE`-Feld. Beide würden
  E-Mail-Adressen enthalten. Der Feed ist ein reiner Abo-Kalender — er lädt
  niemanden ein (siehe Decisions: Weg A).
- Der Esri-Account wird **nur clientseitig vom User** in ArcGIS Online
  genutzt. Das Repo enthält lediglich `autofrei.geojson` — reine
  Event-Geodaten, keine Kontodaten.
- Die Tile-URLs enthalten **keinen** API-Key (bewusste Entscheidung, siehe
  Decisions).
- `SPEC.md` und `PLAN.md` dürfen ins Repo — sie enthalten nur den ohnehin
  öffentlichen GitHub-Usernamen, keine Kontaktdaten.

**Wenn doch etwas durchrutscht:** Ein `git rm` reicht nicht — die History muss
neu geschrieben oder das Repo neu angelegt werden. Deshalb wird **vor** dem
ersten Push geprüft (PLAN Task 9a).

## Scope

**In scope:**

- Parser für freipass.ch → `events.json`
- Diff gegen den letzten Snapshot → `isNew`-Markierung
- Generator für das responsive HTML-Artifact
- Generator für `autofrei.ics`
- Generator für Karten-Seite + GeoJSON (bei jedem Lauf)
- GitHub-Repo + Pages-Hosting für `.ics`, Karte und GeoJSON
- `SKILL.md`, die diese Schritte orchestriert
- Wöchentliche Cloud-Routine

**Non-goals / out of scope:**

- Keine OAuth-/API-Anbindung an Google oder Microsoft Kalender
- Kein Versand von Einladungs-Mails oder Benachrichtigungen an Dritte
- Keine weiteren Datenquellen (kein ciclista.net, kein bikehotels.it) —
  auch wenn freipass.ch dorthin verlinkt
- Kein Deutschland und kein Slowenien (Filter siehe unten)
- Keine Anmeldung/Registrierung zu Events
- Keine Höhenmeter-/Distanz-Daten — freipass.ch liefert sie für Events nicht
- Kein Login, keine Credentials, kein Bezahlvorgang
- **Keinerlei Account-Daten im Repo** — siehe Abschnitt „Datenschutz"

## Datenquelle — verifizierte Struktur

Verifiziert am 2026-08-09. **Diese Struktur nicht raten — sie ist exakt so.**

### A) Events: `https://www.freipass.ch/index.php`

Jedes Event ist genau ein `<li>`:

```html
<li><span class="date">6. Juni</span><a href="http://www.sellarondabikeday.com" target="_blank">Sellaronda Bike Day</a><div class="flag map it" onclick="openmap(1); showpop(sellarondabikeday126)"></div></li>
```

Neue Events tragen ein zusätzliches Span **innerhalb** des `<a>`:

```html
<a href="..." target="_blank">Passo San Marco<span class="highlight">Neu</span></a>
```

Verifiziertes Regex (liefert 103 Treffer):

```python
EVENT_RE = re.compile(
    r'<li><span class="date">(?P<date>.*?)</span>'
    r'<a href="(?P<url>.*?)".*?>(?P<name>.*?)</a>'
    r'<div class="flag map (?P<country>\w+)"[^>]*showpop\((?P<marker>\w+)\)',
    re.S,
)
```

Feldbedeutung:

| Feld | Beispielwerte | Hinweis |
|------|---------------|---------|
| `date` | `6. Juni`, `1.-5. Juni`, `30. Mai` | Deutsch, **ohne Jahr**; kann Bereich sein |
| `url` | Organisator-URL | extern, `target="_blank"` |
| `name` | `Sellaronda Bike Day` | kann `<span class="highlight">Neu</span>` enthalten → strippen |
| `country` | `it` `fr` `ch` `at` `de` | Ländercode |
| `marker` | `sellarondabikeday126` | **Orts**-Key, siehe Warnung unten |

Ist-Verteilung 2026: `fr` 46, `it` 40, `ch` 14, `at` 2, `de` 1 = 103.
Nach Filter auf die 4 Zielländer: **102 Events**.

> **⚠️ Die Marker-ID identifiziert den ORT, nicht das Event.**
> Verifiziert am 2026-08-09: `kloental26` kommt **dreimal** vor — Slow Sundays
> Klöntal am 28. Juni, 26. Juli und 30. August. Derselbe Pass, drei autofreie
> Termine, ein Marker.
> Dedup allein über die Marker-ID löscht deshalb echte Events.
> **Event-Schlüssel ist `marker + "__" + dateStart`.**

> **⚠️ Nicht jeder `<span class="date">` ist ein Event.**
> Die Seite enthält 109 solcher Spans, aber nur 103 Events. Die übrigen 6
> gehören zur Statistik-Tabelle (`<span class="date">Frankreich</span>` +
> `<p class="comment">48 (-7)</p>`). Sie haben **kein** `showpop(...)` und
> werden vom Regex automatisch aussortiert — das ist korrekt, kein Datenverlust.
>
> Nebenbefund: Die Seite nennt in dieser Tabelle andere Zahlen (FR 48, IT 41)
> als ihre eigene Liste hergibt (FR 46, IT 40). Der eigene Zähler von
> freipass.ch ist also leicht ungenau. **Maßgeblich ist die geparste Liste.**

> **⚠️ freipass.ch hat einen Soft-404.**
> Verifiziert: `https://www.freipass.ch/gibtesnicht-404.php` antwortet mit
> **HTTP 200**. Der Statuscode allein beweist also nicht, dass die richtige
> Seite geladen wurde. Der eigentliche Schutz ist der `MIN_EVENTS`-Check.

Das Saison-Jahr steht in einer Überschrift: `<h…>Saison 2026</h…>`.
Regex: `r'Saison\s+(\d{4})'` — daraus stammt das Jahr für alle Events.

### B) Koordinaten: `https://www.freipass.ch/fpscripts3.js`

```js
const sellarondabikeday126 = L.marker([46.54994026869288, 11.809057755038467], {icon: fpmarker3}).bindPopup('...').addTo(paesse26)
```

Verifiziertes Regex:

```python
COORD_RE = re.compile(
    r'(?:const|let|var)\s+(?P<marker>\w+)\s*=\s*L\.marker\('
    r'\[(?P<lat>-?[\d.]+),\s*(?P<lng>-?[\d.]+)\]'
)
```

Die Datei enthält 225 `L.marker`-Aufrufe (auch Vorjahre und
„empfehlenswerte Pässe"). **Join über die Marker-ID aus dem HTML** — dadurch
fallen Fremd-Marker automatisch weg. Nicht über `.addTo(paesse26)` filtern.

## Data model / contracts

`data/events.json` — **exakt dieses Schema**:

```jsonc
{
  "source": "https://www.freipass.ch/",
  "season": 2026,
  "fetchedAt": "2026-08-09",          // ISO-Datum des Laufs
  "eventCount": 102,
  "events": [
    {
      "id": "sellarondabikeday126__2026-06-06",  // marker + "__" + dateStart
      "marker": "sellarondabikeday126",          // Orts-Key, Join zu Koordinaten
      "name": "Sellaronda Bike Day",  // ohne "Neu"-Span
      "country": "it",                // it | at | fr | ch
      "dateRaw": "6. Juni",           // Originaltext von freipass.ch
      "dateStart": "2026-06-06",      // ISO; null wenn unparsebar
      "dateEnd": "2026-06-06",        // ISO; bei Bereich der letzte Tag
      "url": "http://www.sellarondabikeday.com",  // null wenn "#" oder leer
      "lat": 46.54994026869288,       // null wenn kein Marker-Match
      "lng": 11.809057755038467,      // null wenn kein Marker-Match
      "isNewOnSite": false,           // freipass.ch selbst markiert es als "Neu"
      "isNew": false                  // true = seit UNSEREM letzten Snapshot neu
    }
  ]
}
```

Python-Signaturen, die der Implementer so ausschreibt:

```python
# scripts/fetch_events.py
def fetch(url: str) -> str: ...
def parse_season(html: str) -> int: ...
def parse_events(html: str, season: int) -> list[dict]: ...
def parse_coords(js: str) -> dict[str, tuple[float, float]]: ...
def parse_german_date(raw: str, season: int) -> tuple[str, str]: ...
def diff_new(events: list[dict], previous_path: str) -> list[dict]: ...
def main() -> int: ...   # 0 = ok, 1 = Fehler

# scripts/build_ics.py
def build_ics(events: list[dict]) -> str: ...

# scripts/build_html.py
def build_html(data: dict) -> str: ...

# scripts/build_map.py
def build_map(data: dict) -> str: ...
```

### Datums-Parsing — deutsche Monate

Mapping (Quelle nutzt volle Namen):

```python
MONATE = {"Januar":1,"Februar":2,"März":3,"April":4,"Mai":5,"Juni":6,
          "Juli":7,"August":8,"September":9,"Oktober":10,"November":11,"Dezember":12}
```

Zu unterstützende Formate:

| Rohtext | `dateStart` | `dateEnd` |
|---------|-------------|-----------|
| `6. Juni` | `2026-06-06` | `2026-06-06` |
| `1.-5. Juni` | `2026-06-01` | `2026-06-05` |
| `30. Mai-2. Juni` | `2026-05-30` | `2026-06-02` |

Bindestrich-Varianten `-`, `–`, `—` alle akzeptieren. Whitespace um den
Bindestrich ist optional.

## Behaviour

Ablauf eines wöchentlichen Laufs:

1. `index.php` und `fpscripts3.js` laden (User-Agent setzen, 30 s Timeout).
2. Saison-Jahr aus `Saison (\d{4})` lesen.
3. Events parsen. **Wenn < 50 Events gefunden → Abbruch mit Fehler** (siehe
   Edge Cases), nichts überschreiben.
4. Auf `country in {"it","at","fr","ch"}` filtern.
5. Koordinaten joinen; kein Match → `lat`/`lng` = `null`.
6. Deutsche Daten in ISO umrechnen.
7. Gegen bestehende `data/events.json` diffen: ID nicht im alten Snapshot →
   `isNew: true`. Existiert keine alte Datei (Erstlauf) → alle `isNew: false`.
8. `data/events.json`, `docs/autofrei.ics` schreiben.
9. HTML generieren und via `Artifact`-Tool veröffentlichen (bei Updates
   dieselbe URL, siehe „Artifact-Update").
10. Nach GitHub pushen (nur wenn sich etwas geändert hat).
11. Zusammenfassung ausgeben: Gesamtzahl, neue Events, nächstes Event.

### HTML-Artifact — Darstellung

- **Kopf:** Titel, „Quelle: freipass.ch", Stand-Datum, Gesamtzahl.
- **Nächstes Event hervorgehoben** — eigene Karte ganz oben mit
  „in X Tagen". Der Countdown wird **im Browser** gerechnet, nicht beim Build:
  die Seite kann Tage nach der Generierung geöffnet werden.
- **Filter-Buttons** nach Land, reines CSS/JS, ohne externe Requests. Es
  erscheinen nur Länder mit mindestens einem **kommenden** Termin (2026-08-09
  z. B. ohne Österreich), jeweils mit Anzahl.
- **Gruppierung nach Monat**, innerhalb chronologisch.
- **Pro Event:** Wochentag, Tag, Name, Land-Chip, `neu`-Badge falls `isNew`,
  Link zum Organisator (`target="_blank" rel="noopener noreferrer"`).
- **Datum ohne Monatsnamen**, solange der Monat schon in der Gruppenüberschrift
  steht (`9.` statt `9. August`). Monatsübergreifende Bereiche behalten den
  Volltext. Grund: mit Monatsnamen lief die Datumsspalte in die Nachbarspalte —
  in der ersten Fassung real reproduziert.
- **Wochentag wird angezeigt** — bei einem Bike-Day ist „ist das ein Samstag?"
  die erste Frage; die meisten Termine liegen am Wochenende.
- **Responsive:** einspaltiger Fahrplan, `max-width: 47rem`. Unter 29 rem
  rutscht das Datum über den Namen. Touch-Ziele ≥ 44 px über
  `@media (pointer: coarse)` — nicht über die Fensterbreite, ein schmales
  Desktop-Fenster braucht keine Fingergrößen.

> **Abweichungen von der ersten Fassung dieses Specs** (beim Bauen mit den
> echten 102 Events korrigiert):
>
> | ursprünglich | jetzt | Grund |
> |---|---|---|
> | Karten-Grid ab 768 px | einspaltiger Fahrplan | 102 chronologische Termine scannt man als Liste, nicht als 102 Karten |
> | Vergangene ausgegraut, ans Ende | eingeklappt in `<details>` | 75 von 102 sind vergangen — ausgegraut wäre die Seite zu drei Vierteln Altlast |
- **Theme-aware:** `@media (prefers-color-scheme: dark)` **plus**
  `:root[data-theme="dark"]` / `:root[data-theme="light"]` Overrides.
- **Self-contained:** alles inline, keine externen Fonts/Skripte/Bilder
  (Artifact-CSP blockiert sie).
- **ICS-Hinweis** im Fuß: Abo-URL + kurze Anleitung.

### Karten-Seite `docs/karte.html` (GitHub Pages)

Läuft **nicht** unter der Artifact-CSP — externe Ressourcen sind hier erlaubt.

- **Leaflet 1.9.4 vom CDN** (`unpkg.com`), CSS und JS, jeweils mit
  `integrity`- und `crossorigin`-Attribut (SRI).
- **Basemap:** zwei umschaltbare Layer über `L.control.layers`:
  - `Esri World Topo` (Default) —
    `https://services.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}`
  - `Esri World Imagery` —
    `.../World_Imagery/MapServer/tile/{z}/{y}/{x}`
  - **Achtung Achsenreihenfolge:** Esri nutzt `{z}/{y}/{x}`, nicht
    `{z}/{x}/{y}`. Falsch herum = leere Kacheln.
  - `attribution: 'Tiles © Esri'`, `maxZoom: 17`
- **Kein API-Key.** Verifiziert: die Endpoints antworten ohne Key mit 200.
- **Marker** pro Event mit Koordinaten, eingefärbt nach Land
  (`it` `#009246`, `at` `#e07b00`, `fr` `#0055a4`, `ch` `#d52b1e`).
  Popup: Name, Datum, Land, Link zum Organisator.

> **⚠️ Österreich ist bewusst NICHT flaggenrot.**
> Erste Fassung nutzte `#ed2939` (AT) neben `#d52b1e` (CH) — auf der Karte
> waren die Punkte nicht unterscheidbar, da Marker kein Label tragen.
> Vier klar trennbare Farbtöne schlagen hier Flaggentreue. Dieselbe Korrektur
> gilt im HTML-Artifact (`--at`).
- **Layer-Gruppe je Land**, über dieselbe `L.control.layers` einzeln
  ein-/ausblendbar.
- **Initialer Ausschnitt:** `fitBounds` über alle Marker.
- Events **ohne** Koordinaten werden unterhalb der Karte als Liste
  „Ohne Koordinaten" ausgegeben — nicht stillschweigend verschlucken.
- Responsive: Karte `height: 70vh` mobil, `85vh` ab 768 px.
- Link zurück zur Listen-Übersicht und zu `index.html`.

### GeoJSON-Export `docs/autofrei.geojson`

Für den Import in ArcGIS Online (Esri-Account des Users). Standard
`FeatureCollection`, nur Events **mit** Koordinaten:

```jsonc
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { "type": "Point", "coordinates": [11.809057755038467, 46.54994026869288] },
      "properties": {
        "name": "Sellaronda Bike Day",
        "country": "it",
        "date": "2026-06-06",     // == dateStart
        "dateEnd": "2026-06-06",
        "dateRaw": "6. Juni",
        "url": "http://www.sellarondabikeday.com",
        "isNew": false
      }
    }
  ]
}
```

**Achtung:** GeoJSON-Koordinaten sind `[lng, lat]` — umgekehrt zu Leaflet.
Vertauschen legt alle Pins in den Indischen Ozean.

### Artifact-Update

Beim ersten Lauf entsteht eine neue Artifact-URL. Diese URL wird in
`data/artifact-url.txt` gespeichert. **Alle Folgeläufe geben sie als `url`-
Parameter an das `Artifact`-Tool** — sonst entsteht jede Woche ein neues
Artifact statt eines aktualisierten.

## ICS-Format

- Ganztagestermine mit `VALUE=DATE`.
- `DTEND` ist im ICS-Standard **exklusiv** → `dateEnd + 1 Tag`.
- `UID` = `{id}@autofrei.freipass` — stabil, damit Updates keine Duplikate
  erzeugen.
- Zeilen auf 75 Oktetts falten (CRLF + Leerzeichen), Zeilenende **CRLF**.
- Escaping in TEXT-Feldern: `\` → `\\`, `;` → `\;`, `,` → `\,`,
  Zeilenumbruch → `\n`.
- Kalendername via `X-WR-CALNAME:Autofreie Bike-Tage`.
- `REFRESH-INTERVAL;VALUE=DURATION:P1W` und `X-PUBLISHED-TTL:P1W` setzen.
- **Kein `ORGANIZER`, kein `ATTENDEE`** — beide enthalten E-Mail-Adressen
  (siehe „Datenschutz").

Beispiel-Event (Zielausgabe, exakt dieses Format):

```
BEGIN:VEVENT
UID:sellarondabikeday126__2026-06-06@autofrei.freipass
DTSTAMP:20260809T000000Z
DTSTART;VALUE=DATE:20260606
DTEND;VALUE=DATE:20260607
SUMMARY:🚲 Sellaronda Bike Day (IT)
DESCRIPTION:Autofreier Tag\nQuelle: freipass.ch
URL:http://www.sellarondabikeday.com
GEO:46.549940;11.809058
END:VEVENT
```

`GEO` weglassen wenn `lat`/`lng` `null` sind.

## Edge cases & error handling

Der Implementer behandelt **genau diese** Fälle:

- **freipass.ch nicht erreichbar / HTTP ≠ 200** → Abbruch mit Exit-Code 1,
  Fehlermeldung, **bestehende `events.json` und `.ics` bleiben unverändert**.
  Niemals mit leeren Daten überschreiben.
- **Weniger als 50 Events geparst** → Strukturänderung annehmen. Abbruch mit
  Exit-Code 1 und Meldung „Parser lieferte nur N Events — HTML-Struktur von
  freipass.ch vermutlich geändert, Regex prüfen." Nichts schreiben.
- **`Saison (\d{4})` nicht gefunden** → Abbruch mit Exit-Code 1. Jahr **nicht**
  raten — falsche Jahreszahlen erzeugen falsche Kalendereinträge.
- **Datum nicht parsebar** → Event trotzdem übernehmen, `dateStart`/`dateEnd`
  = `null`, Warnung ausgeben. Im HTML unter „Termin unklar" listen, **im ICS
  weglassen**.
- **Marker-ID ohne Koordinaten-Match** → `lat`/`lng` = `null`, kein Fehler.
- **Erstlauf ohne alte `events.json`** → alle `isNew: false` (nicht alle 102
  als „neu" markieren).
- **Event-URL ist `#` oder leer** → Event listen, aber ohne Link.
- **Doppelte Marker-IDs im HTML** → **kein Fehler, kein Dedup.** Derselbe Pass
  hat oft mehrere Termine (verifiziert: `kloental26` 3×). Erst ein doppelter
  *zusammengesetzter* Schlüssel (`marker__dateStart`) ist eine echte Dublette
  → erste gewinnt, Warnung.
- **Timeout / Verbindungsabbruch bei freipass.ch** → bis zu 3 Versuche mit
  20 s Pause. Erst danach Exit 1. Im Test ist die Seite bei schneller
  Abfolge tatsächlich getimeoutet — ohne Retry wäre ein Wochenlauf ausgefallen.
- **Keine Änderung gegenüber letztem Lauf** → kein Commit, kein Push,
  Artifact trotzdem mit neuem Stand-Datum aktualisieren.
- **Umlaute** → alle Dateien UTF-8 lesen und schreiben, ICS ohne BOM.

## Files touched

Alle Pfade relativ zu `~/claude/01 Projects/autofrei/`.

| Pfad | Status | Zweck |
|------|--------|-------|
| `SPEC.md` | vorhanden | dieses Dokument |
| `PLAN.md` | vorhanden | Task-Liste |
| `scripts/fetch_events.py` | neu | Parser → `events.json` |
| `scripts/build_ics.py` | neu | ICS-Generator |
| `scripts/build_html.py` | neu | HTML-Generator |
| `scripts/build_map.py` | neu | Karten-Seite + GeoJSON-Export |
| `data/events.json` | neu | Snapshot + Koordinaten-Cache |
| `data/artifact.html` | neu | generiertes Artifact-Markup |
| `data/artifact-url.txt` | neu | URL des Listen-Artifacts |
| `.claude/launch.json` | neu | lokaler Preview-Server zum Sichtprüfen |
| `docs/autofrei.ics` | neu | Kalender-Feed (GitHub Pages) |
| `docs/autofrei.geojson` | neu | Export für ArcGIS Online |
| `docs/karte.html` | neu | Leaflet-Karte mit Esri-Basemap |
| `docs/index.html` | neu | Landing-Page: Abo-Anleitung + Links |
| `skills/autofrei-check/SKILL.md` | neu | Orchestrierung |
| `README.md` | neu | Kurzbeschreibung + Abo-Anleitung |

`docs/` ist der Publish-Ordner von GitHub Pages (Branch `main`, Ordner
`/docs`).

## Acceptance criteria (Definition of Done)

- [ ] `python3 scripts/fetch_events.py` erzeugt `data/events.json` mit
      **102 Events** (Stand 2026-08-09) und den Ländern `it`, `at`, `fr`, `ch`.
- [ ] Kein Event hat `country == "de"`.
- [ ] Sellaronda Bike Day ist enthalten mit `dateStart == "2026-06-06"` und
      `lat`/`lng` ≈ `46.5499` / `11.8091`.
- [ ] Mindestens ein Bereichs-Datum (z. B. `1.-5. Juni`) hat
      `dateEnd > dateStart`.
- [ ] Bei simuliertem Netzwerkfehler bleibt eine vorhandene `events.json`
      unverändert und der Exit-Code ist 1.
- [ ] Bei künstlich kaputtem Regex (< 50 Treffer) bricht das Skript ab und
      schreibt nichts.
- [ ] `docs/autofrei.ics` validiert gegen
      `python3 -c "import icalendar"` **oder**, falls nicht installiert,
      erfüllt manuell: beginnt mit `BEGIN:VCALENDAR`, endet mit
      `END:VCALENDAR`, CRLF-Zeilenenden, `VEVENT`-Anzahl == Events mit Datum.
- [ ] Das ICS lässt sich in Google Calendar per „Über URL hinzufügen"
      abonnieren und zeigt die Events (manueller Check durch den User).
- [ ] Das HTML-Artifact rendert bei 375 px Breite ohne horizontales Scrollen.
- [ ] Das HTML-Artifact ist in hellem **und** dunklem Theme lesbar.
- [ ] Das HTML-Artifact lädt keine externen Ressourcen (Prüfung: kein
      `http://` oder `https://` in `src=`/`href=` außer Event-Links mit
      `target="_blank"`).
- [ ] `docs/karte.html` zeigt die Esri-Topo-Basemap (keine leeren Kacheln →
      Achsenreihenfolge `{z}/{y}/{x}` korrekt) und alle Marker.
- [ ] Land-Layer der Karte lassen sich einzeln ein-/ausblenden.
- [ ] `docs/autofrei.geojson` ist valides GeoJSON, Koordinaten in der
      Reihenfolge `[lng, lat]` — Stichprobe Sellaronda: `[11.80…, 46.54…]`.
- [ ] `autofrei.geojson` lässt sich in ArcGIS Online als Layer importieren und
      die Pins liegen in den Alpen (manueller Check durch den User).
- [ ] Folgeläufe aktualisieren **dieselbe** Artifact-URL.
- [ ] `data/artifact-url.txt` enthält nach dem ersten Lauf eine URL.
- [ ] Die wöchentliche Routine ist angelegt und in `CronList`/
      `list_scheduled_tasks` sichtbar.
