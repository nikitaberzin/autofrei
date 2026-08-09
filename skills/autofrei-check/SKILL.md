---
name: autofrei-check
description: Aktualisiert die autofreien Bike-Tage von freipass.ch — parst die Termine für Italien, Österreich, Frankreich und die Schweiz, erzeugt Kalender-Feed, Karte und GeoJSON, pusht nach GitHub und aktualisiert das Übersichts-Artifact. Verwenden, wenn der User nach autofreien Tagen, Passtagen oder Bike Days fragt, oder wenn die wöchentliche Routine läuft.
---

# Autofreie Bike-Tage aktualisieren

Vollständige Entscheidungen, Datenmodell und Edge Cases stehen in `SPEC.md`
im Projektordner. Diese Datei ist die Ablaufanleitung.

## Projektordner finden

Primär: `~/claude/01 Projects/autofrei/`

Existiert der Ordner nicht (z. B. frische Cloud-Umgebung), das Repo klonen:

```bash
gh repo clone nikitaberzin/autofrei
```

Alle folgenden Befehle laufen im Projektordner.

## Ablauf

### 1. Daten holen

```bash
python3 scripts/fetch_events.py
```

**Bricht das Skript mit Exit 1 ab, hier stoppen.** Es hat dann bewusst nichts
geschrieben — `events.json` und der Kalender bleiben unangetastet. Mögliche
Gründe stehen in der Fehlermeldung:

- freipass.ch nicht erreichbar (3 Versuche sind schon erfolgt)
- weniger als 50 Events geparst → die Seitenstruktur hat sich geändert,
  die Regexe in `SPEC.md` müssen angepasst werden
- „Saison JJJJ" nicht gefunden → Jahr wird **nicht** geraten

In diesen Fällen dem User berichten, was passiert ist, und **nichts pushen**.

### 2. Ausgaben erzeugen

```bash
python3 scripts/build_ics.py
python3 scripts/build_map.py
python3 scripts/build_html.py
```

### 3. Nach GitHub pushen — nur bei echten Änderungen

```bash
git status --porcelain
```

Ist die Ausgabe leer, gibt es nichts zu committen. Dann Schritt 3
überspringen und mit Schritt 4 weitermachen.

Sonst committen und pushen:

```bash
git add -A
git commit -m "Termine aktualisiert (Stand JJJJ-MM-TT)"
git push origin main
```

**Datenschutz:** Die Commit-Identität dieses Repos ist lokal auf die
GitHub-Noreply-Adresse gesetzt. Nach einem frischen Klon erneut setzen:

```bash
git config user.email "$(gh api user --jq .id)+nikitaberzin@users.noreply.github.com"
git config user.name "nikitaberzin"
```

Niemals `--global` verwenden. Keine E-Mail-Adressen ins Repo — es ist
öffentlich.

### 4. Artifact aktualisieren

Die URL steht in `data/artifact-url.txt`. Sie **muss** als `url`-Parameter an
das Artifact-Tool übergeben werden, sonst entsteht jede Woche ein neues
Artifact statt eines aktualisierten.

- `file_path`: `data/artifact.html`
- `url`: Inhalt von `data/artifact-url.txt`
- `favicon`: 🚲 (unverändert lassen)

### 5. Berichten

Kurz und konkret:

- Gesamtzahl der Termine und wie viele noch anstehen
- **Neue Termine seit dem letzten Lauf** (`isNew: true` in `events.json`) —
  das ist der eigentliche Mehrwert des Laufs, namentlich nennen
- das nächste anstehende Event mit Datum
- ob gepusht wurde oder nichts zu tun war

Gab es keine neuen Termine, das in einem Satz sagen — keine langen Berichte
über Unverändertes.

## Karte auf Anfrage

`docs/karte.html` und `docs/autofrei.geojson` entstehen bei jedem Lauf mit.
Fragt der User nach der Karte, einfach verlinken:

- Karte: https://nikitaberzin.github.io/autofrei/karte.html
- GeoJSON für ArcGIS Online: https://nikitaberzin.github.io/autofrei/autofrei.geojson

## Nicht tun

- Keine weiteren Datenquellen anzapfen — freipass.ch ist die einzige Quelle
- Keine Kalender-Einladungen verschicken, kein Kalenderkonto verbinden
  (der ICS-Feed ist ein reines Abo)
- Bei Parser-Fehlern nichts „reparieren", indem Daten geraten oder alte
  Stände überschrieben werden
