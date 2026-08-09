#!/usr/bin/env python3
"""Erzeugt data/artifact.html aus data/events.json.

Siehe SPEC.md "HTML-Artifact - Darstellung".

Wichtig: Das Artifact-Tool wrappt die Datei in <!doctype>/<head>/<body>.
Hier also KEINE dieser Tags - nur Seiteninhalt. Und nichts Externes laden,
die Artifact-CSP blockiert jeden fremden Host (Fonts, Skripte, Bilder).
"""

import json
import os
import sys
from datetime import date
from string import Template

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN_PATH = os.path.join(BASE, "data", "events.json")
OUT_PATH = os.path.join(BASE, "data", "artifact.html")

PAGES_BASE = "https://nikitaberzin.github.io/autofrei"

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

    if ev.get("url"):
        titel = ('<a class="n" href="%s" target="_blank" rel="noopener noreferrer">'
                 "%s</a>" % (esc(ev["url"]), name))
    else:
        titel = '<span class="n">%s</span>' % name

    neu = '<span class="neu">neu</span>' if ev.get("isNew") else ""

    return (
        '<li class="ev" data-c="%s">'
        '<div class="d"><span class="wd">%s</span>'
        '<span class="dm">%s</span></div>'
        '<div class="b">%s<div class="m">'
        '<span class="c c-%s">%s</span>%s</div></div>'
        "</li>"
    ) % (land, wd, esc(datum_in_gruppe(ev, gruppen_monat)), titel, land,
         esc(LAND_NAME.get(land, land)), neu)


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


PAGE = Template("""<title>Autofreie Bike-Tage $season</title>
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

.fil { display:flex; flex-wrap:wrap; gap:.4rem; margin-bottom:1.6rem; }
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
    <h1>Autofreie Bike-Tage $season</h1>
    <p class="sub">$total Termine &middot; Stand $stand &middot; Quelle
      <a href="https://www.freipass.ch/" target="_blank" rel="noopener noreferrer">freipass.ch</a>
    </p>
  </header>

  $next_block

  <nav class="fil" id="fil" aria-label="Nach Land filtern">
    $filter_buttons
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
  var fil = document.getElementById('fil');
  var empty = document.getElementById('empty');

  fil.addEventListener('click', function (e) {
    var btn = e.target.closest('button');
    if (!btn) { return; }
    var land = btn.dataset.land;

    fil.querySelectorAll('button').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b === btn));
    });

    document.querySelectorAll('.ev').forEach(function (ev) {
      ev.classList.toggle('hide', land !== 'all' && ev.dataset.c !== land);
    });

    // Monatsgruppen ohne sichtbare Eintraege ausblenden.
    document.querySelectorAll('.mo').forEach(function (mo) {
      var sichtbar = mo.querySelectorAll('.ev:not(.hide)').length;
      mo.classList.toggle('hide', sichtbar === 0);
      var n = mo.querySelector('.mo-n');
      if (n) { n.textContent = sichtbar; }
    });

    var offen = document.querySelectorAll('#upcoming .ev:not(.hide)').length;
    empty.classList.toggle('hide', offen > 0);
  });

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
        if n.get("url"):
            titel = ('<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>'
                     % (esc(n["url"]), esc(n["name"])))
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
               "Alle %d</button>" % len(kommend)]
    for code in ("it", "at", "fr", "ch"):
        if zaehler.get(code):
            knoepfe.append(
                '<button type="button" data-land="%s" aria-pressed="false">'
                "%s %d</button>" % (code, LAND_NAME[code], zaehler[code])
            )

    # --- Vergangene: eingeklappt, sonst waeren 3/4 der Seite Altlast ---
    if vergangen:
        past_block = (
            '<details class="past"><summary>%d vergangene Termine %s anzeigen'
            "</summary>%s</details>"
        ) % (len(vergangen), data["season"], render_gruppen(gruppiere_nach_monat(vergangen)))
    else:
        past_block = ""

    return PAGE.substitute(
        season=data["season"],
        total=len(events),
        stand=data["fetchedAt"],
        next_block=next_block,
        filter_buttons="\n    ".join(knoepfe),
        upcoming=render_gruppen(gruppiere_nach_monat(kommend)) or
                 '<p class="empty">Keine kommenden Termine.</p>',
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
    Daten von <a href="https://www.freipass.ch/" target="_blank"
    rel="noopener noreferrer">freipass.ch</a>. Wöchentlich automatisch
    aktualisiert.
  </footer>
</div>
</body>
</html>
""")


def build_index(data):
    return INDEX.substitute(
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
