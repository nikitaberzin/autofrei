#!/usr/bin/env python3
"""Erzeugt data/artifact.html aus data/events.json.

Siehe SPEC.md "HTML-Artifact - Darstellung".

Wichtig: Das Artifact-Tool wrappt die Datei in <!doctype>/<head>/<body>.
Hier also KEINE dieser Tags - nur Seiteninhalt. Und nichts Externes laden,
die Artifact-CSP blockiert jeden fremden Host (Fonts, Skripte, Bilder).
"""

import json
import math
import os
import sys
from datetime import date
from string import Template

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN_PATH = os.path.join(BASE, "data", "events.json")
OUT_PATH = os.path.join(BASE, "data", "artifact.html")

PAGES_BASE = "https://nikitaberzin.github.io/autofrei"
QUELLE_URL = "https://freipass.ch/"
QUELLE_NAME = "freipass.ch"
QUELLE2_URL = "https://www.slowup.ch/"
QUELLE2_NAME = "slowup.ch"


LAND_NAME = {"it": "Italien", "at": "Österreich", "fr": "Frankreich", "ch": "Schweiz"}
MONAT = ["", "Januar", "Februar", "März", "April", "Mai", "Juni",
         "Juli", "August", "September", "Oktober", "November", "Dezember"]
WOCHENTAG = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def esc(value):
    """HTML-Escaping fuer Text und Attributwerte."""
    return (
        str(value)
        .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;").replace("'", "&#39;")
    )


def sichere_url(url):
    """Nur http/https durchlassen.

    Die URLs stammen aus fremdem HTML. Ohne diese Pruefung landet z. B.
    "javascript:..." unveraendert in einem href und wird beim Klick
    ausgefuehrt. Alles andere wird verworfen - das Event bleibt bestehen,
    nur ohne Link.
    """
    if not url:
        return None
    u = url.strip()
    return u if u[:7].lower() == "http://" or u[:8].lower() == "https://" else None


def datum_kurz(ev):
    """'6. Juni' bzw. '1.-5. Juni' - Originaltext, nur Bindestrich als Halbgeviert."""
    return ev["dateRaw"].replace("-", "–")


def datum_in_gruppe(ev, gruppen_monat):
    """Datum ohne Monatsnamen, solange der Monat schon in der Ueberschrift steht.

    '9. August' -> '9.'   |   '20.-22. August' -> '20.–22.'
    Monatsuebergreifende Bereiche ('30. Mai-2. Juni') behalten den Volltext,
    sonst waere unklar, welcher Monat gemeint ist.
    """
    if gruppen_monat is None or not ev["dateStart"]:
        return datum_kurz(ev)

    start = date.fromisoformat(ev["dateStart"])
    end = date.fromisoformat(ev["dateEnd"] or ev["dateStart"])
    if start.month != gruppen_monat or end.month != gruppen_monat:
        return datum_kurz(ev)

    if start.day == end.day:
        return "%d." % start.day
    return "%d.–%d." % (start.day, end.day)


def wochentag(iso):
    return WOCHENTAG[date.fromisoformat(iso).weekday()]


def render_event(ev, gruppen_monat=None):
    land = ev["country"]
    name = esc(ev["name"])
    wd = wochentag(ev["dateStart"]) if ev["dateStart"] else "&mdash;"

    url = sichere_url(ev.get("url"))
    if url:
        titel = ('<a class="n" href="%s" target="_blank" rel="noopener noreferrer">'
                 "%s</a>" % (esc(url), name))
    else:
        titel = '<span class="n">%s</span>' % name

    neu = '<span class="neu">neu</span>' if ev.get("isNew") else ""
    slow = '<span class="su">slowUp</span>' if ev.get("isSlowup") else ""

    return (
        '<li class="ev" data-id="%s" data-c="%s" data-f="%s" data-y="%s">'
        '<button type="button" class="mk" data-mk="%s" aria-pressed="false" '
        'title="Für mich vormerken">'
        '<span class="mk-i" aria-hidden="true"></span>'
        '<span class="vh">Für mich vormerken</span></button>'
        '<div class="d"><span class="wd">%s</span>'
        '<span class="dm">%s</span></div>'
        '<div class="b">%s<div class="m">'
        '<span class="c c-%s">%s</span>%s%s</div></div>'
        "</li>"
    ) % (esc(ev["id"]), land, "1" if ev.get("flach") else "0",
         (ev["dateStart"] or "")[:4], esc(ev["id"]), wd,
         esc(datum_in_gruppe(ev, gruppen_monat)), titel, land,
         esc(LAND_NAME.get(land, land)), slow, neu)


OUTLINE_PATH = os.path.join(BASE, "data", "outline.json")


def _mercator_y(lat):
    """Web-Mercator-Y, damit die Mini-Karte zur Leaflet-Karte passt."""
    rad = math.radians(max(-85.0, min(85.0, lat)))
    return math.log(math.tan(math.pi / 4 + rad / 2))


def build_minimap(events, breite=760, hoehe=380, rand=8):
    """Inline-SVG-Karte fuer das Artifact.

    Kartenkacheln sind unter der Artifact-CSP nicht ladbar (jeder externe Host
    ist blockiert). Selbst gezeichnete Vektoren dagegen schon - deshalb hier
    grobe Laenderumrisse (Natural Earth 110m) plus ein Punkt je Termin.
    """
    punkte = [e for e in events if e.get("lat") is not None]
    if not punkte:
        return ""

    try:
        with open(OUTLINE_PATH, encoding="utf-8") as fh:
            umrisse = json.load(fh)
    except OSError:
        umrisse = []

    lngs = [e["lng"] for e in punkte]
    lats = [e["lat"] for e in punkte]
    lng0, lng1 = min(lngs) - 0.9, max(lngs) + 0.9
    lat0, lat1 = min(lats) - 0.7, max(lats) + 0.7

    # X muss wie Y im Bogenmass gerechnet werden - sonst stimmt das
    # Seitenverhaeltnis nicht (Grad und Mercator-Y sind nicht vergleichbar).
    x0, x1 = math.radians(lng0), math.radians(lng1)
    # In Mercator ist Norden der GROESSERE Y-Wert, auf dem Bildschirm aber oben.
    y_nord, y_sued = _mercator_y(lat1), _mercator_y(lat0)

    spanne_x = x1 - x0
    spanne_y = y_nord - y_sued  # positiv

    skala = min((breite - 2 * rand) / spanne_x, (hoehe - 2 * rand) / spanne_y)
    off_x = (breite - spanne_x * skala) / 2
    off_y = (hoehe - spanne_y * skala) / 2

    def px(lng, lat):
        return (off_x + (math.radians(lng) - x0) * skala,
                off_y + (y_nord - _mercator_y(lat)) * skala)

    pfade = []
    for ring in umrisse:
        d = []
        for i, (lng, lat) in enumerate(ring["ring"]):
            x, y = px(lng, lat)
            d.append("%s%.1f %.1f" % ("M" if i == 0 else "L", x, y))
        iso = (ring.get("iso") or "").lower()
        # Nur die vier Zielländer werden eingefaerbt; alles andere bleibt
        # neutraler Kontext.
        klasse = ' class="l-%s"' % iso if iso in LAND_NAME else ""
        pfade.append('<path%s d="%sZ"/>' % (klasse, "".join(d)))

    # Beschriftung der Zielländer. Ankerpunkte bewusst von Hand gesetzt -
    # ein Polygon-Schwerpunkt landet bei Italien im Meer.
    ANKER = {
        "ch": (8.15, 46.85), "it": (11.4, 44.4),
        "fr": (2.6, 46.6), "at": (13.4, 48.15),
    }
    labels = []
    for iso, (lng, lat) in ANKER.items():
        x, y = px(lng, lat)
        if not (0 <= x <= breite and 0 <= y <= hoehe):
            continue
        labels.append('<text class="lb lb-%s" x="%.1f" y="%.1f">%s</text>'
                      % (iso, x, y, esc(LAND_NAME[iso])))

    heute = date.today().isoformat()
    kreise = []
    for e in punkte:
        x, y = px(e["lng"], e["lat"])
        kommend = bool(e["dateStart"] and e["dateStart"] >= heute)
        kreise.append(
            '<circle class="pt %s%s" data-id="%s" data-c="%s" data-f="%s" '
            'data-y="%s" cx="%.1f" cy="%.1f" r="%s">'
            "<title>%s</title></circle>"
            % ("kommend" if kommend else "vorbei",
               " su" if e.get("flach") else "",
               esc(e["id"]), e["country"], "1" if e.get("flach") else "0",
               (e["dateStart"] or "")[:4], x, y, "4.2" if kommend else "3",
               esc("%s — %s" % (e["name"], datum_kurz(e))))
        )

    return (
        '<a class="mini" href="%s/karte.html" target="_blank" rel="noopener noreferrer">'
        '<svg viewBox="0 0 %d %d" role="img" '
        'aria-label="Übersichtskarte aller Termine">'
        '<g class="land">%s</g><g class="pts">%s</g>'
        '<g class="lbs">%s</g></svg>'
        '<span class="mini-h">Interaktive Karte öffnen &rarr;</span></a>'
        % (PAGES_BASE, breite, hoehe, "".join(pfade), "".join(kreise),
           "".join(labels))
    )


def events_json(events):
    """Kompakte Termindaten fuer die Kalenderansicht im Browser.

    Kurze Schluessel, weil die Nutzlast im Artifact mitgeliefert wird.
    Landet in <script type="application/json">: dort beendet erst
    "</script>" den Block, deshalb wird "<" maskiert. Die URLs sind schon
    durch sichere_url gegangen, hier steht also nichts Ausfuehrbares.
    """
    schlank = []
    for e in events:
        if not e["dateStart"]:
            continue
        schlank.append({
            "id": e["id"],
            "n": e["name"],
            "c": e["country"],
            "s": e["dateStart"],
            "e": e["dateEnd"] or e["dateStart"],
            "y": e["dateStart"][:4],
            "r": datum_kurz(e),
            "u": sichere_url(e.get("url")) or "",
            "fl": bool(e.get("flach")),
            "su": bool(e.get("isSlowup")),
        })
    roh = json.dumps(schlank, ensure_ascii=False, separators=(",", ":"))
    return roh.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def gruppiere_nach_monat(events):
    """[(label, monatsnummer, [event, ...]), ...] - chronologische Reihenfolge."""
    gruppen = []
    for ev in events:
        if not ev["dateStart"]:
            label, monat = "Termin unklar", None
        else:
            d = date.fromisoformat(ev["dateStart"])
            label, monat = "%s %d" % (MONAT[d.month], d.year), d.month
        if not gruppen or gruppen[-1][0] != label:
            gruppen.append((label, monat, []))
        gruppen[-1][2].append(ev)
    return gruppen


def render_gruppen(gruppen):
    teile = []
    for label, monat, evs in gruppen:
        teile.append(
            '<section class="mo">'
            '<h3 class="mo-h">%s<span class="mo-n">%d</span></h3>'
            '<ul class="lst">%s</ul>'
            "</section>" % (esc(label), len(evs),
                            "".join(render_event(e, monat) for e in evs))
        )
    return "".join(teile)


PAGE = Template("""<title>Autofreie Bike-Tage $spanne</title>
<style>
:root {
  color-scheme: light dark;
  --bg:#f2f5f4; --surface:#ffffff; --ink:#16211f; --ink2:#5d6f6c;
  --line:#dde4e3; --accent:#0e6e6b; --accent-soft:#e0efee; --accent-ink:#0a5350;
  --it:#00803f; --at:#c96a00; --fr:#0055a4; --ch:#c8241a;
  --wkend:#e8edec;
  --r:10px;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg:#0f1514; --surface:#18211f; --ink:#e7edec; --ink2:#8fa39f;
    --line:#26322f; --accent:#4fd1c7; --accent-soft:#123230; --accent-ink:#7fe3db;
    --it:#2bb673; --at:#f0a03c; --fr:#5f9de8; --ch:#f2594c;
    --wkend:#141c1b;
  }
}
:root[data-theme="light"] {
  --bg:#f2f5f4; --surface:#ffffff; --ink:#16211f; --ink2:#5d6f6c;
  --line:#dde4e3; --accent:#0e6e6b; --accent-soft:#e0efee; --accent-ink:#0a5350;
  --it:#00803f; --at:#c96a00; --fr:#0055a4; --ch:#c8241a;
  --wkend:#e8edec;
}
:root[data-theme="dark"] {
  --bg:#0f1514; --surface:#18211f; --ink:#e7edec; --ink2:#8fa39f;
  --line:#26322f; --accent:#4fd1c7; --accent-soft:#123230; --accent-ink:#7fe3db;
  --it:#2bb673; --at:#f0a03c; --fr:#5f9de8; --ch:#f2594c;
  --wkend:#141c1b;
}

* { box-sizing:border-box; }
body {
  margin:0; background:var(--bg); color:var(--ink);
  font:16px/1.55 var(--sans);
  -webkit-text-size-adjust:100%;
}
.wrap { max-width:47rem; margin:0 auto; padding:1.5rem 1.1rem 4rem; }

.hd { display:flex; flex-direction:column; gap:.3rem; margin-bottom:1.5rem; }
h1 { margin:0; font-size:1.45rem; line-height:1.2; letter-spacing:-.015em;
     font-weight:640; text-wrap:balance; }
.sub { font-family:var(--mono); font-size:.76rem; letter-spacing:.02em;
       color:var(--ink2); font-variant-numeric:tabular-nums; }
.sub a { color:var(--accent); text-decoration:none; border-bottom:1px solid var(--line); }
.sub a:hover { border-color:var(--accent); }

.next {
  background:var(--surface); border:1px solid var(--line);
  border-radius:var(--r); padding:1rem 1.1rem; margin-bottom:1.4rem;
  display:flex; flex-direction:column; gap:.45rem;
  box-shadow:0 1px 2px rgba(0,0,0,.04);
}
.next-l { font-family:var(--mono); font-size:.68rem; text-transform:uppercase;
          letter-spacing:.14em; color:var(--accent); }
.next-t { font-size:1.12rem; font-weight:620; line-height:1.3; text-wrap:balance; }
.next-t a { color:inherit; text-decoration:none; }
.next-t a:hover { color:var(--accent); }
.next-m { font-family:var(--mono); font-size:.8rem; color:var(--ink2);
          font-variant-numeric:tabular-nums; display:flex; flex-wrap:wrap;
          gap:.5rem; align-items:center; }

.mini {
  display:block; margin-bottom:1.4rem; padding:.5rem .5rem .1rem;
  background:var(--surface); border:1px solid var(--line);
  border-radius:var(--r); text-decoration:none; position:relative;
}
.mini:hover { border-color:var(--accent); }
.mini svg { display:block; width:100%; height:auto; }
.mini .land path {
  fill:var(--bg); stroke:var(--line); stroke-width:.8;
  stroke-linejoin:round; vector-effect:non-scaling-stroke;
}
.mini .land path.l-ch { fill:var(--ch); fill-opacity:.13; stroke:var(--ch);
                          stroke-opacity:.55; stroke-width:1.4; }
.mini .land path.l-it { fill:var(--it); fill-opacity:.07; }
.mini .land path.l-fr { fill:var(--fr); fill-opacity:.07; }
.mini .land path.l-at { fill:var(--at); fill-opacity:.07; }
.mini .lb {
  font-family:var(--mono); font-size:11px; letter-spacing:.08em;
  text-anchor:middle; pointer-events:none;
  paint-order:stroke; stroke:var(--surface); stroke-width:3.5;
  stroke-linejoin:round; fill:var(--ink2);
}
.mini .lb-ch { fill:var(--ch); font-size:12.5px; font-weight:700; }
.mini .pt { stroke:var(--surface); stroke-width:1.2; }
.mini .pt.vorbei { opacity:.28; }
.mini .pt[data-c="it"] { fill:var(--it); }
.mini .pt[data-c="at"] { fill:var(--at); }
.mini .pt[data-c="fr"] { fill:var(--fr); }
.mini .pt[data-c="ch"] { fill:var(--ch); }
/* Hohl = flache, kindergerechte Strecke. */
.mini .pt.su { fill:var(--surface); stroke-width:2; }
.mini .pt.su[data-c="it"] { stroke:var(--it); }
.mini .pt.su[data-c="at"] { stroke:var(--at); }
.mini .pt.su[data-c="fr"] { stroke:var(--fr); }
.mini .pt.su[data-c="ch"] { stroke:var(--ch); }
.mini .pt.hide { display:none; }
.mini-h {
  display:block; padding:.35rem .3rem .5rem; text-align:right;
  font-family:var(--mono); font-size:.72rem; color:var(--accent);
}
.fil { display:flex; flex-wrap:wrap; gap:.4rem; margin-bottom:.5rem; }
.fil2, .fil3 { margin-bottom:.5rem; }
.fil3 { margin-bottom:1.6rem; }
.fil .cnt { opacity:.7; margin-left:.1rem; }
.fil button {
  font:inherit; font-family:var(--mono); font-size:.76rem; letter-spacing:.02em;
  padding:.34rem .68rem; border-radius:99px; cursor:pointer;
  background:transparent; color:var(--ink2);
  border:1px solid var(--line); transition:.14s;
  font-variant-numeric:tabular-nums;
}
.fil button:hover { color:var(--ink); border-color:var(--ink2); }
.fil button[aria-pressed="true"] {
  background:var(--accent-soft); color:var(--accent-ink);
  border-color:var(--accent);
}
.fil button:focus-visible, .lnk:focus-visible, .n:focus-visible,
summary:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }

.vh { position:absolute; width:1px; height:1px; margin:-1px; padding:0;
      overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; border:0; }

/* --- Ansichtsumschalter Liste / Kalender --- */
.views { display:flex; align-items:center; gap:.5rem; flex-wrap:wrap;
         margin:0 0 1rem; }
.seg { display:inline-flex; padding:2px; gap:2px; border-radius:99px;
       border:1px solid var(--line); background:var(--surface); }
.seg button {
  font:inherit; font-family:var(--mono); font-size:.74rem; letter-spacing:.02em;
  padding:.34rem .8rem; border-radius:99px; cursor:pointer;
  background:transparent; color:var(--ink2); border:0; transition:.14s;
}
.seg button:hover { color:var(--ink); }
.seg button[aria-pressed="true"] { background:var(--accent-soft);
                                   color:var(--accent-ink); }
.seg button:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
.mine {
  font:inherit; font-family:var(--mono); font-size:.74rem;
  padding:.36rem .7rem; border-radius:99px; cursor:pointer;
  background:transparent; color:var(--ink2); border:1px solid var(--line);
  transition:.14s; font-variant-numeric:tabular-nums;
}
.mine:hover { color:var(--ink); border-color:var(--ink2); }
.mine[aria-pressed="true"] { background:var(--accent-soft);
  color:var(--accent-ink); border-color:var(--accent); }
.mine:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
.mine .mk-i { vertical-align:-1px; margin-right:.35rem; }

/* --- Merken --- */
.mk {
  border:0; background:none; padding:.15rem; margin:0; cursor:pointer;
  display:flex; align-items:center; justify-content:center; align-self:start;
  border-radius:6px; line-height:0;
}
.mk-i {
  display:inline-block; width:13px; height:13px; border-radius:4px;
  border:1.5px solid var(--line); background:transparent;
  transition:.14s; position:relative;
}
.mk:hover .mk-i { border-color:var(--accent); }
.mk[aria-pressed="true"] .mk-i,
.mine[aria-pressed="true"] .mk-i {
  background:var(--accent); border-color:var(--accent);
}
.mk[aria-pressed="true"] .mk-i::after,
.mine[aria-pressed="true"] .mk-i::after {
  content:""; position:absolute; left:3.5px; top:.5px;
  width:3.5px; height:7px; border:solid var(--surface);
  border-width:0 1.8px 1.8px 0; transform:rotate(42deg);
}
.mk:focus-visible { outline:2px solid var(--accent); outline-offset:1px; }
.ev.marked { background:var(--accent-soft); }
.ev.marked .n { color:var(--accent-ink); }

/* --- Kalenderansicht --- */
#cal { margin-bottom:1.5rem; }
.cal-g { display:grid; gap:1.4rem 1.5rem;
         grid-template-columns:repeat(auto-fill,minmax(15.5rem,1fr)); }
.cmo { min-width:0; }
.cmo-h {
  margin:0 0 .5rem; font-family:var(--mono); font-weight:500;
  font-size:.7rem; text-transform:uppercase; letter-spacing:.16em;
  color:var(--ink2); display:flex; align-items:center; gap:.5rem;
  padding-bottom:.35rem; border-bottom:1px solid var(--line);
}
.cmo-n { margin-left:auto; font-variant-numeric:tabular-nums; opacity:.75; }
.cgrid { display:grid; grid-template-columns:repeat(7,1fr); gap:2px; }
.cwd {
  font-family:var(--mono); font-size:.6rem; text-transform:uppercase;
  letter-spacing:.08em; color:var(--ink2); text-align:center;
  padding:.2rem 0 .3rem; opacity:.8;
}
.cd { aspect-ratio:1; }
/* Wochenende leicht getoent: fast alle Sperrungen liegen dort, und im
   Raster sieht man dann sofort, ob ein Termin unter der Woche liegt. */
.cwd:nth-child(6), .cwd:nth-child(7) { color:var(--accent); opacity:1; }
/* Vor den Tageszellen stehen genau 7 .cwd-Koepfe, deshalb faellt Samstag
   auf 7n+6 und Sonntag auf 7n+7. */
.cd:nth-child(7n+6), .cd:nth-child(7n+7) { background:var(--wkend);
                                           border-radius:7px; }
.cd-b {
  width:100%; height:100%; border:1px solid transparent; background:transparent;
  border-radius:7px; padding:.15rem 0 0; cursor:default; font:inherit;
  display:flex; flex-direction:column; align-items:center; gap:2px;
  color:var(--ink2); transition:.14s;
}
.cd-n { font-family:var(--mono); font-size:.72rem; line-height:1.1;
        font-variant-numeric:tabular-nums; }
.cd-dots { display:flex; gap:2px; flex-wrap:wrap; justify-content:center;
           min-height:5px; }
.cd-dots i { width:5px; height:5px; border-radius:50%; display:block; }
.cd-dots i.d-it { background:var(--it); } .cd-dots i.d-at { background:var(--at); }
.cd-dots i.d-fr { background:var(--fr); } .cd-dots i.d-ch { background:var(--ch); }
.cd.has .cd-b { cursor:pointer; color:var(--ink); background:var(--surface);
                border-color:var(--line); font-weight:600; }
.cd.has .cd-b:hover { border-color:var(--accent); }
.cd.has .cd-b:focus-visible { outline:2px solid var(--accent); outline-offset:1px; }
.cd.marked .cd-b { background:var(--accent-soft); color:var(--accent-ink);
                   border-color:var(--accent); box-shadow:inset 0 0 0 1px var(--accent); }
.cd.marked .cd-n { font-weight:700; }
.cd.sel .cd-b { border-color:var(--accent); box-shadow:0 0 0 2px var(--accent-soft); }
.cd.today .cd-n { text-decoration:underline; text-underline-offset:2px;
                  text-decoration-thickness:2px;
                  text-decoration-color:var(--accent); }
.cd.past-d .cd-b { opacity:.42; }
.cd-e { visibility:hidden; }

.cdet {
  margin-top:1.2rem; background:var(--surface); border:1px solid var(--line);
  border-radius:var(--r); padding:.9rem 1rem;
}
.cdet-h { font-family:var(--mono); font-size:.68rem; text-transform:uppercase;
          letter-spacing:.14em; color:var(--accent); margin-bottom:.5rem; }
.cdet .lst { gap:.1rem; }
.cdet .ev { grid-template-columns:1.2rem 1fr; }
.cdet .ev:hover { background:var(--bg); }
.cdet-p { font-family:var(--mono); font-size:.8rem; color:var(--ink2); margin:0; }

.mo { margin-bottom:1.7rem; }
.mo-h {
  margin:0 0 .55rem; font-family:var(--mono); font-weight:500;
  font-size:.7rem; text-transform:uppercase; letter-spacing:.16em;
  color:var(--ink2); display:flex; align-items:center; gap:.55rem;
  padding-bottom:.4rem; border-bottom:1px solid var(--line);
}
.mo-n { margin-left:auto; font-variant-numeric:tabular-nums; opacity:.75; }

.lst { list-style:none; margin:0; padding:0; display:flex;
       flex-direction:column; gap:.15rem; }
.ev {
  display:grid; grid-template-columns:1.2rem 3.7rem 1fr; gap:.15rem .7rem;
  padding:.6rem .7rem; border-radius:8px; align-items:baseline;
}
.ev:hover { background:var(--surface); }
.d { display:flex; flex-direction:column; gap:.05rem; }
.wd { font-family:var(--mono); font-size:.66rem; text-transform:uppercase;
      letter-spacing:.1em; color:var(--ink2); }
/* Kein nowrap: monatsuebergreifende Bereiche ("30. Mai–2. Juni") behalten
   den Volltext und sollen umbrechen statt in die Nachbarspalte zu laufen. */
.dm { font-family:var(--mono); font-size:.82rem; color:var(--ink);
      font-variant-numeric:tabular-nums; overflow-wrap:break-word; }
.b { display:flex; flex-direction:column; gap:.18rem; min-width:0; }
.n { font-size:.97rem; font-weight:530; color:var(--ink);
     text-decoration:none; overflow-wrap:anywhere; }
a.n:hover { color:var(--accent); text-decoration:underline;
            text-underline-offset:2px; }
.m { display:flex; flex-wrap:wrap; gap:.4rem; align-items:center; }
.c { font-family:var(--mono); font-size:.68rem; letter-spacing:.05em;
     color:var(--ink2); display:inline-flex; align-items:center; gap:.3rem; }
.c::before { content:""; width:7px; height:7px; border-radius:50%;
             background:currentColor; flex:none; }
.c-it { color:var(--it); } .c-at { color:var(--at); }
.c-fr { color:var(--fr); } .c-ch { color:var(--ch); }
.su {
  font-family:var(--mono); font-size:.62rem; text-transform:uppercase;
  letter-spacing:.1em; padding:.1rem .35rem; border-radius:3px;
  border:1px solid currentColor; color:var(--ink2); font-weight:600;
}
.neu {
  font-family:var(--mono); font-size:.62rem; text-transform:uppercase;
  letter-spacing:.1em; padding:.1rem .35rem; border-radius:3px;
  background:var(--accent-soft); color:var(--accent-ink); font-weight:600;
}

.past { margin-top:2.2rem; border-top:1px solid var(--line); padding-top:1rem; }
.past summary {
  cursor:pointer; font-family:var(--mono); font-size:.76rem;
  color:var(--ink2); list-style:none; padding:.3rem 0;
  font-variant-numeric:tabular-nums;
}
.past summary::-webkit-details-marker { display:none; }
.past summary::before { content:"\\25B8  "; display:inline-block;
                        transition:transform .15s; }
.past[open] summary::before { transform:rotate(90deg); }
.past summary:hover { color:var(--ink); }
.past[open] .mo { opacity:.62; }

.ft { margin-top:2.6rem; padding-top:1.2rem; border-top:1px solid var(--line);
      display:flex; flex-direction:column; gap:.55rem;
      font-family:var(--mono); font-size:.76rem; color:var(--ink2); }
.lnk { color:var(--accent); text-decoration:none;
       border-bottom:1px solid var(--line); }
.lnk:hover { border-color:var(--accent); }
.empty { padding:2rem .7rem; color:var(--ink2); font-family:var(--mono);
         font-size:.82rem; }
.hide { display:none !important; }

/* Schmale Schirme: Filterzeilen einzeilig und wischbar statt umbrechend.
   Drei umbrechende Zeilen ergaben sechs Zeilen Chips - der erste Termin lag
   damit weit unter dem Falz. */
@media (max-width:40rem) {
  .fil {
    flex-wrap:nowrap; overflow-x:auto; overflow-y:hidden;
    -webkit-overflow-scrolling:touch; scrollbar-width:none;
    padding-bottom:.15rem; margin-bottom:.4rem;
  }
  .fil::-webkit-scrollbar { display:none; }
  .fil button { flex:0 0 auto; }
  .fil3 { margin-bottom:1.2rem; }
}
@media (max-width:29rem) {
  .ev { grid-template-columns:1.2rem 1fr; gap:.15rem .7rem;
        padding:.55rem .5rem; }
  .ev .b { grid-column:2; }
  .d { flex-direction:row; gap:.45rem; align-items:baseline; }
  .cal-g { grid-template-columns:1fr; }
}
/* Touch-Ziele >= 44px. pointer:coarse trifft Finger-Bedienung, nicht bloss
   schmale Fenster - ein kleines Desktop-Fenster braucht das nicht. */
@media (pointer: coarse) {
  .fil button { min-height:44px; padding:.6rem .9rem; }
  .seg button, .mine { min-height:44px; padding:.6rem 1rem; }
  .mk { min-width:34px; min-height:34px; margin:-.35rem 0 0 -.6rem; }
  .cd-b { border-radius:8px; }
  .past summary { min-height:44px; display:flex; align-items:center; }
  .ft { gap:.9rem; }
  .ft .lnk { display:inline-block; padding:.32rem 0; }
}
@media (prefers-reduced-motion: reduce) {
  * { transition:none !important; animation:none !important; }
}
</style>

<div class="wrap">
  <header class="hd">
    <h1>Autofreie Bike-Tage $spanne</h1>
    <p class="sub">$total Termine &middot; Stand $stand &middot; Quellen
      <a href="$quelle_url" target="_blank" rel="noopener noreferrer">$quelle_name</a>
      &middot;
      <a href="$quelle2_url" target="_blank" rel="noopener noreferrer">$quelle2_name</a>
    </p>
  </header>

  $next_block

  $minimap

  <nav class="fil" id="fil" aria-label="Nach Land filtern">
    $filter_buttons
  </nav>

  <nav class="fil fil2" id="fil2" aria-label="Nach Streckenart filtern">
    <button type="button" data-ter="all" aria-pressed="true">Alle Strecken
      <span class="cnt"></span></button>
    <button type="button" data-ter="flach">Flach &middot; kindergerecht
      <span class="cnt"></span></button>
    <button type="button" data-ter="berg">Pässe <span class="cnt"></span></button>
  </nav>

  <nav class="fil fil3" id="fil3" aria-label="Nach Saison filtern">
    $jahr_buttons
  </nav>

  <div class="views">
    <div class="seg" id="seg" role="group" aria-label="Ansicht wählen">
      <button type="button" data-view="list" aria-pressed="true">Liste</button>
      <button type="button" data-view="cal" aria-pressed="false">Kalender</button>
    </div>
    <button type="button" class="mine" id="mine" aria-pressed="false">
      <span class="mk-i" aria-hidden="true"></span>Nur vorgemerkte
      <span class="cnt" id="mine-n">0</span></button>
  </div>

  <section id="cal" class="hide" aria-label="Kalenderansicht">
    <div class="cal-g" id="cal-g"></div>
    <div class="cdet" id="cdet">
      <p class="cdet-p">Einen hervorgehobenen Tag antippen, um seine Termine
        zu sehen und vorzumerken.</p>
    </div>
  </section>

  <main id="upcoming">
    $upcoming
  </main>

  <p class="empty hide" id="empty">Keine Termine für diese Auswahl.</p>

  $past_block

  <footer class="ft">
    <span id="ft-mine">Vorgemerkte Termine bleiben in diesem Browser
      gespeichert &mdash; sie überstehen die wöchentliche Aktualisierung,
      wandern aber nicht auf andere Geräte.</span>
    <span>Kalender abonnieren:
      <a class="lnk" href="$pages/autofrei.ics">autofrei.ics</a>
      &mdash; in Outlook, Google oder Apple Kalender als URL hinzufügen
    </span>
    <span>
      <a class="lnk" href="$pages/karte.html">Karte ansehen</a> &middot;
      <a class="lnk" href="$pages/autofrei.geojson">GeoJSON</a> für ArcGIS Online
    </span>
  </footer>
</div>

<script type="application/json" id="evd">$events_json</script>

<script>
(function () {
  var empty = document.getElementById('empty');
  var alleEv = [].slice.call(document.querySelectorAll('.ev'));

  // --- Vorgemerkte Termine ---------------------------------------------
  // Bewusst localStorage und nicht im HTML: das Artifact wird woechentlich
  // neu generiert und ueberschrieben. Im Markup gespeicherte Haken waeren
  // jeden Montag weg, der Browser-Speicher ueberlebt die Neuveroeffentlichung.
  // Schluessel ist die Event-ID (marker + dateStart), die stabil bleibt.
  var MK_KEY = 'autofrei.marks.v1';
  var marks = {};
  try {
    marks = JSON.parse(localStorage.getItem(MK_KEY) || '{}') || {};
  } catch (e) { marks = {}; }

  function marksSpeichern() {
    // Privater Modus, volles Kontingent, blockierte Site-Daten: alles
    // moeglich. Die Seite muss trotzdem funktionieren, nur ohne Gedaechtnis.
    try { localStorage.setItem(MK_KEY, JSON.stringify(marks)); } catch (e) {}
  }

  // --- Filter ------------------------------------------------------------
  // Vier unabhaengige Filter, gleichzeitig angewendet:
  // "Schweiz + flach + 2026 + nur vorgemerkte" muss moeglich sein.
  var f = { land: 'all', ter: 'all', jahr: '$default_jahr', mine: false };

  function trifftZu(el, ausser) {
    return (ausser === 'land' || f.land === 'all' || el.dataset.c === f.land)
        && (ausser === 'ter'  || f.ter === 'all'
            || (f.ter === 'flach' ? el.dataset.f === '1' : el.dataset.f !== '1'))
        && (ausser === 'jahr' || f.jahr === 'all' || el.dataset.y === f.jahr)
        && (!f.mine || !el.dataset.id || !!marks[el.dataset.id]);
  }

  // Zaehler jeder Schaltflaeche gegen die JEWEILS ANDEREN Filter rechnen -
  // sonst behauptet "Italien 9", waehrend bei aktivem Jahresfilter nur 4
  // uebrig sind.
  function zaehlerSetzen(nav, attr, dimension) {
    nav.querySelectorAll('button').forEach(function (b) {
      var wert = b.dataset[attr];
      var n = 0;
      for (var i = 0; i < alleEv.length; i++) {
        var el = alleEv[i];
        if (el.closest('.past')) { continue; }
        if (!trifftZu(el, dimension)) { continue; }
        if (wert === 'all'
            || (dimension === 'land' && el.dataset.c === wert)
            || (dimension === 'ter' && (wert === 'flach'
                  ? el.dataset.f === '1' : el.dataset.f !== '1'))
            || (dimension === 'jahr' && el.dataset.y === wert)) { n++; }
      }
      var sp = b.querySelector('.cnt');
      if (sp) { sp.textContent = n; }
    });
  }

  function anwenden() {
    alleEv.forEach(function (el) {
      el.classList.toggle('hide', !trifftZu(el));
    });
    document.querySelectorAll('.mini .pt').forEach(function (pt) {
      pt.classList.toggle('hide', !trifftZu(pt));
    });

    document.querySelectorAll('.mo').forEach(function (mo) {
      var n = mo.querySelectorAll('.ev:not(.hide)').length;
      mo.classList.toggle('hide', n === 0);
      var z = mo.querySelector('.mo-n');
      if (z) { z.textContent = n; }
    });

    var pn = document.getElementById('pn');
    if (pn) {
      pn.textContent = document.querySelectorAll('.past .ev:not(.hide)').length;
    }

    zaehlerSetzen(document.getElementById('fil'), 'land', 'land');
    zaehlerSetzen(document.getElementById('fil2'), 'ter', 'ter');
    zaehlerSetzen(document.getElementById('fil3'), 'jahr', 'jahr');

    var offen = document.querySelectorAll('#upcoming .ev:not(.hide)').length;
    empty.classList.toggle('hide', offen > 0 || ansicht === 'cal');

    hakenZeichnen();
    if (ansicht === 'cal') { kalenderZeichnen(); }
  }

  [['fil', 'land'], ['fil2', 'ter'], ['fil3', 'jahr']].forEach(function (paar) {
    var nav = document.getElementById(paar[0]);
    nav.addEventListener('click', function (e) {
      var btn = e.target.closest('button');
      if (!btn) { return; }
      nav.querySelectorAll('button').forEach(function (b) {
        b.setAttribute('aria-pressed', String(b === btn));
      });
      f[paar[1]] = btn.dataset[paar[1]];
      anwenden();
    });
  });

  // --- Haken setzen ------------------------------------------------------
  var mineBtn = document.getElementById('mine');
  var mineN = document.getElementById('mine-n');

  function hakenZeichnen() {
    var n = 0;
    for (var k in marks) { if (marks[k]) { n++; } }
    mineN.textContent = n;
    mineBtn.disabled = n === 0 && !f.mine;
    mineBtn.style.opacity = mineBtn.disabled ? '.5' : '';

    document.querySelectorAll('[data-mk]').forEach(function (b) {
      var an = !!marks[b.dataset.mk];
      b.setAttribute('aria-pressed', String(an));
      b.title = an ? 'Vormerkung entfernen' : 'Für mich vormerken';
      var li = b.closest('.ev');
      if (li) { li.classList.toggle('marked', an); }
    });
  }

  // Delegiert, damit auch die im Kalender nachgerenderten Knoepfe wirken.
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-mk]');
    if (!b) { return; }
    e.preventDefault();
    var id = b.dataset.mk;
    if (marks[id]) { delete marks[id]; } else { marks[id] = 1; }
    marksSpeichern();
    anwenden();
    if (tagOffen) { detailZeichnen(tagOffen); }
  });

  mineBtn.addEventListener('click', function () {
    f.mine = !f.mine;
    mineBtn.setAttribute('aria-pressed', String(f.mine));
    anwenden();
  });

  // --- Kalenderansicht ---------------------------------------------------
  var MONAT = ['', 'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
               'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'];
  var WD = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];
  var LAND = { it: 'Italien', at: 'Österreich', fr: 'Frankreich', ch: 'Schweiz' };

  var daten = [];
  try {
    daten = JSON.parse(document.getElementById('evd').textContent) || [];
  } catch (e) { daten = []; }

  var calSec = document.getElementById('cal');
  var calG = document.getElementById('cal-g');
  var cdet = document.getElementById('cdet');
  var ansicht = 'list';
  var tagOffen = null;
  var heuteIso = (function () {
    var d = new Date();
    return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2)
         + '-' + ('0' + d.getDate()).slice(-2);
  })();

  function sichtbar(e) {
    return (f.land === 'all' || e.c === f.land)
        && (f.ter === 'all' || (f.ter === 'flach' ? e.fl : !e.fl))
        && (f.jahr === 'all' || e.y === f.jahr)
        && (!f.mine || !!marks[e.id]);
  }

  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // Termin -> alle betroffenen Tage. Mehrtaegige Sperrungen sollen im
  // Raster ueber ihre ganze Dauer erscheinen, nicht nur am Starttag.
  function tageVon(e) {
    var out = [];
    if (!e.s) { return out; }
    var d = new Date(e.s + 'T00:00:00Z');
    var bis = new Date((e.e || e.s) + 'T00:00:00Z');
    if (isNaN(d) || isNaN(bis) || bis < d) { return [e.s]; }
    var schutz = 0;
    while (d <= bis && schutz++ < 400) {
      out.push(d.toISOString().slice(0, 10));
      d.setUTCDate(d.getUTCDate() + 1);
    }
    return out;
  }

  function kalenderZeichnen() {
    var proTag = {};
    daten.filter(sichtbar).forEach(function (e) {
      tageVon(e).forEach(function (t) {
        (proTag[t] = proTag[t] || []).push(e);
      });
    });

    var tage = Object.keys(proTag).sort();
    if (!tage.length) {
      calG.innerHTML = '<p class="empty">Keine Termine für diese Auswahl.</p>';
      tagOffen = null;
      detailZeichnen(null);
      return;
    }

    // Von erstem bis letztem Termin durchgehend - Monate ohne Termine
    // bleiben stehen, damit die Luecken im Jahr sichtbar werden.
    var von = tage[0], bis = tage[tage.length - 1];
    var y = +von.slice(0, 4), m = +von.slice(5, 7);
    var yEnd = +bis.slice(0, 4), mEnd = +bis.slice(5, 7);
    var teile = [];
    var schutz = 0;

    while ((y < yEnd || (y === yEnd && m <= mEnd)) && schutz++ < 120) {
      teile.push(monatHtml(y, m, proTag));
      m++;
      if (m > 12) { m = 1; y++; }
    }
    calG.innerHTML = teile.join('');

    if (tagOffen && !proTag[tagOffen]) { tagOffen = null; }
    detailZeichnen(tagOffen);
  }

  function monatHtml(y, m, proTag) {
    var erster = new Date(Date.UTC(y, m - 1, 1));
    var vorlauf = (erster.getUTCDay() + 6) % 7;      // Montag = 0
    var tage = new Date(Date.UTC(y, m, 0)).getUTCDate();

    var zellen = [];
    for (var i = 0; i < vorlauf; i++) {
      zellen.push('<div class="cd cd-e"></div>');
    }

    // Gezaehlt werden Termine, die in diesem Monat BEGINNEN - so steht in
    // der Kopfzeile dieselbe Zahl wie in der Listenansicht. Tage zu zaehlen
    // wuerde mehrtaegige Sperrungen mehrfach mitnehmen.
    var anzahl = 0;
    var praefix = y + '-' + ('0' + m).slice(-2);
    daten.forEach(function (e) {
      if (sichtbar(e) && e.s.slice(0, 7) === praefix) { anzahl++; }
    });

    for (var t = 1; t <= tage; t++) {
      var iso = praefix + '-' + ('0' + t).slice(-2);
      var evs = proTag[iso] || [];

      var laender = [];
      evs.forEach(function (e) {
        if (laender.indexOf(e.c) === -1) { laender.push(e.c); }
      });
      var punkte = laender.slice(0, 4).map(function (c) {
        return '<i class="d-' + c + '"></i>';
      }).join('');

      var kl = ['cd'];
      if (evs.length) { kl.push('has'); }
      if (iso < heuteIso) { kl.push('past-d'); }
      if (iso === heuteIso) { kl.push('today'); }
      if (iso === tagOffen) { kl.push('sel'); }
      if (evs.some(function (e) { return marks[e.id]; })) { kl.push('marked'); }

      var innen = '<span class="cd-n">' + t + '</span>'
        + '<span class="cd-dots">' + punkte + '</span>';

      // Tage ohne Termine sind kein Bedienelement - sonst laeuft man beim
      // Tabben durch 30 tote Schaltflaechen pro Monat.
      zellen.push(
        '<div class="' + kl.join(' ') + '">'
        + (evs.length
            ? '<button type="button" class="cd-b" data-day="' + iso + '" '
              + 'aria-label="' + t + '. ' + MONAT[m] + ' ' + y + ', '
              + evs.length + (evs.length === 1 ? ' Termin' : ' Termine') + '">'
              + innen + '</button>'
            : '<div class="cd-b">' + innen + '</div>')
        + '</div>'
      );
    }

    return '<section class="cmo"><h3 class="cmo-h">' + MONAT[m] + ' ' + y
      + '<span class="cmo-n">' + anzahl + '</span></h3>'
      + '<div class="cgrid" role="grid">'
      + WD.map(function (w) { return '<div class="cwd">' + w + '</div>'; }).join('')
      + zellen.join('') + '</div></section>';
  }

  function evLi(e) {
    var titel = e.u
      ? '<a class="n" href="' + esc(e.u) + '" target="_blank" '
        + 'rel="noopener noreferrer">' + esc(e.n) + '</a>'
      : '<span class="n">' + esc(e.n) + '</span>';
    // Mehrtaegiges laeuft ueber den gewaehlten Tag hinaus - dann gehoert
    // der Zeitraum dazu, sonst waere er schon in der Kopfzeile doppelt.
    var spanne = e.e !== e.s ? '<span class="dm">' + esc(e.r) + '</span>' : '';
    return '<li class="ev' + (marks[e.id] ? ' marked' : '') + '">'
      + '<button type="button" class="mk" data-mk="' + esc(e.id) + '" '
      + 'aria-pressed="' + (marks[e.id] ? 'true' : 'false') + '">'
      + '<span class="mk-i" aria-hidden="true"></span>'
      + '<span class="vh">Für mich vormerken</span></button>'
      + '<div class="b">' + titel + '<div class="m">'
      + '<span class="c c-' + e.c + '">' + esc(LAND[e.c] || e.c) + '</span>'
      + (e.su ? '<span class="su">slowUp</span>' : '') + spanne + '</div></div></li>';
  }

  function detailZeichnen(iso) {
    if (!iso) {
      cdet.innerHTML = '<p class="cdet-p">Einen hervorgehobenen Tag antippen, '
        + 'um seine Termine zu sehen und vorzumerken.</p>';
      return;
    }
    var evs = daten.filter(function (e) {
      return sichtbar(e) && tageVon(e).indexOf(iso) !== -1;
    });
    var d = new Date(iso + 'T00:00:00Z');
    var kopf = WD[(d.getUTCDay() + 6) % 7] + ', ' + d.getUTCDate() + '. '
      + MONAT[d.getUTCMonth() + 1] + ' ' + d.getUTCFullYear();
    cdet.innerHTML = '<div class="cdet-h">' + kopf + '</div>'
      + '<ul class="lst">' + evs.map(evLi).join('') + '</ul>';
  }

  calG.addEventListener('click', function (e) {
    var b = e.target.closest('.cd-b[data-day]');
    if (!b || !b.closest('.cd').classList.contains('has')) { return; }
    tagOffen = b.dataset.day === tagOffen ? null : b.dataset.day;
    calG.querySelectorAll('.cd.sel').forEach(function (c) {
      c.classList.remove('sel');
    });
    if (tagOffen) { b.closest('.cd').classList.add('sel'); }
    detailZeichnen(tagOffen);
    if (tagOffen) { cdet.scrollIntoView({ block: 'nearest' }); }
  });

  var seg = document.getElementById('seg');
  seg.addEventListener('click', function (e) {
    var btn = e.target.closest('button');
    if (!btn) { return; }
    ansicht = btn.dataset.view;
    seg.querySelectorAll('button').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b === btn));
    });
    calSec.classList.toggle('hide', ansicht !== 'cal');
    document.getElementById('upcoming').classList.toggle('hide', ansicht === 'cal');
    var past = document.querySelector('.past');
    if (past) { past.classList.toggle('hide', ansicht === 'cal'); }
    anwenden();
  });

  anwenden();

  // Countdown erst im Browser rechnen - die Seite kann Tage nach der
  // Generierung geoeffnet werden.
  var cd = document.getElementById('cd');
  if (cd && cd.dataset.date) {
    var heute = new Date(); heute.setHours(0, 0, 0, 0);
    var ziel = new Date(cd.dataset.date + 'T00:00:00');
    var tage = Math.round((ziel - heute) / 86400000);
    cd.textContent = tage < 0 ? 'vorbei'
      : tage === 0 ? 'heute'
      : tage === 1 ? 'morgen'
      : 'in ' + tage + ' Tagen';
  }
})();
</script>
""")


def build_html(data):
    events = data["events"]
    heute = date.today().isoformat()

    kommend = [e for e in events if e["dateStart"] and e["dateStart"] >= heute]
    vergangen = [e for e in events if not (e["dateStart"] and e["dateStart"] >= heute)]

    # --- "Als Naechstes" ---
    if kommend:
        n = kommend[0]
        n_url = sichere_url(n.get("url"))
        if n_url:
            titel = ('<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>'
                     % (esc(n_url), esc(n["name"])))
        else:
            titel = esc(n["name"])
        next_block = (
            '<div class="next">'
            '<span class="next-l">Als Nächstes</span>'
            '<span class="next-t">%s</span>'
            '<span class="next-m"><span>%s</span>'
            '<span class="c c-%s">%s</span>'
            '<span id="cd" data-date="%s"></span></span>'
            "</div>"
        ) % (titel, esc(datum_kurz(n)), n["country"],
             esc(LAND_NAME.get(n["country"], n["country"])), n["dateStart"])
    else:
        next_block = ('<div class="next"><span class="next-l">Saison</span>'
                      '<span class="next-t">Für %s sind keine Termine mehr offen.'
                      "</span></div>" % data["season"])

    # --- Filter mit echten Zaehlern der kommenden Termine ---
    zaehler = {}
    for e in kommend:
        zaehler[e["country"]] = zaehler.get(e["country"], 0) + 1

    knoepfe = ['<button type="button" data-land="all" aria-pressed="true">'
               'Alle <span class="cnt"></span></button>']
    for code in ("it", "at", "fr", "ch"):
        if zaehler.get(code):
            knoepfe.append(
                '<button type="button" data-land="%s" aria-pressed="false">'
                '%s <span class="cnt"></span></button>' % (code, LAND_NAME[code])
            )

    # Saison-Filter. Vorbelegt ist das laufende Jahr - danach wird am
    # haeufigsten gesucht, und slowUp reicht bis 2028.
    jahre_kommend = sorted({e["dateStart"][:4] for e in kommend if e["dateStart"]})
    jetzt = str(date.today().year)
    default_jahr = jetzt if jetzt in jahre_kommend else (
        jahre_kommend[0] if jahre_kommend else "all")
    jahr_knoepfe = []
    for j in jahre_kommend:
        jahr_knoepfe.append(
            '<button type="button" data-jahr="%s" aria-pressed="%s">'
            '%s <span class="cnt"></span></button>'
            % (j, "true" if j == default_jahr else "false", j)
        )
    jahr_knoepfe.append(
        '<button type="button" data-jahr="all" aria-pressed="%s">'
        'Alle Jahre <span class="cnt"></span></button>'
        % ("true" if default_jahr == "all" else "false")
    )

    # --- Vergangene: eingeklappt, sonst waeren 3/4 der Seite Altlast ---
    if vergangen:
        past_block = (
            '<details class="past"><summary><span id="pn">%d</span> vergangene '
            'Termine %s anzeigen</summary>%s</details>'
        ) % (len(vergangen), data["season"], render_gruppen(gruppiere_nach_monat(vergangen)))
    else:
        past_block = ""

    jahre = sorted({e["dateStart"][:4] for e in events if e["dateStart"]})
    spanne = jahre[0] if len(jahre) <= 1 else "%s–%s" % (jahre[0], jahre[-1])

    return PAGE.substitute(
        spanne=spanne,
        quelle_url=QUELLE_URL,
        quelle_name=QUELLE_NAME,
        quelle2_url=QUELLE2_URL,
        quelle2_name=QUELLE2_NAME,
        season=data["season"],
        total=len(events),
        stand=data["fetchedAt"],
        next_block=next_block,
        filter_buttons="\n    ".join(knoepfe),
        jahr_buttons="\n    ".join(jahr_knoepfe),
        default_jahr=default_jahr,
        upcoming=render_gruppen(gruppiere_nach_monat(kommend)) or
                 '<p class="empty">Keine kommenden Termine.</p>',
        minimap=build_minimap(events),
        past_block=past_block,
        events_json=events_json(events),
        pages=PAGES_BASE,
    )


INDEX = Template("""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Autofreie Bike-Tage $season</title>
<style>
  :root { color-scheme: light dark;
    --bg:#f2f5f4; --surface:#fff; --ink:#16211f; --ink2:#5d6f6c;
    --line:#dde4e3; --accent:#0e6e6b; }
  @media (prefers-color-scheme: dark) { :root {
    --bg:#0f1514; --surface:#18211f; --ink:#e7edec; --ink2:#8fa39f;
    --line:#26322f; --accent:#4fd1c7; } }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
    font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
  .w { max-width:38rem; margin:0 auto; padding:2.5rem 1.2rem 4rem; }
  h1 { font-size:1.5rem; margin:0 0 .3rem; letter-spacing:-.015em; }
  .meta { font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
    font-size:.78rem; color:var(--ink2); margin:0 0 2rem; }
  h2 { font-size:1rem; margin:2rem 0 .6rem; }
  .card { background:var(--surface); border:1px solid var(--line);
    border-radius:10px; padding:1rem 1.1rem; margin-bottom:.7rem; }
  .card a { color:var(--accent); font-weight:600; text-decoration:none; }
  .card a:hover { text-decoration:underline; }
  .card p { margin:.3rem 0 0; font-size:.88rem; color:var(--ink2); }
  code { font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
    font-size:.8rem; background:var(--surface); border:1px solid var(--line);
    border-radius:5px; padding:.15rem .4rem; overflow-wrap:anywhere; }
  ol { padding-left:1.2rem; } li { margin:.35rem 0; font-size:.92rem; }
  .feeds { border-collapse:collapse; width:100%; margin:.8rem 0 1rem;
           font-size:.85rem; }
  .feeds th, .feeds td { text-align:left; padding:.4rem .5rem;
                         border-bottom:1px solid var(--line); }
  .feeds th { font-size:.72rem; text-transform:uppercase;
              letter-spacing:.08em; color:var(--ink2); font-weight:600; }
  .feeds td:nth-child(2) { text-align:right; font-variant-numeric:tabular-nums;
                           color:var(--ink2); white-space:nowrap; }
  .feeds code { font-size:.74rem; word-break:break-all; background:none;
                border:0; padding:0; }
  .url { display:block; margin:.6rem 0; padding:.6rem .7rem;
    background:var(--surface); border:1px solid var(--line);
    border-radius:7px; font-family:ui-monospace,Menlo,monospace;
    font-size:.78rem; overflow-x:auto; white-space:nowrap; }
  footer { margin-top:2.5rem; padding-top:1rem; border-top:1px solid var(--line);
    font-size:.8rem; color:var(--ink2); }
  footer a { color:var(--accent); }
</style>
</head>
<body>
<div class="w">
  <h1>Autofreie Bike-Tage $season</h1>
  <p class="meta">$total Termine &middot; Italien, Österreich, Frankreich,
     Schweiz &middot; Stand $stand</p>

  <div class="card">
    <a href="karte.html">Karte ansehen &rarr;</a>
    <p>Alle Termine auf der Landkarte, umschaltbar nach Land.</p>
  </div>
  <div class="card">
    <a href="autofrei.geojson" download>GeoJSON herunterladen &rarr;</a>
    <p>Zum Import als Layer in ArcGIS Online.</p>
  </div>

  <h2>Kalender abonnieren</h2>
  <p style="font-size:.92rem"><strong>Adresse abonnieren, Datei nicht
     herunterladen.</strong> Wer die .ics herunterl&auml;dt und anklickt,
     <em>importiert</em> sie einmalig &ndash; der Kalender hei&szlig;t dann
     &bdquo;Untitled&ldquo; und erh&auml;lt nie wieder Updates. Beim
     Abonnieren &uuml;bernimmt der Kalender den Namen und aktualisiert sich
     w&ouml;chentlich von selbst.</p>
  <p style="font-size:.92rem">Wie oft ein Anbieter tats&auml;chlich nachl&auml;dt,
     bestimmt er selbst. Outlook pr&uuml;ft eher t&auml;glich bis seltener &ndash;
     neue Termine k&ouml;nnen also einen Tag brauchen.</p>
  <p style="font-size:.92rem"><strong>Farbe nach Land?</strong> Outlook,
     Apple und Google f&auml;rben pro <em>Kalender</em>, nicht pro Termin.
     Abonniere daher die L&auml;nder einzeln und weise jedem Abo im
     Kalenderprogramm eine Farbe zu.</p>

  <table class="feeds">
    <tr><th>Feed</th><th>Termine</th><th>Adresse</th></tr>
    <tr><td>Alle</td><td>$n_alle</td><td><code>$pages/autofrei.ics</code></td></tr>
    <tr><td>Italien</td><td>$n_it</td><td><code>$pages/autofrei-it.ics</code></td></tr>
    <tr><td>Österreich</td><td>$n_at</td><td><code>$pages/autofrei-at.ics</code></td></tr>
    <tr><td>Frankreich</td><td>$n_fr</td><td><code>$pages/autofrei-fr.ics</code></td></tr>
    <tr><td>Schweiz</td><td>$n_ch</td><td><code>$pages/autofrei-ch.ics</code></td></tr>
    <tr><td>Flach &middot; kindergerecht</td><td>$n_flach</td>
        <td><code>$pages/autofrei-flach.ics</code></td></tr>
  </table>
  <ol>
    <li><strong>Google Kalender:</strong> Weitere Kalender <code>+</code> &rarr;
        Per URL &rarr; Adresse einfügen &rarr; Kalender hinzufügen</li>
    <li><strong>Outlook im Web</strong> (outlook.com / Microsoft&nbsp;365):
        Kalender &rarr; <em>Kalender hinzuf&uuml;gen</em> &rarr;
        <em>Aus dem Internet abonnieren</em> &rarr; Adresse einf&uuml;gen,
        Namen vergeben, <em>Importieren</em>.</li>
    <li><strong>Outlook am Handy:</strong> Die App kann keine Adresse
        abonnieren. Einmal im Web abonnieren (siehe oben) &ndash; der
        Kalender erscheint dann von selbst in der App unter demselben Konto.
        Sichtbar schalten unter Einstellungen &rarr; Kalender.</li>
    <li><strong>Apple Kalender:</strong> Ablage &rarr; <em>Neues
        Kalenderabo&hellip;</em> &rarr; Adresse einf&uuml;gen.
        Nicht &bdquo;Importieren&ldquo; verwenden.</li>
  </ol>

  <footer>
    Daten von <a href="$quelle_url" target="_blank"
    rel="noopener noreferrer">$quelle_name</a> und
    <a href="$quelle2_url" target="_blank"
    rel="noopener noreferrer">$quelle2_name</a>. Wöchentlich automatisch
    aktualisiert.
  </footer>
</div>
</body>
</html>
""")


def build_index(data):
    ev = data["events"]
    zahl = lambda f: sum(1 for e in ev if f(e))
    return INDEX.substitute(
        n_alle=len(ev),
        n_it=zahl(lambda e: e["country"] == "it"),
        n_at=zahl(lambda e: e["country"] == "at"),
        n_fr=zahl(lambda e: e["country"] == "fr"),
        n_ch=zahl(lambda e: e["country"] == "ch"),
        n_flach=zahl(lambda e: e.get("flach")),
        quelle_url=QUELLE_URL, quelle_name=QUELLE_NAME,
        quelle2_url=QUELLE2_URL, quelle2_name=QUELLE2_NAME,
        season=data["season"], total=len(data["events"]),
        stand=data["fetchedAt"], pages=PAGES_BASE,
    )


def main():
    if not os.path.exists(IN_PATH):
        print("FEHLER: %s fehlt - erst fetch_events.py laufen lassen." % IN_PATH,
              file=sys.stderr)
        return 1

    with open(IN_PATH, encoding="utf-8") as fh:
        data = json.load(fh)

    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        fh.write(build_html(data))

    index_path = os.path.join(BASE, "docs", "index.html")
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    with open(index_path, "w", encoding="utf-8") as fh:
        fh.write(build_index(data))
    print("geschrieben: %s" % index_path)

    heute = date.today().isoformat()
    kommend = sum(1 for e in data["events"] if e["dateStart"] and e["dateStart"] >= heute)
    print("geschrieben: %s" % OUT_PATH)
    print("  kommend: %d | vergangen: %d" % (kommend, len(data["events"]) - kommend))
    return 0


if __name__ == "__main__":
    sys.exit(main())
