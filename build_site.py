"""Build the static rijexamenwachttijden.nl site from data/history.csv.

Usage: python3 build_site.py
Output: dist/  (deploy this directory, e.g. via Cloudflare Pages)
"""

import csv
import re
import unicodedata
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DIST = ROOT / "dist"

EXAM_META = {
    "wanneer-praktijkexamen": {
        "label": "Praktijkexamen", "short": "praktijkexamen",
        "vraag": "Vanaf hoeveel weken kan ik praktijkexamen doen?",
        "unit_note": "aantal weken tot een beschikbare examenplek",
    },
    "wanneer-herexamen": {
        "label": "Herexamen", "short": "herexamen",
        "vraag": "Vanaf hoeveel weken kan ik herexamen doen?",
        "unit_note": "aantal weken tot een beschikbare examenplek (let op: pas vanaf de 14e dag na je vorige examen)",
    },
    "wanneer-theorie-examen": {
        "label": "Theorie-examen", "short": "theorie-examen",
        "vraag": "Vanaf hoeveel weken kan ik theorie-examen doen?",
        "unit_note": "aantal weken tot een beschikbare examenplek",
    },
}
EXAM_ORDER = ["wanneer-praktijkexamen", "wanneer-herexamen", "wanneer-theorie-examen"]


def slugify(name):
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    n = re.sub(r"[^a-zA-Z0-9]+", "-", n).strip("-").lower()
    return n


def weeks_sort_key(w):
    """For sorting: ranges like '1-4' sort by their low end."""
    if isinstance(w, str) and "-" in w:
        return int(w.split("-")[0])
    try:
        return int(w)
    except (TypeError, ValueError):
        return 999


def urgency_class(w):
    """Thresholds calibrated to observed data: most locations sit at 6-7 weeks
    (the current norm for praktijkexamen), so that range reads as 'gemiddeld',
    not alarm. Orange is reserved for genuine outliers (8+)."""
    lo = weeks_sort_key(w)
    if lo <= 4:
        return "kort"
    if lo <= 7:
        return "gemiddeld"
    return "lang"


def load_history():
    """Returns: locations[loc_slug] = {
         name, province,
         series[slug] = [(iso_week, cover_week, cover_period, weeks), ...] sorted
       }
       Also returns latest_by_exam[slug][loc_slug] = weeks (most recent iso_week)
    """
    locations = {}
    with (DATA / "history.csv").open(newline="") as f:
        for row in csv.DictReader(f):
            loc = row["location"]
            lslug = slugify(loc)
            entry = locations.setdefault(lslug, {
                "name": loc, "province": row["province"], "series": defaultdict(list)
            })
            entry["series"][row["publication"]].append((
                row["iso_week"], row["cover_week"], row["cover_period"], row["weeks"]
            ))

    for entry in locations.values():
        for slug in entry["series"]:
            entry["series"][slug].sort(key=lambda r: r[0])

    latest_by_exam = defaultdict(dict)
    for lslug, entry in locations.items():
        for slug, series in entry["series"].items():
            latest_by_exam[slug][lslug] = series[-1][3]  # weeks value

    return locations, latest_by_exam


# ---------------------------------------------------------------- templates

CSS = """
:root{
  --groen:#00563F; --groen-licht:#3B7A57; --oranje:#E85D2F;
  --bg:#F5F2EA; --inkt:#1A1A1A; --lijn:#DDD8C7; --wit:#FFFDF8;
  --mono: 'IBM Plex Mono', ui-monospace, monospace;
  --sans: 'IBM Plex Sans', -apple-system, sans-serif;
  --display: 'Fraunces', Georgia, serif;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--inkt);font-family:var(--sans);
  line-height:1.5;-webkit-font-smoothing:antialiased}
a{color:var(--groen);text-decoration-thickness:1px}
.wrap{max-width:960px;margin:0 auto;padding:0 20px}
header.top{border-bottom:2px solid var(--inkt);padding:18px 0}
header.top .wrap{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap}
.logo{font-family:var(--display);font-weight:600;font-size:1.4rem;letter-spacing:-0.01em;color:var(--inkt);text-decoration:none}
.logo span{color:var(--groen)}
nav a{margin-left:18px;font-size:0.92rem;font-weight:500;color:var(--inkt);text-decoration:none;border-bottom:2px solid transparent}
nav a:hover{border-color:var(--oranje)}
main{padding:36px 0 80px}
h1{font-family:var(--display);font-size:2.1rem;font-weight:600;line-height:1.15;margin:0 0 8px;letter-spacing:-0.01em}
h2{font-family:var(--display);font-size:1.5rem;font-weight:600;margin:2.4em 0 0.6em}
.lead{font-size:1.05rem;color:#4a4a42;max-width:60ch;margin:0 0 28px}
.notice{background:var(--wit);border:1px solid var(--lijn);border-left:4px solid var(--oranje);
  padding:14px 18px;border-radius:2px;font-size:0.94rem;margin:0 0 32px}
.notice strong{color:var(--oranje)}

.search-bar{margin:0 0 20px}
.search-bar input{width:100%;max-width:360px;padding:10px 14px;border:2px solid var(--inkt);
  border-radius:4px;font-family:var(--sans);font-size:1rem;background:var(--wit)}
.search-bar input:focus{outline:none;border-color:var(--groen)}
.search-empty{margin:14px 0 0;color:#6b6b60;font-size:0.9rem}

/* wachttijdbord: signature badge */
.bord{display:inline-flex;flex-direction:column;align-items:center;justify-content:center;
  background:var(--wit);border:3px solid var(--inkt);border-radius:10px;
  min-width:92px;padding:10px 14px;font-family:var(--mono)}
.bord .n{font-family:var(--display);font-size:2.3rem;font-weight:600;line-height:1;color:var(--groen)}
.bord.lang .n{color:var(--oranje)}
.bord .u{font-size:0.68rem;letter-spacing:0.04em;color:#6b6b60;margin-top:2px}

/* homepage grid */
.provincies{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px;margin:20px 0 40px}
.provincie{background:var(--wit);border:1px solid var(--lijn);border-radius:6px;padding:16px 18px}
.provincie h3{font-family:var(--display);font-size:1.05rem;margin:0 0 10px;font-weight:600}
.loc-row{display:flex;justify-content:space-between;align-items:center;padding:6px 0;
  border-top:1px solid var(--lijn);font-size:0.92rem}
.loc-row:first-of-type{border-top:none}
.loc-row a{color:var(--inkt);text-decoration:none}
.loc-row a:hover{color:var(--groen);text-decoration:underline}
.pill{font-family:var(--mono);font-size:0.82rem;font-weight:600;padding:2px 8px;border-radius:20px;white-space:nowrap}
.pill.kort{background:#DCEEE3;color:var(--groen-licht)}
.pill.gemiddeld{background:#EFE9D8;color:#8a7a3d}
.pill.lang{background:#FBE4D9;color:var(--oranje)}

/* location page */
.hero{display:flex;gap:28px;align-items:center;flex-wrap:wrap;margin-bottom:8px}
.hero .bord{padding:16px 24px}
.hero .bord .n{font-size:2.8rem}
.exam-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;margin:24px 0 8px}
.exam-card{background:var(--wit);border:1px solid var(--lijn);border-radius:6px;padding:18px 20px}
.exam-card h3{font-family:var(--sans);font-size:0.95rem;font-weight:600;margin:0 0 12px;color:#4a4a42}
.exam-card .bord{width:100%;flex-direction:row;justify-content:space-between;padding:10px 16px}
.exam-card .bord .n{font-size:1.8rem}
.history-table{width:100%;border-collapse:collapse;font-size:0.9rem;margin:8px 0 0}
.history-table th,.history-table td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--lijn);font-family:var(--mono)}
.ranking-table td:first-child{color:#6b6b60;width:32px}
.history-table th{color:#6b6b60;font-weight:600;font-size:0.8rem}
.crumbs{font-size:0.85rem;margin-bottom:18px}
.crumbs a{color:#6b6b60}
footer{border-top:1px solid var(--lijn);padding:28px 0;font-size:0.85rem;color:#6b6b60}
footer a{color:#6b6b60}
.source-note{font-size:0.85rem;color:#6b6b60;margin-top:6px}

.alert-signup{background:var(--wit);border:1px solid var(--lijn);border-radius:6px;padding:16px 18px;margin:20px 0}
.alert-signup h2{font-size:1.05rem;margin:0 0 6px}
.alert-signup p{margin:0 0 12px;font-size:0.9rem;color:#6b6b60}
.alert-form{display:flex;gap:8px;flex-wrap:wrap}
.alert-form input{flex:1;min-width:180px;padding:8px 10px;border:1px solid var(--lijn);border-radius:4px;font-family:var(--sans)}
.alert-form button{padding:8px 16px;border:1px solid var(--inkt);border-radius:4px;background:var(--inkt);color:var(--wit);cursor:pointer;font-family:var(--sans)}
.alert-form button:hover{background:var(--groen);border-color:var(--groen)}
.alert-status{margin-top:8px;font-size:0.85rem;color:var(--groen)}

/* widgets distribution page */
.widget-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;margin:20px 0}
.widget-row{background:var(--wit);border:1px solid var(--lijn);border-radius:6px;padding:14px 16px}
.widget-row strong{display:block;font-size:0.95rem;margin-bottom:8px}
.embed-code{background:var(--bg);border:1px solid var(--lijn);border-radius:4px;padding:8px 10px;
  font-family:var(--mono);font-size:0.72rem;white-space:pre-wrap;word-break:break-all;margin:0}
@media(max-width:600px){
  h1{font-size:1.6rem}
  .hero{gap:16px}
  .hero .bord .n{font-size:2.1rem}
}
"""

HEAD = """<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:wght@500;600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{root}style.css">
</head>
<body>
<header class="top"><div class="wrap">
  <a class="logo" href="{root}index.html">rijexamen<span>wachttijden</span>.nl</a>
  <nav>
    <a href="{root}index.html">Overzicht</a>
    <a href="{root}kortste-wachttijden.html">Kortste wachttijden</a>
    <a href="{root}over.html">Over dit archief</a>
  </nav>
</div></header>
<main><div class="wrap">
"""

FOOT = """
</div></main>
<footer><div class="wrap">
  Bron: CBR (publiek gepubliceerde wachttijden). Wekelijks gearchiveerd sinds week 27, 2026 &mdash;
  <a href="https://github.com/mansikapahi/cbr-wachttijden-archief" target="_blank" rel="noopener">broncode &amp; ruwe data op GitHub</a>.
  Dit is geen officieel CBR-kanaal.
</div></footer>
</body></html>
"""


def page(title, description, body, root="./"):
    return HEAD.format(title=title, description=description, root=root) + body + FOOT


def bord_html(weeks, size_class="bord"):
    uc = urgency_class(weeks)
    label = "wk" if not (isinstance(weeks, str) and "-" in weeks) else "wk"
    return f'<div class="{size_class} {uc}"><span class="n">{weeks}</span><span class="u">{label}</span></div>'


def sparkline_svg(series, width=140, height=36):
    """series: list of (iso_week, cover_week, cover_period, weeks) -- numeric only."""
    pts = []
    for _, _, _, w in series:
        v = weeks_sort_key(w)
        pts.append(v)
    if len(pts) < 2:
        return ""
    lo, hi = min(pts), max(pts)
    span = max(hi - lo, 1)
    step = width / (len(pts) - 1)
    coords = []
    for i, v in enumerate(pts):
        x = i * step
        y = height - ((v - lo) / span) * (height - 8) - 4
        coords.append(f"{x:.1f},{y:.1f}")
    path = " ".join(coords)
    dots = "".join(
        f'<circle cx="{c.split(",")[0]}" cy="{c.split(",")[1]}" r="2.5" fill="var(--groen)"/>'
        for c in coords
    )
    return (f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            f'role="img" aria-label="Verloop over tijd">'
            f'<polyline points="{path}" fill="none" stroke="var(--groen)" stroke-width="2"/>'
            f'{dots}</svg>')


# ---------------------------------------------------------------- builders

def build_homepage(locations, latest_by_exam, out_dir):
    by_province = defaultdict(list)
    for lslug, entry in locations.items():
        by_province[entry["province"]].append((lslug, entry))
    for locs in by_province.values():
        locs.sort(key=lambda t: t[1]["name"])

    cards = []
    for prov in sorted(by_province):
        rows = []
        for lslug, entry in by_province[prov]:
            w = latest_by_exam.get("wanneer-praktijkexamen", {}).get(lslug)
            if w is None:
                continue
            uc = urgency_class(w)
            rows.append(
                f'<div class="loc-row"><a href="locatie/{lslug}/">{entry["name"]}</a>'
                f'<span class="pill {uc}">{w} wk</span></div>'
            )
        cards.append(f'<div class="provincie"><h3>{prov}</h3>{"".join(rows)}</div>')

    body = f"""
<h1>Wachttijden CBR-examens per locatie</h1>
<p class="lead">Actuele en historische wachttijden voor praktijkexamen, herexamen en
theorie-examen &mdash; per examenlocatie. CBR toont alleen de huidige week; wij archiveren
elke week, zodat je het verloop kunt zien.</p>

<div class="notice">
<strong>Let op:</strong> CBR publiceerde tussen week 27 en week 28 (2026) geen nieuwe
wachttijden &mdash; een pauze van twee weken tijdens het examenseizoen. Zie
<a href="over.html">over dit archief</a> voor details.
</div>

<div class="search-bar">
  <input type="text" id="loc-search" placeholder="Zoek je plaats&hellip;" autocomplete="off">
  <p id="search-empty" class="search-empty" hidden>Geen locaties gevonden.</p>
</div>

<h2>Praktijkexamen &mdash; per provincie</h2>
<div class="provincies" id="provincies">{"".join(cards)}</div>

<script>
(function() {{
  var input = document.getElementById('loc-search');
  var empty = document.getElementById('search-empty');
  var provincies = document.querySelectorAll('#provincies .provincie');

  input.addEventListener('input', function() {{
    var q = input.value.trim().toLowerCase();
    var anyVisible = false;

    provincies.forEach(function(prov) {{
      var rows = prov.querySelectorAll('.loc-row');
      var provHasMatch = false;

      rows.forEach(function(row) {{
        var name = row.querySelector('a').textContent.toLowerCase();
        var match = q === '' || name.indexOf(q) !== -1;
        row.hidden = !match;
        if (match) provHasMatch = true;
      }});

      prov.hidden = !provHasMatch;
      if (provHasMatch) anyVisible = true;
    }});

    empty.hidden = anyVisible || q === '';
  }});
}})();
</script>
"""
    (out_dir / "index.html").write_text(
        page("Wachttijden CBR-examens per locatie | rijexamenwachttijden.nl",
             "Actuele en historische wachttijden voor CBR praktijkexamen, herexamen en "
             "theorie-examen per locatie in Nederland.", body))


def build_location_page(lslug, entry, out_dir):
    prov = entry["province"]
    exam_cards = []
    history_sections = []
    for slug in EXAM_ORDER:
        series = entry["series"].get(slug)
        if not series:
            continue
        meta = EXAM_META[slug]
        latest = series[-1]
        weeks = latest[3]
        spark = sparkline_svg(series)
        uc = urgency_class(weeks)
        exam_cards.append(f"""
<div class="exam-card">
  <h3>{meta['label']}</h3>
  <div class="bord {uc}"><span class="n">{weeks}</span><span class="u">wk</span></div>
  {spark}
</div>""")

        rows = "".join(
            f"<tr><td>{iso}</td><td>{cw}</td><td>{cp}</td><td>{w}</td></tr>"
            for iso, cw, cp, w in series
        )
        history_sections.append(f"""
<h2>{meta['label']} &mdash; geschiedenis</h2>
<table class="history-table">
<tr><th>Gearchiveerd (iso-week)</th><th>CBR-week</th><th>Periode</th><th>Weken</th></tr>
{rows}
</table>""")

    current_praktijk = entry["series"].get("wanneer-praktijkexamen", [(None, None, None, "?")])[-1][3]

    # Build a unique meta description from this location's actual current
    # weeks-values, rather than a boilerplate sentence repeated on every page.
    weeks_by_slug = {}
    for slug in EXAM_ORDER:
        series = entry["series"].get(slug)
        if series:
            weeks_by_slug[slug] = series[-1][3]

    desc_parts = [f"Praktijkexamen in {entry['name']}: {weeks_by_slug.get('wanneer-praktijkexamen', '?')} weken wachttijd."]
    extras = []
    if "wanneer-herexamen" in weeks_by_slug:
        extras.append(f"herexamen {weeks_by_slug['wanneer-herexamen']} wk")
    if "wanneer-theorie-examen" in weeks_by_slug:
        extras.append(f"theorie-examen {weeks_by_slug['wanneer-theorie-examen']} wk")
    if extras:
        desc_parts.append(f"Ook bekend: {', '.join(extras)}.")
    desc_parts.append(f"Wekelijks gearchiveerd sinds week 27, 2026 &mdash; {prov}.")
    location_description = " ".join(desc_parts)

    body = f"""
<p class="crumbs"><a href="../../index.html">Overzicht</a> &rsaquo; {prov} &rsaquo; {entry['name']}</p>
<h1>Wachttijden examens in {entry['name']}</h1>
<p class="lead">{prov} &middot; actuele wachttijd voor praktijkexamen: <strong>{current_praktijk} weken</strong>.
Hieronder het verloop per examentype sinds het begin van dit archief.</p>

<div class="exam-grid">{"".join(exam_cards)}</div>

<div class="alert-signup">
  <h2>Alert bij verandering</h2>
  <p>Krijg een e-mail zodra de wachttijd voor {entry['name']} verandert.</p>
  <form class="alert-form" data-location="{lslug}">
    <input type="email" name="email" placeholder="jouw@email.nl" required>
    <button type="submit">Meld me aan</button>
  </form>
  <p class="alert-status" hidden></p>
</div>

{"".join(history_sections)}

<p class="source-note">Bron: CBR, wekelijks gearchiveerd. Definitie: aantal weken tot
er voldoende examenplekken beschikbaar zijn (CBR's eigen definitie).</p>

<script>
document.querySelectorAll('.alert-form').forEach(function(form) {{
  form.addEventListener('submit', async function(e) {{
    e.preventDefault();
    var status = form.nextElementSibling;
    var email = form.email.value;
    var location = form.dataset.location;
    form.querySelector('button').disabled = true;
    try {{
      var res = await fetch('/api/subscribe', {{
        method: 'POST',
        headers: {{'content-type': 'application/json'}},
        body: JSON.stringify({{email: email, location: location}})
      }});
      status.hidden = false;
      if (res.ok) {{
        status.textContent = 'Check je inbox om je aanmelding te bevestigen.';
        form.reset();
      }} else {{
        status.textContent = 'Er ging iets mis, probeer het later opnieuw.';
      }}
    }} catch (err) {{
      status.hidden = false;
      status.textContent = 'Er ging iets mis, probeer het later opnieuw.';
    }}
    form.querySelector('button').disabled = false;
  }});
}});
</script>
"""
    d = out_dir / "locatie" / lslug
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(
        page(f"Wachttijd examens {entry['name']} | rijexamenwachttijden.nl",
             location_description, body, root="../../"))


def build_widget(lslug, entry, out_dir):
    """A small, self-contained page meant to be loaded in an <iframe> on a
    rijschool's own site. Deliberately noindexed: it's a near-duplicate of
    the full location page, and its job is distribution/backlinks, not to
    rank in search itself."""
    prov = entry["province"]
    current = entry["series"].get("wanneer-praktijkexamen", [(None, None, None, "?")])[-1][3]
    uc = urgency_class(current)
    latest_iso = entry["series"].get("wanneer-praktijkexamen", [(None,)])[-1][0]

    html = f"""<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Wachttijd {entry['name']} widget</title>
<style>
:root{{--groen:#00563F;--oranje:#E85D2F;--inkt:#1A1A1A;--lijn:#DDD8C7;--wit:#FFFDF8;
  --mono:'IBM Plex Mono',ui-monospace,monospace;--sans:'IBM Plex Sans',-apple-system,sans-serif;
  --display:'Fraunces',Georgia,serif}}
*{{box-sizing:border-box}}
body{{margin:0;padding:12px;background:var(--wit);color:var(--inkt);font-family:var(--sans)}}
.card{{border:2px solid var(--inkt);border-radius:8px;padding:14px 16px;max-width:260px}}
.loc{{font-family:var(--display);font-weight:600;font-size:1rem;margin:0 0 8px}}
.bord{{display:inline-flex;align-items:baseline;gap:6px;background:var(--wit)}}
.bord .n{{font-family:var(--display);font-size:2rem;font-weight:600;color:var(--groen)}}
.bord.lang .n{{color:var(--oranje)}}
.bord .u{{font-size:0.75rem;color:#6b6b60}}
.sub{{font-size:0.78rem;color:#6b6b60;margin:6px 0 10px}}
a.attr{{display:block;font-size:0.72rem;color:#6b6b60;text-decoration:none;border-top:1px solid var(--lijn);padding-top:8px;margin-top:4px}}
a.attr:hover{{color:var(--groen)}}
</style>
</head>
<body>
<div class="card">
  <p class="loc">{entry['name']}</p>
  <div class="bord {uc}"><span class="n">{current}</span><span class="u">weken<br>wachttijd</span></div>
  <p class="sub">Praktijkexamen &middot; {prov} &middot; stand {latest_iso or ''}</p>
  <a class="attr" href="https://rijexamenwachttijden.nl/locatie/{lslug}/" target="_blank" rel="noopener">
    Bron: rijexamenwachttijden.nl &rarr;
  </a>
</div>
</body>
</html>"""
    d = out_dir / "widget" / lslug
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(html)


def build_widgets_page(locations, out_dir):
    """A distribution page listing every location's copy-paste iframe
    snippet, so rijscholen can grab their own location's embed code."""
    rows = []
    for lslug, entry in sorted(locations.items(), key=lambda t: t[1]["name"]):
        snippet = (
            f'&lt;iframe src="https://rijexamenwachttijden.nl/widget/{lslug}/" '
            f'width="280" height="160" style="border:none"&gt;&lt;/iframe&gt;'
        )
        rows.append(f"""
<div class="widget-row">
  <strong>{entry['name']}</strong>
  <pre class="embed-code">{snippet}</pre>
</div>""")

    body = f"""
<h1>Widget: wachttijd op jouw website</h1>
<p class="lead">Gratis embed voor rijscholen: toon de actuele CBR-wachttijd van jouw
locatie direct op je eigen website. Kopieer de code bij jouw plaats en plak die in
je website-editor (de meeste CMS'en, zoals WordPress, hebben een "HTML-blok" of
"embed"-optie).</p>

<div class="widget-list">{"".join(rows)}</div>

<p class="source-note">De widget toont automatisch de meest recente wachttijd zodra
wij die archiveren &mdash; je hoeft niets bij te werken.</p>
"""
    (out_dir / "widgets.html").write_text(
        page("Widget voor rijscholen | rijexamenwachttijden.nl",
             "Gratis embeddable widget: toon de actuele CBR-wachttijd van jouw "
             "examenlocatie op je eigen rijschool-website.", body))



def build_ranking_page(locations, latest_by_exam, out_dir):
    """Ranks all locations shortest-to-longest wait, per exam type. This is
    the kind of page people screenshot/share/bookmark on its own, and it's a
    natural match for high-intent searches like 'kortste wachttijd rijexamen'."""
    sections = []
    for slug in EXAM_ORDER:
        meta = EXAM_META[slug]
        rows = []
        entries = []
        for lslug, entry in locations.items():
            w = latest_by_exam.get(slug, {}).get(lslug)
            if w is not None:
                entries.append((lslug, entry, w))
        entries.sort(key=lambda t: weeks_sort_key(t[2]))

        for rank, (lslug, entry, w) in enumerate(entries, start=1):
            uc = urgency_class(w)
            rows.append(
                f'<tr><td>{rank}</td>'
                f'<td><a href="locatie/{lslug}/">{entry["name"]}</a></td>'
                f'<td>{entry["province"]}</td>'
                f'<td><span class="pill {uc}">{w} wk</span></td></tr>'
            )
        sections.append(f"""
<h2>{meta['label']} &mdash; kortste wachttijd eerst</h2>
<table class="history-table ranking-table">
<tr><th>#</th><th>Locatie</th><th>Provincie</th><th>Wachttijd</th></tr>
{"".join(rows)}
</table>""")

    body = f"""
<h1>Kortste wachttijden CBR-examens</h1>
<p class="lead">Alle {len(locations)} locaties gerangschikt van kortste naar langste
wachttijd, per examentype. Bijgewerkt bij elke wekelijkse archivering.</p>
{"".join(sections)}
<p class="source-note">Zie ook de <a href="index.html">volledige lijst per provincie</a>
of <a href="over.html">hoe dit archief werkt</a>.</p>
"""
    (out_dir / "kortste-wachttijden.html").write_text(
        page("Kortste wachttijden CBR-examens | rijexamenwachttijden.nl",
             "Alle examenlocaties in Nederland gerangschikt van kortste naar langste "
             "CBR-wachttijd, voor praktijkexamen, herexamen en theorie-examen.", body))


def build_over_page(out_dir):
    body = """
<h1>Over dit archief</h1>
<p class="lead">CBR publiceert elke week de actuele wachttijden per examenlocatie &mdash;
maar overschrijft die data de week erna. Er bestond nergens een geschiedenis. Dit archief
lost dat op: elke maandag wordt de publicatie automatisch opgehaald en bewaard.</p>

<h2>Wat er is gebeurd tussen week 27 en 28</h2>
<p>CBR publiceerde in week 28 (2026) geen nieuwe wachttijden-editie; de publicatie bleef
op "Stand week 27" staan. Dit archief heeft dat gedocumenteerd doordat het elke week
onafhankelijk controleert wat CBR daadwerkelijk publiceert &mdash; iets wat nergens anders
zichtbaar is, omdat CBR's eigen pagina alleen de laatste stand toont.</p>

<h2>Methodologie</h2>
<p>Elke maandag (met een dinsdag-vangnet) wordt de PDF-publicatie van CBR automatisch
opgehaald voor praktijkexamen, herexamen en theorie-examen, en per locatie geparsed.
De "weken"-waarde is CBR's eigen definitie: het aantal weken tot er voldoende
examenplekken beschikbaar zijn &mdash; geen garantie, en vaak kan het opleidingsinstituut
eerder een plek vinden via het reserveringssysteem.</p>

<h2>Broncode &amp; ruwe data</h2>
<p>De volledige pipeline, ruwe PDF's en geschiedenis staan open op
<a href="https://github.com/mansikapahi/cbr-wachttijden-archief" target="_blank" rel="noopener">GitHub</a>.</p>
"""
    (out_dir / "over.html").write_text(
        page("Over dit archief | rijexamenwachttijden.nl",
             "Methodologie en achtergrond van het CBR-wachttijden archief.", body))


SITE_URL = "https://rijexamenwachttijden.nl"


def build_sitemap(locations, out_dir):
    """Lists homepage, over.html, and every location page so Google can
    discover pages that aren't reachable purely by crawling links."""
    urls = [
        f"{SITE_URL}/",
        f"{SITE_URL}/over.html",
        f"{SITE_URL}/widgets.html",
        f"{SITE_URL}/kortste-wachttijden.html",
    ]
    for lslug in locations:
        urls.append(f"{SITE_URL}/locatie/{lslug}/")

    body = "".join(f"<url><loc>{u}</loc></url>\n" for u in urls)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}"
        "</urlset>\n"
    )
    (out_dir / "sitemap.xml").write_text(xml)


def build_robots(out_dir):
    (out_dir / "robots.txt").write_text(
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n"
    )


def build_data_json(locations, latest_by_exam, out_dir):
    """Machine-readable snapshot the alert Worker reads to compare this
    week's values against what it last sent alerts for. Kept separate from
    the HTML build so the Worker never has to parse CSV/HTML."""
    import json
    snapshot = {}
    for lslug, entry in locations.items():
        snapshot[lslug] = {
            "name": entry["name"],
            "province": entry["province"],
            "weeks": {
                slug: latest_by_exam.get(slug, {}).get(lslug)
                for slug in EXAM_ORDER
                if latest_by_exam.get(slug, {}).get(lslug) is not None
            },
        }
    (out_dir / "data.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=0))


def main():
    DIST.mkdir(exist_ok=True)
    (DIST / "style.css").write_text(CSS)
    locations, latest_by_exam = load_history()
    build_homepage(locations, latest_by_exam, DIST)
    build_over_page(DIST)
    build_ranking_page(locations, latest_by_exam, DIST)
    for lslug, entry in locations.items():
        build_location_page(lslug, entry, DIST)
        build_widget(lslug, entry, DIST)
    build_widgets_page(locations, DIST)
    build_sitemap(locations, DIST)
    build_robots(DIST)
    build_data_json(locations, latest_by_exam, DIST)
    print(f"Built {len(locations)} location pages + {len(locations)} widgets + "
          f"homepage + over.html + widgets.html + data.json + sitemap.xml + robots.txt into dist/")


if __name__ == "__main__":
    main()
