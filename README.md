# Autofreie Bike-Tage

Wöchentlich aktualisierte Übersicht autofreier Pass- und Straßentage in
**Italien, Österreich, Frankreich und der Schweiz**.

Datenquellen: [freipass.ch](https://freipass.ch/) und
[slowup.ch](https://www.slowup.ch/)

## Was hier liegt

| Datei | Zweck |
|---|---|
| [`docs/autofrei.ics`](docs/autofrei.ics) | Kalender-Feed zum Abonnieren |
| [`docs/karte.html`](docs/karte.html) | Karte mit allen Terminen |
| [`docs/autofrei.geojson`](docs/autofrei.geojson) | Layer-Import für ArcGIS Online |
| `data/events.json` | Snapshot der geparsten Termine |

## Kalender abonnieren

```
https://nikitaberzin.github.io/autofrei/autofrei.ics
```

**Adresse abonnieren, Datei nicht herunterladen.** Wer die `.ics` herunterlädt
und anklickt, importiert sie einmalig: der Kalender heißt dann „Untitled" und
bekommt nie wieder Updates. Beim Abonnieren übernimmt der Client den Namen und
aktualisiert wöchentlich von selbst.

- **Google Kalender** — Weitere Kalender `+` → Per URL → Adresse einfügen
- **Outlook im Web** — Kalender hinzufügen → Aus dem Internet abonnieren
- **Outlook am Handy** — die App kann keine Adresse abonnieren; einmal im
  Web abonnieren, dann erscheint der Kalender in der App unter demselben Konto
- **Apple Kalender** — Ablage → *Neues Kalenderabo…* (nicht „Importieren")

Ein Abo ist eine reine Ansicht: es verschickt keine Einladungen. Wer die
Termine ebenfalls sehen soll, abonniert dieselbe Adresse.

## Selbst ausführen

Python 3.9+, keine Abhängigkeiten.

```bash
python3 scripts/fetch_events.py   # freipass.ch parsen -> data/events.json
python3 scripts/build_ics.py      # -> docs/autofrei.ics
python3 scripts/build_map.py      # -> docs/karte.html, docs/autofrei.geojson
python3 scripts/build_html.py     # -> data/artifact.html, docs/index.html
```

`fetch_events.py` bricht bei Netzwerkfehlern oder unplausibel wenigen Treffern
ab, ohne `events.json` zu überschreiben — ein Umbau der Quellseite löscht also
nicht den Kalender.

## Dokumentation

- [`CLAUDE.md`](CLAUDE.md) — Fallstricke beim Weiterentwickeln
- [`SPEC.md`](SPEC.md) — Entscheidungen, Datenmodell, Edge Cases
- [`PLAN.md`](PLAN.md) — Umsetzungsschritte
