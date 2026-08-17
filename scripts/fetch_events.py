#!/usr/bin/env python3
"""Parst autofreie Bike-Tage von freipass.ch nach data/events.json.

Siehe SPEC.md "Datenquelle - verifizierte Struktur".
Bei jedem Fehler: Exit 1 und bestehende events.json bleibt unveraendert.
"""

import json
import os
sys_path_hint = None
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(BASE, "data", "events.json")

import fetch_slowup

URL_HTML = "https://www.freipass.ch/index.php"
URL_JS = "https://www.freipass.ch/fpscripts3.js"

USER_AGENT = (
    "Mozilla/5.0 (compatible; autofrei-bot/1.0; "
    "+https://github.com/nikitaberzin/autofrei)"
)
TIMEOUT = 30

LAENDER = {"it", "at", "fr", "ch"}
MIN_EVENTS = 50  # darunter: Strukturaenderung annehmen, nichts schreiben

# Verifiziert 2026-08-09 gegen die echte Seite - nicht "verbessern".
EVENT_RE = re.compile(
    r'<li><span class="date">(?P<date>.*?)</span>'
    r'<a href="(?P<url>.*?)".*?>(?P<name>.*?)</a>'
    r'<div class="flag map (?P<country>\w+)"[^>]*showpop\((?P<marker>\w+)\)',
    re.S,
)

COORD_RE = re.compile(
    r"(?:const|let|var)\s+(?P<marker>\w+)\s*=\s*L\.marker\("
    r"\[(?P<lat>-?[\d.]+),\s*(?P<lng>-?[\d.]+)\]"
)

SEASON_RE = re.compile(r"Saison\s+(\d{4})")
HIGHLIGHT_RE = re.compile(r'<span class="highlight">.*?</span>', re.S)
TAG_RE = re.compile(r"<[^>]+>")

MONATE = {
    "Januar": 1, "Februar": 2, "März": 3, "April": 4, "Mai": 5, "Juni": 6,
    "Juli": 7, "August": 8, "September": 9, "Oktober": 10, "November": 11,
    "Dezember": 12,
}

DASH_RE = re.compile(r"\s*[-–—]\s*")
PART_RE = re.compile(r"(\d{1,2})\.\s*([A-Za-zÄÖÜäöü]+)?")


def warn(msg):
    print("WARN: %s" % msg, file=sys.stderr)


def fail(msg):
    print("FEHLER: %s" % msg, file=sys.stderr)
    print("Bestehende events.json bleibt unveraendert.", file=sys.stderr)
    return 1


def fetch(url, versuche=3, pause=20):
    """Laedt eine URL als Text, mit Retry.

    freipass.ch hat im Test gelegentlich getimeoutet. Ohne Retry waere ein
    einzelner Aussetzer ein kompletter Wochenlauf-Ausfall.

    Achtung: Die Seite liefert einen Soft-404 (HTTP 200 fuer nicht
    existierende Pfade). Der Statuscode allein sagt also nichts ueber die
    Gueltigkeit des Inhalts - dafuer sorgt der MIN_EVENTS-Check in main().
    """
    letzter_fehler = None
    for versuch in range(1, versuche + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                if resp.status != 200:
                    raise urllib.error.HTTPError(
                        url, resp.status, "unerwarteter Status", resp.headers, None
                    )
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            letzter_fehler = exc
            if versuch < versuche:
                warn("Versuch %d/%d fehlgeschlagen (%s) - warte %ds"
                     % (versuch, versuche, exc, pause))
                time.sleep(pause)

    raise letzter_fehler


def parse_season(html):
    """Saison-Jahr aus der Ueberschrift. Niemals raten."""
    m = SEASON_RE.search(html)
    if not m:
        return None
    return int(m.group(1))


def clean_name(raw):
    """Entfernt den 'Neu'-Span samt Inhalt, dann alle restlichen Tags."""
    without_badge = HIGHLIGHT_RE.sub("", raw)
    return TAG_RE.sub("", without_badge).strip()


def _parse_part(part):
    """'30. Mai' -> (30, 5); '1.' -> (1, None). None wenn unparsebar."""
    m = PART_RE.search(part)
    if not m:
        return None
    day = int(m.group(1))
    month_name = m.group(2)
    if month_name is None:
        return (day, None)
    if month_name not in MONATE:
        return None
    return (day, MONATE[month_name])


def parse_german_date(raw, season):
    """'6. Juni' / '1.-5. Juni' / '30. Mai-2. Juni' -> (start_iso, end_iso).

    Gibt (None, None) zurueck wenn nicht parsebar - das Event bleibt trotzdem
    erhalten (siehe SPEC "Edge cases").
    """
    text = raw.replace("&nbsp;", " ").strip()
    parts = DASH_RE.split(text)

    try:
        if len(parts) == 1:
            got = _parse_part(parts[0])
            if not got or got[1] is None:
                return (None, None)
            d = date(season, got[1], got[0])
            iso = d.isoformat()
            return (iso, iso)

        if len(parts) == 2:
            end = _parse_part(parts[1])
            if not end or end[1] is None:
                return (None, None)
            start = _parse_part(parts[0])
            if not start:
                return (None, None)
            # Monat fehlt im ersten Teil ("1.-5. Juni") -> Monat vom Ende
            start_month = start[1] if start[1] is not None else end[1]
            d_start = date(season, start_month, start[0])
            d_end = date(season, end[1], end[0])
            if d_end < d_start:
                return (None, None)
            return (d_start.isoformat(), d_end.isoformat())
    except ValueError:
        # z.B. 31. Juni
        return (None, None)

    return (None, None)


def parse_events(html, season):
    """Alle Events der Zielaender.

    WICHTIG: Die Marker-ID identifiziert den ORT, nicht das Event. Derselbe
    Pass kann mehrere autofreie Termine haben (z.B. Slow Sundays Kloental:
    kloental26 an drei Daten). Der Event-Schluessel ist deshalb
    Marker + Startdatum. Dedup nur ueber Marker wuerde echte Events loeschen.
    """
    events = []
    seen = set()

    for idx, m in enumerate(EVENT_RE.finditer(html)):
        country = m.group("country")
        if country not in LAENDER:
            continue

        marker = m.group("marker")
        name = clean_name(m.group("name"))
        raw_date = m.group("date").strip()
        start, end = parse_german_date(raw_date, season)
        if start is None:
            warn("Datum nicht parsebar: '%s' (%s)" % (raw_date, name))

        url = m.group("url").strip()
        if url in ("", "#"):
            url = None

        # Event-Schluessel: Ort + Datum. Ohne Datum als Fallback der Index,
        # damit die ID trotzdem eindeutig bleibt.
        suffix = start if start is not None else "idx%d" % idx
        event_id = "%s__%s" % (marker, suffix)
        if event_id in seen:
            warn("doppeltes Event '%s' (%s) - erstes gewinnt" % (event_id, name))
            continue
        seen.add(event_id)

        events.append({
            "id": event_id,
            "marker": marker,
            "name": name,
            "country": country,
            "dateRaw": raw_date,
            "dateStart": start,
            "dateEnd": end,
            "url": url,
            "lat": None,
            "lng": None,
            "isNewOnSite": '<span class="highlight">' in m.group("name"),
            "isNew": False,
        })

    return events


def parse_coords(js):
    """Marker-ID -> (lat, lng). Join spaeter ueber die IDs aus dem HTML."""
    coords = {}
    for m in COORD_RE.finditer(js):
        marker = m.group("marker")
        if marker in coords:
            continue
        try:
            coords[marker] = (float(m.group("lat")), float(m.group("lng")))
        except ValueError:
            warn("unlesbare Koordinaten fuer '%s'" % marker)
    return coords


def merge_slowup(freipass_events, slowup_events):
    """Fuehrt beide Quellen zusammen und entfernt Dubletten.

    freipass.ch verlinkt einzelne Eintraege direkt auf slowup.ch (z. B.
    "Slowup Mountain Albula" -> slowup.ch/albula/de.html). Solche Paare sind
    dieselbe Veranstaltung. Der freipass-Eintrag gewinnt, weil er echte
    Koordinaten mitbringt statt unserer geschaetzten - er wird aber als
    slowUp markiert, damit die Kennzeichnung stimmt.
    """
    # (slug, datum) -> freipass-Event, sofern dieses auf slowup.ch zeigt
    nach_slug = {}
    for e in freipass_events:
        e.setdefault("source", "freipass")
        e.setdefault("isSlowup", False)
        if e.get("url") and "slowup" in e["url"].lower():
            slug = fetch_slowup.slug_aus_url(e["url"])
            if slug:
                nach_slug[(slug, e["dateStart"])] = e

    zusammen = list(freipass_events)
    dubletten = 0
    for e in slowup_events:
        treffer = nach_slug.get((e.get("slug"), e["dateStart"]))
        if treffer is not None:
            treffer["isSlowup"] = True
            dubletten += 1
            continue
        e["isSlowup"] = True
        e.pop("slug", None)
        zusammen.append(e)

    if dubletten:
        print("  %d Dublette(n) zwischen den Quellen zusammengefuehrt" % dubletten)
    return zusammen


def diff_new(events, previous_path):
    """Markiert Events, die im letzten Snapshot fehlten.

    Erstlauf (keine alte Datei) -> alles False, nicht alles als neu melden.
    """
    if not os.path.exists(previous_path):
        print("Erstlauf - kein Vergleich moeglich, isNew bleibt ueberall False.")
        return events

    try:
        with open(previous_path, encoding="utf-8") as fh:
            old = json.load(fh)
        old_ids = {e["id"] for e in old.get("events", [])}
    except (ValueError, KeyError, OSError) as exc:
        warn("alter Snapshot unlesbar (%s) - isNew bleibt ueberall False." % exc)
        return events

    for ev in events:
        ev["isNew"] = ev["id"] not in old_ids
    return events


def main():
    try:
        html = fetch(URL_HTML)
        js = fetch(URL_JS)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        return fail("freipass.ch nicht erreichbar: %s" % exc)

    season = parse_season(html)
    if season is None:
        return fail(
            "'Saison JJJJ' nicht gefunden - Jahr wird nicht geraten, "
            "sonst entstehen falsche Kalendereintraege."
        )

    events = parse_events(html, season)

    # Plausibilitaet: deutlich weniger Treffer als <span class="date"> deutet
    # auf eine Strukturaenderung hin.
    date_spans = html.count('<span class="date">')
    if len(events) < MIN_EVENTS:
        return fail(
            "Parser lieferte nur %d Events - HTML-Struktur von freipass.ch "
            "vermutlich geaendert, Regex pruefen. (%d date-Spans auf der Seite)"
            % (len(events), date_spans)
        )

    coords = parse_coords(js)
    for ev in events:
        if ev["marker"] in coords:
            ev["lat"], ev["lng"] = coords[ev["marker"]]

    # Zweitquelle slowup.ch. Faellt sie aus, laeuft der Rest trotzdem durch -
    # ein Ausfall dort darf den freipass-Kalender nicht mitreissen.
    try:
        slowup_html = fetch(fetch_slowup.URL)
        slowup_events = fetch_slowup.parse_slowup(slowup_html)
        if len(slowup_events) < fetch_slowup.MIN_EVENTS:
            warn("slowup.ch lieferte nur %d Termine - Struktur geaendert? "
                 "Zweitquelle wird uebersprungen." % len(slowup_events))
            slowup_events = []
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        warn("slowup.ch nicht erreichbar (%s) - nur freipass-Daten." % exc)
        slowup_events = []

    print("  freipass: %d | slowUp: %d" % (len(events), len(slowup_events)))
    events = merge_slowup(events, slowup_events)

    events = diff_new(events, OUT_PATH)

    # Chronologisch; Events ohne Datum ans Ende.
    events.sort(key=lambda e: (e["dateStart"] is None, e["dateStart"] or ""))

    data = {
        "source": "https://freipass.ch/",
        "sources": ["https://freipass.ch/", "https://www.slowup.ch/"],
        "season": season,
        "fetchedAt": date.today().isoformat(),
        "eventCount": len(events),
        "events": events,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    ohne_koord = sum(1 for e in events if e["lat"] is None)
    ohne_datum = sum(1 for e in events if e["dateStart"] is None)
    neu = sum(1 for e in events if e["isNew"])

    print("Saison %d - %d Events (von %d date-Spans auf der Seite)"
          % (season, len(events), date_spans))
    print("  ohne Koordinaten: %d" % ohne_koord)
    print("  ohne Datum:       %d" % ohne_datum)
    print("  neu seit letztem Lauf: %d" % neu)
    from collections import Counter
    print("  Quellen:", dict(Counter(e.get("source", "freipass") for e in events)))
    print("  davon slowUp markiert:", sum(1 for e in events if e.get("isSlowup")))
    print("geschrieben: %s" % OUT_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
