#!/usr/bin/env python3
"""Erzeugt docs/autofrei.ics aus data/events.json.

Siehe SPEC.md "ICS-Format". Bewusst OHNE ORGANIZER/ATTENDEE - beide wuerden
E-Mail-Adressen enthalten (SPEC "Datenschutz"). Der Feed ist ein reiner
Abo-Kalender und laedt niemanden ein.
"""

import json
import os
import sys
from datetime import date, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN_PATH = os.path.join(BASE, "data", "events.json")
OUT_PATH = os.path.join(BASE, "docs", "autofrei.ics")

CRLF = "\r\n"
PRODID = "-//autofrei//freipass.ch scraper//DE"
CALNAME = "Autofreie Bike-Tage"
QUELLE_URL = "https://freipass.ch/"
QUELLE_NAME = "freipass.ch"


LAND_LABEL = {"it": "IT", "at": "AT", "fr": "FR", "ch": "CH"}


def escape_text(value):
    """RFC 5545 TEXT-Escaping. Reihenfolge zaehlt: Backslash zuerst."""
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def fold(line):
    """Faltet auf max. 75 OKTETTS pro Zeile (nicht Zeichen!).

    Umlaute und Emoji sind mehrere Bytes lang - naiv nach Zeichen zu falten
    erzeugt zu lange Zeilen. Es wird nie mitten in ein Zeichen gefaltet.
    """
    out = []
    current = ""
    current_bytes = 0
    limit = 75  # erste Zeile

    for ch in line:
        size = len(ch.encode("utf-8"))
        if current_bytes + size > limit:
            out.append(current)
            current = ch
            current_bytes = size
            limit = 74  # Folgezeilen: fuehrendes Leerzeichen zaehlt mit
        else:
            current += ch
            current_bytes += size

    out.append(current)
    return CRLF.join([out[0]] + [" " + part for part in out[1:]])


def ics_date(iso):
    """'2026-06-06' -> '20260606'"""
    return iso.replace("-", "")


def build_ics(events, stamp_iso):
    """Baut den kompletten ICS-Text. Events ohne Datum werden uebersprungen."""
    dtstamp = ics_date(stamp_iso) + "T000000Z"

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:" + PRODID,
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:" + escape_text(CALNAME),
        # Bewusst nicht "Alpen": der Datensatz enthaelt auch Vogesen,
        # Ardeche, Ventoux und einen Pyrenaeen-Pass (Tourmalet).
        "X-WR-CALDESC:" + escape_text(
            "Autofreie Passtage in Italien, Österreich, Frankreich und der "
            "Schweiz. Quellen: " + QUELLE_URL + " und https://www.slowup.ch/"
        ),
        "SOURCE;VALUE=URI:" + QUELLE_URL,
        "REFRESH-INTERVAL;VALUE=DURATION:P1W",
        "X-PUBLISHED-TTL:P1W",
    ]

    uebersprungen = 0
    for ev in events:
        if not ev.get("dateStart"):
            uebersprungen += 1
            continue

        start = date.fromisoformat(ev["dateStart"])
        end = date.fromisoformat(ev["dateEnd"] or ev["dateStart"])
        # DTEND ist im ICS-Standard EXKLUSIV -> ein Tag nach dem letzten Tag.
        dtend = end + timedelta(days=1)

        land = LAND_LABEL.get(ev["country"], ev["country"].upper())
        summary = "\U0001f6b2 %s (%s)" % (ev["name"], land)

        beschreibung = "Autofreier Tag"
        merkmale = []
        if ev.get("flach"):
            merkmale.append("flach, kindergerecht")
        if ev.get("isSlowup"):
            merkmale.append("slowUp")
        if merkmale:
            beschreibung += " (" + ", ".join(merkmale) + ")"
        beschreibung += "\nQuelle: " + (
            "https://www.slowup.ch/" if ev.get("source") == "slowup" else QUELLE_URL)
        if ev.get("url"):
            beschreibung += "\n" + ev["url"]

        lines.append("BEGIN:VEVENT")
        lines.append("UID:%s@autofrei.freipass" % ev["id"])
        lines.append("DTSTAMP:" + dtstamp)
        lines.append("DTSTART;VALUE=DATE:" + ics_date(start.isoformat()))
        lines.append("DTEND;VALUE=DATE:" + ics_date(dtend.isoformat()))
        lines.append("SUMMARY:" + escape_text(summary))
        lines.append("DESCRIPTION:" + escape_text(beschreibung))
        if ev.get("url"):
            # URL ist ein URI-Typ, kein TEXT -> nicht escapen.
            lines.append("URL:" + ev["url"])
        if ev.get("lat") is not None and ev.get("lng") is not None:
            lines.append("GEO:%.6f;%.6f" % (ev["lat"], ev["lng"]))
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")

    if uebersprungen:
        print("Hinweis: %d Event(s) ohne Datum uebersprungen." % uebersprungen,
              file=sys.stderr)

    return CRLF.join(fold(line) for line in lines) + CRLF


def main():
    if not os.path.exists(IN_PATH):
        print("FEHLER: %s fehlt - erst fetch_events.py laufen lassen." % IN_PATH,
              file=sys.stderr)
        return 1

    with open(IN_PATH, encoding="utf-8") as fh:
        data = json.load(fh)

    text = build_ics(data["events"], data["fetchedAt"])

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    # newline="" verhindert, dass Python die CRLF nochmal umschreibt.
    # encoding utf-8 ohne BOM.
    with open(OUT_PATH, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)

    mit_datum = sum(1 for e in data["events"] if e.get("dateStart"))
    print("geschrieben: %s" % OUT_PATH)
    print("  VEVENTs: %d (von %d Events)" % (mit_datum, len(data["events"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
