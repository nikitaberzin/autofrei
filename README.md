# Autofreie Bike-Tage

Wöchentlich aktualisierte Übersicht autofreier Pass- und Straßentage in
**Italien, Österreich, Frankreich und der Schweiz**.

Datenquelle: [freipass.ch](https://freipass.ch/)

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

Einmal abonnieren, danach aktualisiert sich der Kalender selbst — neue Termine
erscheinen automatisch.

- **Google Kalender** — Weitere Kalender `+` → Per URL → Adresse einfügen
- **Outlook** — Kalender hinzufügen → Aus dem Internet abonnieren
- **Apple Kalender** — Ablage → Neues Kalenderabo

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

- [`SPEC.md`](SPEC.md) — Entscheidungen, Datenmodell, Edge Cases
- [`PLAN.md`](PLAN.md) — Umsetzungsschritte
