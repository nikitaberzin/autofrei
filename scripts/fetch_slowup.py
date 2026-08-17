#!/usr/bin/env python3
"""Parst die slowUp-Termine von slowup.ch.

Zweitquelle neben freipass.ch. Wird von fetch_events.py eingebunden, nicht
allein ausgefuehrt (kann es aber zum Pruefen: `python3 scripts/fetch_slowup.py`).

Zwei Eigenheiten der Quelle:
  1. slowup.ch liefert KEINE Koordinaten. Sie stammen aus REGION_KOORD unten -
     ungefaehre Streckenmittelpunkte, gegen Nominatim gegengeprueft
     (2026-08-10, groesste Abweichung ~20 km bei Sundgau).
  2. Die Seite plant mehrere Jahre voraus (2026-2028).
"""

import re
import sys

URL = "https://www.slowup.ch/national/de.html"
QUELLE_URL = "https://www.slowup.ch/"
QUELLE_NAME = "slowup.ch"
BASIS = "https://www.slowup.ch"

# Verifiziert 2026-08-10 gegen die echte Seite.
CARD_RE = re.compile(
    r'<a href="(?P<url>[^"]+)" class="card (?P<kind>[^"]*?)'
    r'(?: card--image[^"]*)?">.*?<h2 class="card__title">\s*'
    r'<span class="block">(?P<name>.*?)</span>\s*'
    r'<span class="block">(?P<date>\d{2}\.\d{2}\.\d{4})</span>',
    re.S,
)

MIN_EVENTS = 10  # darunter: Strukturaenderung annehmen

# Ungefaehre Streckenmittelpunkte. slowup.ch nennt keine Koordinaten; ohne
# diese Tabelle taeten die Termine auf keiner Karte auf.
# Werte gegen Nominatim gegengeprueft - bewusst grob, es sind Regionen,
# keine Punkte.
REGION_KOORD = {
    "bodensee":                 (47.565, 9.378),
    "albula":                   (46.582, 9.838),
    "emmental-oberaargau":      (47.120, 7.831),
    "basel-dreiland":           (47.558, 7.588),
    "zuerichsee":               (47.255, 8.742),
    "ticino":                   (46.192, 9.021),
    "murtensee":                (46.929, 7.116),
    "wfl":                      (47.163, 9.476),  # Werdenberg-Liechtenstein
    "schaffhausen-hegau":       (47.696, 8.635),
    "solothurn-buechibaerg":    (47.319, 7.670),
    "slowup-alsace":            (48.009, 7.551),  # externe Domain
    "slowup-sundgau":           (47.480, 7.401),  # externe Domain
    "valais":                   (46.292, 7.532),
    "hochrhein":                (47.550, 7.783),
    "jura":                     (47.362, 7.355),
    "valleedejoux":             (46.606, 6.231),
    "broye":                    (46.821, 6.939),
    "brugg-regio":              (47.481, 8.209),
    "sempachersee":             (47.135, 8.192),
    "schwyz":                   (47.057, 8.722),
    "seetal":                   (47.282, 8.216),
}

MONAT_DE = ["", "Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
            "August", "September", "Oktober", "November", "Dezember"]


def warn(msg):
    print("WARN [slowup]: %s" % msg, file=sys.stderr)


def slug_aus_url(url):
    """'/albula/de.html' und 'https://www.slowup.ch/albula/de.html' -> 'albula'.

    Der Slug ist zugleich der Dedup-Schluessel gegen freipass.ch: die dortigen
    Eintraege verlinken teils direkt auf slowup.ch.
    """
    if not url:
        return None
    roh = url.strip()
    pfad = re.sub(r"^https?://[^/]+", "", roh)
    teile = [t for t in pfad.split("/") if t and not t.endswith(".html")]
    if teile:
        return teile[0].lower()
    # Kein Pfad -> auslaendische slowUps auf eigener Domain
    # ("https://www.slowup-alsace.fr/" -> "slowup-alsace").
    host = re.match(r"^https?://(?:www\.)?([^/]+)", roh)
    return host.group(1).rsplit(".", 1)[0].lower() if host else None


def iso_datum(ddmmyyyy):
    """'30.08.2026' -> '2026-08-30'"""
    t, m, j = ddmmyyyy.split(".")
    return "%s-%s-%s" % (j, m, t)


def datum_roh(iso):
    """'2026-08-30' -> '30. August' (Format wie bei freipass.ch)."""
    j, m, t = iso.split("-")
    return "%d. %s" % (int(t), MONAT_DE[int(m)])


def parse_slowup(html, jahr_bis=None):
    """HTML -> Event-Liste im selben Schema wie fetch_events.py.

    jahr_bis: optionale Obergrenze (z. B. 2027). None = alle Jahre.
    """
    events = []
    gesehen = set()

    for m in CARD_RE.finditer(html):
        name = re.sub(r"\s+", " ", m.group("name")).strip()
        iso = iso_datum(m.group("date"))
        if jahr_bis and int(iso[:4]) > jahr_bis:
            continue

        url = m.group("url").strip()
        if url.startswith("/"):
            url = BASIS + url
        slug = slug_aus_url(url)

        # "card--foreign" sind die auslaendischen slowUps (Elsass, Sundgau).
        auslaendisch = "foreign" in m.group("kind")
        land = "fr" if auslaendisch else "ch"

        koord = REGION_KOORD.get(slug)
        if koord is None:
            warn("keine Koordinaten fuer '%s' (%s) - Tabelle ergaenzen" % (slug, name))

        eid = "slowup-%s__%s" % (slug or "unbekannt", iso)
        if eid in gesehen:
            warn("doppelter Eintrag '%s' - erster gewinnt" % eid)
            continue
        gesehen.add(eid)

        events.append({
            "id": eid,
            "marker": "slowup-%s" % (slug or "unbekannt"),
            "name": "slowUp %s" % name,
            "country": land,
            "dateRaw": datum_roh(iso),
            "dateStart": iso,
            "dateEnd": iso,
            "url": url,
            "lat": koord[0] if koord else None,
            "lng": koord[1] if koord else None,
            "isNewOnSite": False,
            "isNew": False,
            "source": "slowup",
            "slug": slug,
        })

    return events


def main():
    import urllib.request
    req = urllib.request.Request(URL, headers={
        "User-Agent": "Mozilla/5.0 (compatible; autofrei-bot/1.0; "
                      "+https://github.com/nikitaberzin/autofrei)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8", errors="replace")

    ev = parse_slowup(html)
    print("slowUp: %d Termine" % len(ev))
    ohne = [e["name"] for e in ev if e["lat"] is None]
    print("  ohne Koordinaten: %d %s" % (len(ohne), ohne or ""))
    from collections import Counter
    print("  Jahre:", dict(Counter(e["dateStart"][:4] for e in ev)))
    print("  Laender:", dict(Counter(e["country"] for e in ev)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
