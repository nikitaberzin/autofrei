# CLAUDE.md — Autofreie Bike-Tage

Hinweise für Claude Code in diesem Repo. `SPEC.md` erklärt die Entscheidungen,
`PLAN.md` den Bauverlauf. Hier stehen die **Fallen**, die beim Bauen echt
zugeschlagen haben — jeweils mit Symptom, Ursache und Gegenmittel.

## Was das Projekt tut

Parst autofreie Pass- und Straßentage aus zwei Quellen, filtert auf
IT/AT/FR/CH und erzeugt Kalender-Feed, Karte, GeoJSON und ein Artifact.

```bash
python3 scripts/fetch_events.py   # beide Quellen -> data/events.json
python3 scripts/build_ics.py      # -> docs/autofrei.ics
python3 scripts/build_map.py      # -> docs/karte.html, docs/autofrei.geojson
python3 scripts/build_html.py     # -> data/artifact.html, docs/index.html
```

`fetch_events.py` bindet `fetch_slowup.py` ein. Ablauf des Wochenlaufs:
`skills/autofrei-check/SKILL.md`.

---

## Fallen in den Datenquellen

**Die Marker-ID bei freipass.ch identifiziert den ORT, nicht das Event.**
`kloental26` kommt dreimal vor (Slow Sundays Klöntal an drei Terminen).
Dedup allein über die Marker-ID löscht echte Events — der Schlüssel ist
`marker + "__" + dateStart`. Kostete 2 von 102 Events, bevor es auffiel.

**Nicht jeder `<span class="date">` ist ein Event.** Die Seite hat 109 davon,
aber nur 103 Events. Die übrigen 6 sind die Statistik-Tabelle
(`<span class="date">Frankreich</span>`). Sie haben kein `showpop(...)` und
fallen durch das Regex automatisch raus — das ist korrekt, kein Datenverlust.

**freipass.ch liefert einen Soft-404.** Erfundene Pfade antworten mit
**HTTP 200**. Der Statuscode beweist also nichts. Der eigentliche Schutz ist
`MIN_EVENTS` in `fetch_events.py`.

**freipass.ch timeoutet gelegentlich.** Bei schneller Abfolge real passiert.
Ohne Retry wäre ein Wochenlauf ausgefallen — daher 3 Versuche mit Pause.

**slowUp-Slugs nicht raten, aus der Seite lesen.** Sie weichen von den Namen
ab: `wfl` (Werdenberg-Liechtenstein), `valleedejoux`, `broye`. Die zwei
ausländischen slowUps liegen auf eigenen Domains ohne Pfad — dort wird der
Slug aus dem Hostnamen abgeleitet.

**slowup.ch liefert keine Koordinaten.** Sie stehen als ungefähre
Streckenmittelpunkte in `REGION_KOORD` (gegen Nominatim gegengeprüft).
Neue Region → Tabelle ergänzen, sonst warnt der Parser und der Termin fehlt
auf beiden Karten.

**Die Quellen überschneiden sich.** „Slowup Mountain Albula" steht in beiden.
freipass verlinkt dort exakt die slowUp-URL — darüber läuft der Dedup. Der
freipass-Eintrag gewinnt (echte Koordinaten), wird aber als slowUp markiert.

---

## Rechen- und Formatfallen

**Mercator: Norden ist der GRÖSSERE Y-Wert.** `spanne_y = y_nord - y_sued`.
Falsch herum wird der Maßstab negativ und die Karte unbrauchbar.

**Mercator: X muss im Bogenmaß gerechnet werden wie Y.** Grad für X und
Mercator-Y mischen zerstört das Seitenverhältnis — die Umrisse werden zu
flachen Strichen.

**GeoJSON ist `[lng, lat]`, Leaflet `[lat, lng]`.** Vertauscht landen alle
Punkte im Indischen Ozean.

**Esri-Kacheln brauchen `{z}/{y}/{x}`**, nicht `{z}/{x}/{y}`. Falsch herum
bleibt die Karte leer. Kein API-Key nötig — bewusst die klassischen
Endpoints, damit kein Schlüssel im öffentlichen Repo liegt.

**ICS: `DTEND` ist EXKLUSIV** — ein Tag nach dem letzten Veranstaltungstag.

**ICS: Zeilen auf 75 OKTETTS falten, nicht Zeichen.** Umlaute und Emoji sind
mehrere Bytes lang.

---

## Fallen beim Prüfen (hier ging am meisten Zeit verloren)

**ICS im Textmodus lesen übersetzt `\r\n` zu `\n`.** Ein
`.replace("\r\n ", "")` zum Entfalten läuft dann ins Leere und meldet
fälschlich fehlende Inhalte. Immer `open(..., newline="")` oder als Bytes
lesen.

**Die Vorschau-Pane meldet beim Laden `innerWidth/innerHeight = 0`.**
Damit wird `height: 70vh` zu 0, und Leaflet fällt auf `maxZoom` zurück —
sieht aus wie ein Kartenfehler, ist aber die Messumgebung.
→ **Fenstergröße VOR dem Navigieren setzen** (`resize_window`, dann
`navigate`) und **~1,5 s warten**, bevor gemessen wird.

**Screenshots zeigen manchmal veralteten Paint.** Eine graue Karte, obwohl
alle 18 Kacheln geladen waren. Kartenzustand per JS prüfen (Zoom, geladene
Kacheln, Marker-Positionen), nicht nur per Screenshot beurteilen.

**Synthetische `.click()` auf Leaflets Zoom-Buttons wirken unter
Touch-Emulation nicht.** Der Zoom ändert sich nicht, die Messung suggeriert
einen Bug. Stattdessen die Karteninstanz direkt ansprechen.

**Skript in ein anderes Verzeichnis kopieren ändert `BASE`.** Es wird aus
`__file__` abgeleitet — eine Kopie im Scratchpad schreibt in ihr eigenes
`data/`. Fehlerpfad-Tests, die so laufen, beweisen nichts. Testkopien im
Projektordner ablegen.

Merksatz: bei einem vermeintlichen Fehler **erst die Messung prüfen**. In
dieser Session waren vier von sieben „Bugs" Messfehler.

---

## Betrieb

**Pages-Deployment mit 503 = GitHub-Ausfall, nicht unser Fehler.** Nichts
reparieren, Lauf neu anstoßen oder nächsten Push abwarten. Details in
`SKILL.md`.

**Das Artifact IMMER mit der URL aus `data/artifact-url.txt` aktualisieren.**
Ohne den `url`-Parameter entsteht jede Woche ein neues Artifact.

**GitHub-Verbindung fehlt noch** für die wöchentliche Cloud-Routine
(`/web-setup`). Ohne sie lehnt die API das Anlegen ab.

---

## Harte Regeln

**Das Repo ist öffentlich.** Keine E-Mail-Adressen, keine Keys, keine Tokens
— auch nicht in Commit-Metadaten. Die Commit-Identität ist **lokal** auf die
GitHub-Noreply-Adresse gesetzt; **niemals `git config --global` ändern**.

**Kein `ORGANIZER`/`ATTENDEE` im ICS** — beide enthalten E-Mail-Adressen.
Der Feed ist ein reines Abo und lädt niemanden ein.

**URLs aus den Quellen vor dem Einsetzen prüfen** (`sichere_url`): nur
`http`/`https`. Ungeprüft landet sonst `javascript:` in einem `href`.

**Bei Parser-Fehlern nichts erfinden.** Lieber Exit 1 und die bestehenden
Dateien unangetastet lassen, als geratene Daten zu schreiben. Ein Umbau der
Quellseite darf den Kalender nicht löschen.
