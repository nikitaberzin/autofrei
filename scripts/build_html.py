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
        '<li class="ev" data-c="%s" data-f="%s" data-y="%s">'
        '<div class="d"><span class="wd">%s</span>'
        '<span class="dm">%s</span></div>'
        '<div class="b">%s<div class="m">'
        '<span class="c c-%s">%s</span>%s%s</div></div>'
        "</li>"
    ) % (land, "1" if ev.get("flach") else "0",
         (ev["dateStart"] or "")[:4], wd,
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
            '<circle class="pt %s%s" data-c="%s" data-f="%s" data-y="%s" cx="%.1f" cy="%.1f" r="%s">'
            "<title>%s</title></circle>"
            % ("kommend" if kommend else "vorbei",
               " su" if e.get("flach") else "",
               e["country"], "1" if e.get("flach") else "0",
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
  --r:10px;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg:#0f1514; --surface:#18211f; --ink:#e7edec; --ink2:#8fa39f;
    --line:#26322f; --accent:#4fd1c7; --accent-soft:#123230; --accent-ink:#7fe3db;
    --it:#2bb673; --at:#f0a03c; --fr:#5f9de8; --ch:#f2594c;
  }
}
:root[data-theme="light"] {
  --bg:#f2f5f4; --surface:#ffffff; --ink:#16211f; --ink2:#5d6f6c;
  --line:#dde4e3; --accent:#0e6e6b; --accent-soft:#e0efee; --accent-ink:#0a5350;
  --it:#00803f; --at:#c96a00; --fr:#0055a4; --ch:#c8241a;
}
:root[data-theme="dark"] {
  --bg:#0f1514; --surface:#18211f; --ink:#e7edec; --ink2:#8fa39f;
  --line:#26322f; --accent:#4fd1c7; --accent-soft:#123230; --accent-ink:#7fe3db;
  --it:#2bb673; --at:#f0a03c; --fr:#5f9de8; --ch:#f2594c;
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
  display:grid; grid-template-columns:3.7rem 1fr; gap:.15rem .8rem;
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
  .ev { grid-template-columns:1fr; gap:.15rem; padding:.55rem .5rem; }
  .d { flex-direction:row; gap:.45rem; align-items:baseline; }
}
/* Touch-Ziele >= 44px. pointer:coarse trifft Finger-Bedienung, nicht bloss
   schmale Fenster - ein kleines Desktop-Fenster braucht das nicht. */
@media (pointer: coarse) {
  .fil button { min-height:44px; padding:.6rem .9rem; }
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

  <main id="upcoming">
    $upcoming
  </main>

  <p class="empty hide" id="empty">Keine Termine für diese Auswahl.</p>

  $past_block

  <footer class="ft">
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

<script>
(function () {
  var empty = document.getElementById('empty');
  var alleEv = [].slice.call(document.querySelectorAll('.ev'));

  // Drei unabhaengige Filter, gleichzeitig angewendet:
  // "Schweiz + flach + 2026" muss moeglich sein.
  var f = { land: 'all', ter: 'all', jahr: '$default_jahr' };

  function trifftZu(el, ausser) {
    return (ausser === 'land' || f.land === 'all' || el.dataset.c === f.land)
        && (ausser === 'ter'  || f.ter === 'all'
            || (f.ter === 'flach' ? el.dataset.f === '1' : el.dataset.f !== '1'))
        && (ausser === 'jahr' || f.jahr === 'all' || el.dataset.y === f.jahr);
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
    empty.classList.toggle('hide', offen > 0);
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
  <p style="font-size:.92rem">Der Kalender aktualisiert sich danach
     automatisch &ndash; neue Termine erscheinen von selbst.</p>
  <span class="url">$pages/autofrei.ics</span>
  <ol>
    <li><strong>Google Kalender:</strong> Weitere Kalender <code>+</code> &rarr;
        Per URL &rarr; Adresse einfügen &rarr; Kalender hinzufügen</li>
    <li><strong>Outlook:</strong> Kalender hinzufügen &rarr; Aus dem Internet
        abonnieren &rarr; Adresse einfügen</li>
    <li><strong>Apple Kalender:</strong> Ablage &rarr; Neues Kalenderabo &rarr;
        Adresse einfügen</li>
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
    return INDEX.substitute(
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
