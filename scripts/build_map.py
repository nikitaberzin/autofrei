#!/usr/bin/env python3
"""Erzeugt docs/karte.html und docs/autofrei.geojson aus data/events.json.

Siehe SPEC.md "Karten-Seite" und "GeoJSON-Export".

Zwei Stolperfallen, die hier bewusst kommentiert sind:
  1. Esri-Tiles brauchen {z}/{y}/{x} - NICHT {z}/{x}/{y}. Falsch herum bleibt
     die Karte leer.
  2. GeoJSON erwartet [lng, lat] - Leaflet dagegen [lat, lng]. Vertauscht
     landen alle Pins im Indischen Ozean.
"""

import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN_PATH = os.path.join(BASE, "data", "events.json")
OUT_HTML = os.path.join(BASE, "docs", "karte.html")
OUT_GEOJSON = os.path.join(BASE, "docs", "autofrei.geojson")

LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
LEAFLET_JS_SRI = "sha384-cxOPjt7s7Iz04uaHJceBmS+qpjv2JkIHNVcuOrM+YHwZOmJGBXI00mdUXEq65HTH"
LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
LEAFLET_CSS_SRI = "sha384-sHL9NAb7lN7rfvG5lfHpm643Xkcjzp4jFvuavGOndn6pjVqS6ny56CAt3nsEVT4H"

LAND_NAME = {"it": "Italien", "at": "Österreich", "fr": "Frankreich", "ch": "Schweiz"}
# Oesterreich bewusst NICHT flaggenrot: neben dem Schweizer Rot waeren die
# Marker auf der Karte nicht unterscheidbar (Punkte tragen kein Label).
# Vier klar trennbare Farbtoene schlagen hier Flaggentreue.
LAND_FARBE = {"it": "#009246", "at": "#e07b00", "fr": "#0055a4", "ch": "#d52b1e"}


def sichere_url(url):
    """Nur http/https durchlassen.

    Die URLs stammen aus fremdem HTML. Ungeprueft landet z. B.
    "javascript:..." in einem href im Popup und wird beim Klick
    ausgefuehrt. Alles andere wird verworfen - der Marker bleibt,
    nur ohne Link.
    """
    if not url:
        return None
    u = url.strip()
    return u if u[:7].lower() == "http://" or u[:8].lower() == "https://" else None


def build_geojson(events):
    """FeatureCollection, nur Events MIT Koordinaten. Reihenfolge [lng, lat]."""
    features = []
    for ev in events:
        if ev.get("lat") is None or ev.get("lng") is None:
            continue
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                # ACHTUNG: GeoJSON = [lng, lat], nicht [lat, lng].
                "coordinates": [ev["lng"], ev["lat"]],
            },
            "properties": {
                "name": ev["name"],
                "country": ev["country"],
                "date": ev["dateStart"],
                "dateEnd": ev["dateEnd"],
                "dateRaw": ev["dateRaw"],
                "url": ev["url"],
                "isNew": ev["isNew"],
            },
        })
    return {"type": "FeatureCollection", "features": features}


def js_json(obj):
    """JSON fuer die Einbettung in <script>. Schliesst </script> aus."""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def build_html(data):
    events = data["events"]
    mit_koord = [e for e in events if e.get("lat") is not None]
    ohne_koord = [e for e in events if e.get("lat") is None]

    ohne_liste = ""
    if ohne_koord:
        eintraege = "\n".join(
            "      <li>%s &middot; %s (%s)</li>"
            % (e["dateRaw"], e["name"], LAND_NAME.get(e["country"], e["country"]))
            for e in ohne_koord
        )
        ohne_liste = (
            '    <section class="ohne">\n'
            "      <h2>Ohne Koordinaten (%d)</h2>\n"
            "      <ul>\n%s\n      </ul>\n"
            "    </section>\n" % (len(ohne_koord), eintraege)
        )

    payload = {
        "events": [
            {
                "name": e["name"],
                "country": e["country"],
                "date": e["dateStart"],
                "dateRaw": e["dateRaw"],
                "url": sichere_url(e["url"]),
                "isNew": e["isNew"],
                "lat": e["lat"],
                "lng": e["lng"],
            }
            for e in mit_koord
        ],
        "landName": LAND_NAME,
        "landFarbe": LAND_FARBE,
    }

    return """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Autofreie Bike-Tage %(season)s &ndash; Karte</title>
<link rel="stylesheet" href="%(leaflet_css)s"
      integrity="%(leaflet_css_sri)s" crossorigin="anonymous">
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #fff; color: #1a1a1a;
  }
  header { padding: 1rem 1.25rem .75rem; }
  h1 { margin: 0 0 .25rem; font-size: 1.25rem; }
  .meta { color: #666; font-size: .85rem; }
  .meta a { color: #06c; }
  #map { height: 70vh; width: 100%%; }
  @media (min-width: 768px) { #map { height: 85vh; } }
  .ohne { padding: 1rem 1.25rem; }
  .ohne h2 { font-size: 1rem; }
  .ohne ul { padding-left: 1.1rem; color: #444; }
  footer { padding: 1rem 1.25rem 2rem; font-size: .85rem; color: #666; }
  footer a { color: #06c; }
  .pop b { display: block; font-size: 1rem; margin-bottom: .15rem; }
  .pop .d { color: #555; }
  .pop .neu {
    display: inline-block; margin-left: .3rem; padding: 0 .35rem;
    background: #e8f5e9; color: #1b5e20; border-radius: 3px;
    font-size: .72rem; font-weight: 700; vertical-align: middle;
  }
  @media (prefers-color-scheme: dark) {
    body { background: #16181c; color: #e8e8e8; }
    .meta, .ohne ul, footer { color: #9aa; }
    .pop .d { color: #555; }
  }
</style>
</head>
<body>
<header>
  <h1>&#128690; Autofreie Bike-Tage %(season)s</h1>
  <p class="meta">
    %(count)d Orte &middot; Stand %(stand)s &middot;
    Quelle <a href="https://www.freipass.ch/" target="_blank" rel="noopener noreferrer">freipass.ch</a>
  </p>
</header>

<div id="map"></div>

%(ohne_liste)s
<footer>
  <a href="index.html">&larr; Übersicht &amp; Kalender-Abo</a> &middot;
  <a href="autofrei.geojson" download>GeoJSON herunterladen</a> (für ArcGIS Online)
</footer>

<script src="%(leaflet_js)s"
        integrity="%(leaflet_js_sri)s" crossorigin="anonymous"></script>
<script>
(function () {
  var DATA = %(payload)s;

  // Startausschnitt sofort setzen: schlaegt das spaetere fitBounds fehl,
  // sieht der Nutzer trotzdem den Alpenraum statt eines Maximalzooms.
  var map = L.map('map', { scrollWheelZoom: true }).setView([46.3, 8.5], 6);

  // ACHTUNG: Esri nutzt {z}/{y}/{x}. Mit {z}/{x}/{y} bleibt die Karte leer.
  var esri = 'https://services.arcgisonline.com/ArcGIS/rest/services/';
  var topo = L.tileLayer(esri + 'World_Topo_Map/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 17, attribution: 'Tiles &copy; Esri'
  });
  var sat = L.tileLayer(esri + 'World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 17, attribution: 'Tiles &copy; Esri'
  });
  topo.addTo(map);

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;',
               '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  var gruppen = {};
  var alle = [];

  DATA.events.forEach(function (ev) {
    var farbe = DATA.landFarbe[ev.country] || '#666';
    var m = L.circleMarker([ev.lat, ev.lng], {
      radius: 7, color: '#fff', weight: 2,
      fillColor: farbe, fillOpacity: .9
    });

    var html = '<div class="pop"><b>' + esc(ev.name) + '</b>' +
      '<span class="d">' + esc(ev.dateRaw) + ' &middot; ' +
      esc(DATA.landName[ev.country] || ev.country) + '</span>' +
      (ev.isNew ? '<span class="neu">NEU</span>' : '');
    if (ev.url) {
      html += '<br><a href="' + esc(ev.url) +
              '" target="_blank" rel="noopener noreferrer">Details &rarr;</a>';
    }
    m.bindPopup(html + '</div>');

    if (!gruppen[ev.country]) { gruppen[ev.country] = L.layerGroup(); }
    gruppen[ev.country].addLayer(m);
    alle.push([ev.lat, ev.lng]);
  });

  var overlays = {};
  Object.keys(gruppen).forEach(function (c) {
    gruppen[c].addTo(map);
    var label = '<span style="color:' + DATA.landFarbe[c] + '">&#9679;</span> ' +
                (DATA.landName[c] || c) +
                ' (' + gruppen[c].getLayers().length + ')';
    overlays[label] = gruppen[c];
  });

  L.control.layers(
    { 'Topografisch': topo, 'Satellit': sat }, overlays, { collapsed: false }
  ).addTo(map);

  // Hat der Container beim Init noch keine Hoehe (langsames Layout, Vorschau-
  // Pane das erst nachtraeglich aufgeht, Hintergrund-Tab), liefert Leaflets
  // getBoundsZoom maxZoom zurueck - die Karte klebt dann auf Zoom 17.
  // Deshalb nach Layout-Aenderungen erneut einpassen, aber nur solange der
  // Nutzer die Karte noch nicht selbst bewegt hat.
  var bounds = alle.length ? L.latLngBounds(alle) : null;
  var nutzerHatBewegt = false;

  ['mousedown', 'touchstart', 'wheel', 'dblclick'].forEach(function (typ) {
    map.getContainer().addEventListener(typ, function () {
      nutzerHatBewegt = true;
    }, { passive: true });
  });
  document.querySelector('.leaflet-control-zoom')
    ?.addEventListener('click', function () { nutzerHatBewegt = true; });

  function einpassen() {
    map.invalidateSize({ animate: false });
    if (bounds) { map.fitBounds(bounds, { padding: [30, 30] }); }
    else { map.setView([46.5, 10.5], 6); }
  }

  einpassen();
  window.addEventListener('load', function () {
    if (!nutzerHatBewegt) { einpassen(); }
  });

  // ResizeObserver statt window.resize: er feuert auch, wenn der Container
  // seine Groesse aendert, ohne dass das Fenster ein resize-Event schickt
  // (Vorschau-Pane, das erst aufgeht; vh-Aenderung durch Browser-Chrome;
  // Tab, der aus dem Hintergrund kommt). Genau dieser Fall liess die Karte
  // auf Zoom 17 haengen.
  var timer;
  function nachziehen() {
    clearTimeout(timer);
    timer = setTimeout(function () {
      if (!nutzerHatBewegt) { einpassen(); }
      else { map.invalidateSize({ animate: false }); }
    }, 120);
  }

  if (window.ResizeObserver) {
    new ResizeObserver(nachziehen).observe(map.getContainer());
  }
  window.addEventListener('resize', nachziehen);
})();
</script>
</body>
</html>
""" % {
        "season": data["season"],
        "count": len(mit_koord),
        "stand": data["fetchedAt"],
        "ohne_liste": ohne_liste,
        "leaflet_css": LEAFLET_CSS,
        "leaflet_css_sri": LEAFLET_CSS_SRI,
        "leaflet_js": LEAFLET_JS,
        "leaflet_js_sri": LEAFLET_JS_SRI,
        "payload": js_json(payload),
    }


def main():
    if not os.path.exists(IN_PATH):
        print("FEHLER: %s fehlt - erst fetch_events.py laufen lassen." % IN_PATH,
              file=sys.stderr)
        return 1

    with open(IN_PATH, encoding="utf-8") as fh:
        data = json.load(fh)

    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)

    gj = build_geojson(data["events"])
    with open(OUT_GEOJSON, "w", encoding="utf-8") as fh:
        json.dump(gj, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    with open(OUT_HTML, "w", encoding="utf-8") as fh:
        fh.write(build_html(data))

    print("geschrieben: %s" % OUT_GEOJSON)
    print("  Features: %d (von %d Events)" % (len(gj["features"]), len(data["events"])))
    print("geschrieben: %s" % OUT_HTML)
    return 0


if __name__ == "__main__":
    sys.exit(main())
