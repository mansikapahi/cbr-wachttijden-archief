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

.calc{background:var(--wit);border:1px solid var(--lijn);border-radius:6px;padding:24px;margin:24px 0}
.calc-row{display:flex;align-items:center;flex-wrap:wrap;gap:10px;padding:10px 0;border-bottom:1px solid var(--lijn)}
.calc-row:last-of-type{border-bottom:none}
.calc-row label{font-weight:500;min-width:220px}
.calc-row input[type=number]{width:90px;padding:6px 10px;border:2px solid var(--inkt);border-radius:4px;font-family:var(--mono);font-size:1rem}
.calc-row select{padding:6px 10px;border:2px solid var(--inkt);border-radius:4px;font-family:var(--sans);font-size:0.95rem;background:var(--wit)}
.calc-row input[type=checkbox]{width:18px;height:18px;margin-right:6px;vertical-align:middle}
.calc-hint{font-size:0.85rem;color:#6b6b60}
.calc-total{margin-top:18px;padding-top:18px;border-top:2px solid var(--inkt)}
#calc-breakdown{width:100%;border-collapse:collapse;font-size:0.95rem}
#calc-breakdown td{padding:6px 0;border-bottom:1px solid var(--lijn)}
#calc-breakdown td:last-child{text-align:right;font-family:var(--mono)}
.calc-grand-total{display:flex;justify-content:space-between;margin-top:14px;font-family:var(--display);
  font-size:1.4rem;font-weight:600}
.calc-grand-total span{color:var(--groen)}

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

.rijschool-list{display:grid;gap:10px;margin:12px 0 6px}
.rijschool-card{background:var(--wit);border:1px solid var(--lijn);border-radius:6px;padding:12px 16px}
.rijschool-card strong{display:block;font-size:0.98rem;margin-bottom:4px}
.rijschool-rating{display:block;font-size:0.85rem;color:#6b6b60}
.rijschool-contact{display:block;font-size:0.85rem;margin-top:4px}
.rijschool-contact a{color:var(--groen)}

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
<meta property="og:type" content="website">
<meta property="og:site_name" content="rijexamenwachttijden.nl">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:image" content="https://rijexamenwachttijden.nl/og-image.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{description}">
<meta name="twitter:image" content="https://rijexamenwachttijden.nl/og-image.png">
<link rel="alternate" type="application/rss+xml" title="rijexamenwachttijden.nl updates" href="{root}feed.xml">
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
    <a href="{root}kosten-rijbewijs.html">Kosten rijbewijs</a>
    <a href="{root}planning.html">Wanneer ben ik klaar?</a>
    <a href="{root}kennisbank/index.html">Kennisbank</a>
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


def page(title, description, body, root="./", extra_head="", canonical=None):
    html = HEAD.format(title=title, description=description, root=root) + body + FOOT
    if canonical:
        html = html.replace(
            "</head>",
            f'<link rel="canonical" href="{SITE_URL}{canonical}">\n</head>')
    if extra_head:
        html = html.replace("</head>", extra_head + "\n</head>")
    return html


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

DATASET_SCHEMA = """<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Dataset",
  "name": "CBR-wachttijden archief: praktijkexamen, herexamen en theorie-examen per locatie",
  "description": "Wekelijks gearchiveerde wachttijden (in weken) voor het CBR-praktijkexamen, herexamen en theorie-examen, per examenlocatie in Nederland. CBR publiceert alleen de actuele week; dit archief bewaart elke wekelijkse publicatie apart sinds week 27, 2026.",
  "url": "https://rijexamenwachttijden.nl/",
  "creator": {
    "@type": "Organization",
    "name": "rijexamenwachttijden.nl",
    "url": "https://rijexamenwachttijden.nl/over.html"
  },
  "distribution": [
    {
      "@type": "DataDownload",
      "encodingFormat": "CSV",
      "contentUrl": "https://rijexamenwachttijden.nl/data.json"
    }
  ],
  "temporalCoverage": "2026-07-01/..",
  "spatialCoverage": {
    "@type": "Place",
    "name": "Nederland"
  },
  "keywords": ["CBR", "wachttijd", "praktijkexamen", "herexamen", "theorie-examen", "rijbewijs", "rijexamen"]
}
</script>"""


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
        cards.append(f'<div class="provincie" id="{slugify(prov)}"><h3>{prov}</h3>{"".join(rows)}</div>')

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
             "theorie-examen per locatie in Nederland.", body, extra_head=DATASET_SCHEMA,
             canonical="/"))


def build_location_csv(lslug, entry, out_dir):
    """A raw CSV download of this location's full history -- same data as
    the HTML tables, for anyone who wants to plot/analyze it themselves."""
    import csv
    import io

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["examtype", "gearchiveerd_iso_week", "cbr_week", "periode", "weken"])
    for slug in EXAM_ORDER:
        series = entry["series"].get(slug)
        if not series:
            continue
        label = EXAM_META[slug]["label"]
        for iso, cw, cp, w in series:
            writer.writerow([label, iso, cw, cp, w])

    d = out_dir / "locatie" / lslug
    d.mkdir(parents=True, exist_ok=True)
    (d / "geschiedenis.csv").write_text(buf.getvalue())


def load_rijscholen():
    """Optional: data/rijscholen.json maps location slug -> list of driving
    schools. Missing file or missing location both just mean 'no listing
    yet' -- this feature degrades gracefully as coverage is filled in."""
    import json
    path = DATA / "rijscholen.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def build_rijscholen_section(lslug, entry, rijscholen):
    schools = rijscholen.get(lslug)
    if not schools:
        return ""

    cards = []
    for s in schools[:5]:
        stars = "\u2605" * round(s.get("rating", 0))
        contact_bits = []
        if s.get("phone"):
            contact_bits.append(f'<a href="tel:{s["phone"].replace(" ", "")}">{s["phone"]}</a>')
        if s.get("website"):
            contact_bits.append(f'<a href="{s["website"]}" target="_blank" rel="noopener nofollow">website</a>')
        cards.append(f"""
<div class="rijschool-card">
  <strong>{s['name']}</strong>
  <span class="rijschool-rating">{stars} {s.get('rating', '?')} &middot; {s.get('reviews', 0)} reviews</span>
  <span class="rijschool-contact">{' &middot; '.join(contact_bits)}</span>
</div>""")

    return f"""
<h2>Rijscholen in {entry['name']}</h2>
<div class="rijschool-list">{"".join(cards)}</div>
<p class="source-note">Bron: Google Maps. Geen samenwerking of vergoeding &mdash; gewoon
een startpunt om een rijschool te vinden.</p>
"""


def build_location_page(lslug, entry, out_dir, rijscholen):
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

{build_rijscholen_section(lslug, entry, rijscholen)}

{"".join(history_sections)}

<p class="source-note">Bron: CBR, wekelijks gearchiveerd. Definitie: aantal weken tot
er voldoende examenplekken beschikbaar zijn (CBR's eigen definitie).
&middot; <a href="geschiedenis.csv" download>Download geschiedenis als CSV</a></p>

<p class="source-note">Meer weten? Lees <a href="../../kennisbank/waarom-verschilt-wachttijd-per-locatie/">waarom
verschilt de wachttijd per examenlocatie?</a> of <a href="../../kennisbank/hoe-lang-wachttijd-praktijkexamen/">hoe
lang is de wachttijd voor het CBR praktijkexamen?</a></p>

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
    breadcrumb_schema = f"""<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {{"@type": "ListItem", "position": 1, "name": "Overzicht", "item": "{SITE_URL}/"}},
    {{"@type": "ListItem", "position": 2, "name": "{prov}", "item": "{SITE_URL}/#{slugify(prov)}"}},
    {{"@type": "ListItem", "position": 3, "name": "{entry['name']}", "item": "{SITE_URL}/locatie/{lslug}/"}}
  ]
}}
</script>"""
    (d / "index.html").write_text(
        page(f"{entry['name']}: {current_praktijk} weken wachttijd praktijkexamen | rijexamenwachttijden.nl",
             location_description, body, root="../../",
             canonical=f"/locatie/{lslug}/", extra_head=breadcrumb_schema))


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
             "examenlocatie op je eigen rijschool-website.", body,
             canonical="/widgets.html"))



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
                f'<tr><td data-sort-value="{rank}">{rank}</td>'
                f'<td data-sort-value="{entry["name"].lower()}"><a href="locatie/{lslug}/">{entry["name"]}</a></td>'
                f'<td data-sort-value="{entry["province"].lower()}">{entry["province"]}</td>'
                f'<td data-sort-value="{weeks_sort_key(w)}"><span class="pill {uc}">{w} wk</span></td></tr>'
            )
        sections.append(f"""
<h2>{meta['label']} &mdash; kortste wachttijd eerst</h2>
<table class="history-table ranking-table">
<tr><th data-col="0">#</th><th data-col="1">Locatie</th><th data-col="2">Provincie</th><th data-col="3">Wachttijd</th></tr>
{"".join(rows)}
</table>""")

    body = f"""
<h1>Kortste wachttijden CBR-examens</h1>
<p class="lead">Alle {len(locations)} locaties gerangschikt van kortste naar langste
wachttijd, per examentype. Bijgewerkt bij elke wekelijkse archivering. Klik op een
kolomkop om te sorteren.</p>
{"".join(sections)}
<p class="source-note">Zie ook de <a href="index.html">volledige lijst per provincie</a>
of <a href="over.html">hoe dit archief werkt</a>.</p>

<script>
document.querySelectorAll('.ranking-table').forEach(function(table) {{
  var headers = table.querySelectorAll('th');
  headers.forEach(function(th) {{
    th.style.cursor = 'pointer';
    var asc = true;
    th.addEventListener('click', function() {{
      var col = parseInt(th.dataset.col, 10);
      var tbody = Array.from(table.querySelectorAll('tr')).slice(1);
      tbody.sort(function(a, b) {{
        var va = a.children[col].dataset.sortValue;
        var vb = b.children[col].dataset.sortValue;
        var na = parseFloat(va), nb = parseFloat(vb);
        var cmp = (!isNaN(na) && !isNaN(nb)) ? (na - nb) : va.localeCompare(vb);
        return asc ? cmp : -cmp;
      }});
      tbody.forEach(function(row) {{ table.appendChild(row); }});
      asc = !asc;
    }});
  }});
}});
</script>
"""
    (out_dir / "kortste-wachttijden.html").write_text(
        page("Kortste wachttijden CBR-examens | rijexamenwachttijden.nl",
             "Alle examenlocaties in Nederland gerangschikt van kortste naar langste "
             "CBR-wachttijd, voor praktijkexamen, herexamen en theorie-examen.", body,
             canonical="/kortste-wachttijden.html"))


KENNISBANK = [
    {
        "slug": "hoe-lang-wachttijd-praktijkexamen",
        "title": "Hoe lang is de wachttijd voor het CBR praktijkexamen?",
        "description": "Uitleg over de wachttijd voor het CBR praktijkexamen: wat het "
                        "betekent, hoe het verschilt per locatie, en waar je de actuele en "
                        "historische cijfers vindt.",
        "body": """
<h1>Hoe lang is de wachttijd voor het CBR praktijkexamen?</h1>
<p class="lead">De wachttijd voor het praktijkexamen auto is het aantal weken tussen het
moment dat je (via je rijschool) een examen kunt reserveren en de eerst beschikbare
examendatum bij het CBR. Deze wachttijd verschilt sterk per examenlocatie en per week
&mdash; er is geen vast landelijk cijfer dat overal geldt.</p>

<h2>Waarom is er geen vast antwoord?</h2>
<p>Het CBR publiceert wekelijks de actuele wachttijd per examenlocatie, maar deze cijfers
wisselen voortdurend door annuleringen, drukte in bepaalde regio's en de beschikbaarheid
van examinatoren. Een wachttijd van 6 weken in de ene stad zegt niets over een andere
stad verderop &mdash; en het cijfer van deze week kan er volgende week alweer anders
uitzien.</p>

<h2>Waar vind je de actuele wachttijd voor jouw locatie?</h2>
<p>Op het <a href="../../index.html">overzicht per provincie</a> staan alle CBR-examenlocaties
met de actuele wachttijd in weken. Omdat wij elke week archiveren, kun je op elke
locatiepagina ook zien hoe de wachttijd zich de afgelopen weken heeft ontwikkeld &mdash;
iets wat je nergens anders terugvindt. Zie ook de <a href="../../kortste-wachttijden.html">
kortste wachttijden</a>, gerangschikt per examentype.</p>

<h2>Wat beïnvloedt de wachttijd?</h2>
<ul>
<li><strong>Regio en drukte:</strong> grote steden en populaire locaties hebben vaak
langere wachttijden dan kleinere locaties.</li>
<li><strong>Seizoen:</strong> in sommige periodes van het jaar is de vraag naar examens
hoger.</li>
<li><strong>Beschikbaarheid van examinatoren:</strong> dit varieert per locatie en
periode.</li>
<li><strong>Annuleringen:</strong> soms komen er tussentijds plekken vrij, waardoor de
wachttijd op korte termijn kan dalen.</li>
</ul>

<h2>Praktijkexamen vs. herexamen</h2>
<p>De wachttijd voor een eerste praktijkexamen en voor een herexamen kunnen van elkaar
verschillen. Lees meer in <a href="../verschil-praktijkexamen-herexamen/">wachttijd
praktijkexamen vs. herexamen: wat is het verschil?</a> Benieuwd naar de wachttijd
vóór het praktijkexamen? Zie <a href="../wachttijd-theorie-examen/">hoe lang is de
wachttijd voor het CBR theorie-examen?</a></p>
""",
    },
    {
        "slug": "waarom-verschilt-wachttijd-per-locatie",
        "title": "Waarom verschilt de wachttijd per examenlocatie?",
        "description": "Waarom de CBR-wachttijd voor het praktijkexamen per locatie kan "
                        "verschillen, en hoe je de beste examenplek voor jouw situatie kiest.",
        "body": """
<h1>Waarom verschilt de wachttijd per examenlocatie?</h1>
<p class="lead">De wachttijd voor het CBR-praktijkexamen kan tussen twee locaties die maar
een half uur van elkaar liggen zomaar enkele weken schelen. Dat komt niet doordat het ene
CBR-kantoor "beter" is dan het andere, maar door een combinatie van factoren die per
locatie en per week anders uitpakt.</p>

<h2>De belangrijkste factoren</h2>
<p><strong>Bevolkingsdichtheid en vraag.</strong> Locaties in en rond grote steden zoals
Amsterdam, Utrecht en Rotterdam verwerken doorgaans meer aanvragen, wat de wachttijd kan
opdrijven ten opzichte van kleinere, minder drukke locaties.</p>
<p><strong>Aantal beschikbare examinatoren.</strong> Elke locatie heeft een eigen planning
van examinatoren. Uitval, ziekte of tijdelijke onderbezetting op één locatie werkt direct
door in de wachttijd op die plek, zonder dat andere locaties dit merken.</p>
<p><strong>Regionale spreiding van rijscholen.</strong> In sommige regio's zijn er
relatief veel rijscholen die examens aanvragen voor dezelfde locatie, wat de druk op die
specifieke plek verhoogt.</p>
<p><strong>Tijdelijke pieken.</strong> Een lokale gebeurtenis kan een locatie voor een
aantal weken uit de pas laten lopen met de rest van het land.</p>

<h2>Wat betekent dit voor jou?</h2>
<p>Als je enige reisafstand kunt overbruggen, kan het de moeite waard zijn om de
wachttijd van meerdere locaties in jouw regio te vergelijken. Een verschil van een paar
weken kan soms al opgelost worden door een naburige locatie te overwegen &mdash; in
overleg met je rijschool, die de daadwerkelijke reservering doet.</p>

<h2>Vergelijk locaties in jouw regio</h2>
<p>Op het <a href="../../index.html">overzicht per provincie</a> zie je alle
examenlocaties met de actuele wachttijd ernaast, en op de <a
href="../../kortste-wachttijden.html">kortste-wachttijden-pagina</a> staan ze
gerangschikt van kort naar lang. Benieuwd hoe de wachttijd van jouw locatie zich de
afgelopen weken heeft ontwikkeld? Elke locatiepagina toont ook de geschiedenis, niet
alleen het actuele cijfer.</p>
""",
    },
    {
        "slug": "verschil-praktijkexamen-herexamen",
        "title": "Wachttijd praktijkexamen vs. herexamen: wat is het verschil?",
        "description": "Is de wachttijd voor een herexamen bij het CBR korter dan voor een "
                        "eerste praktijkexamen? Uitleg over het verschil en waar je actuele "
                        "cijfers voor beide vindt.",
        "body": """
<h1>Wachttijd praktijkexamen vs. herexamen: wat is het verschil?</h1>
<p class="lead">Als je voor je eerste praktijkexamen bent gezakt, is de eerstvolgende
vraag meestal: hoe lang moet ik nu wachten op een herexamen? Het CBR houdt voor eerste
examens en herexamens aparte wachttijden bij, en deze twee cijfers lopen niet altijd
gelijk op.</p>

<h2>Waarom zijn dit twee aparte cijfers?</h2>
<p>Eerste examens en herexamens worden binnen dezelfde planning van een examenlocatie
ingepland, maar met een eigen tel voor wachttijd. Dat betekent dat een locatie op
hetzelfde moment een andere wachttijd voor een herexamen kan hebben dan voor een eerste
examen &mdash; soms korter, soms langer, afhankelijk van hoeveel ruimte er in de planning
is voor elk type.</p>

<h2>Wat kun je hieraan doen?</h2>
<p>De wachttijd voor een herexamen wordt, net als voor het eerste examen, per week
bijgewerkt en verschilt per locatie. Er is geen landelijke regel die zegt dat een
herexamen altijd sneller of trager gaat dan een eerste examen &mdash; dit hangt af van de
actuele planning op dat moment. Je rijschool regelt de daadwerkelijke reservering en kan
je vertellen welke opties er voor jouw locatie zijn.</p>

<h2>Actuele cijfers per locatie</h2>
<p>Op elke locatiepagina zie je zowel de wachttijd voor het eerste praktijkexamen als
voor het herexamen, plus hoe deze zich de afgelopen weken hebben ontwikkeld. Bekijk het
<a href="../../index.html">overzicht per provincie</a> om jouw examenplaats te vinden.</p>

<p>Lees ook <a href="../hoe-lang-wachttijd-praktijkexamen/">hoe lang is de wachttijd voor
het CBR praktijkexamen?</a> voor een bredere uitleg over wat de wachttijd beïnvloedt.</p>
""",
    },
    {
        "slug": "volg-wachttijd-trend",
        "title": "Hoe volg je de wachttijd-trend van je examenlocatie?",
        "description": "Waarom het niet genoeg is om alleen de wachttijd van deze week te "
                        "bekijken, en hoe je de trend van jouw CBR-examenlocatie over tijd "
                        "volgt.",
        "body": """
<h1>Hoe volg je de wachttijd-trend van je examenlocatie?</h1>
<p class="lead">Een wachttijd van 6 weken zegt maar de helft van het verhaal. Is die
wachttijd de afgelopen maand gestegen of gedaald? Ligt hij hoger of lager dan normaal
voor deze locatie? Zonder geschiedenis is een los cijfer moeilijk te interpreteren.</p>

<h2>Waarom een momentopname niet genoeg is</h2>
<p>Het CBR publiceert elke week een actuele wachttijd per locatie, maar overschrijft deze
wekelijks &mdash; er is geen ingebouwde manier om te zien hoe dat cijfer zich ontwikkelt.
Dat maakt het lastig om onderscheid te maken tussen een tijdelijke piek en een
structurele stijging.</p>

<h2>Hoe wij dit oplossen</h2>
<p>Omdat CBR deze data wekelijks overschrijft, archiveren wij elke publicatie apart. Op
elke locatiepagina vind je daarom niet alleen de actuele wachttijd, maar ook een
sparkline en tabel met de afgelopen weken, zodat je zelf kunt zien of de trend stijgt,
daalt, of stabiel blijft.</p>

<h2>Hoe je dit gebruikt bij het plannen van je examen</h2>
<ul>
<li><strong>Stijgende trend:</strong> het kan de moeite waard zijn om eerder te
reserveren, of een naburige locatie te overwegen.</li>
<li><strong>Dalende trend:</strong> wachten kan gunstig uitpakken als je nog niet
examenklaar bent.</li>
<li><strong>Stabiele trend:</strong> dit geeft een realistischer beeld van wat je
structureel kunt verwachten dan het cijfer van één week.</li>
</ul>

<p>Bekijk het <a href="../../index.html">overzicht per provincie</a> om de trend van
jouw examenlocatie te bekijken, of lees <a href="../../over.html">over dit archief</a>
voor meer uitleg over hoe en waarom wij deze data wekelijks bewaren.</p>
""",
    },
    {
        "slug": "veelgestelde-vragen",
        "title": "Veelgestelde vragen over CBR-wachttijden",
        "description": "Antwoorden op veelgestelde vragen over CBR-wachttijden voor het "
                        "praktijkexamen: publicatiemomenten, ontbrekende updates, en hoe de "
                        "data tot stand komt.",
        "body": """
<h1>Veelgestelde vragen over CBR-wachttijden</h1>

<h2>Wanneer publiceert het CBR nieuwe wachttijden?</h2>
<p>Het CBR publiceert wekelijks nieuwe wachttijden per examenlocatie. Wij archiveren deze
publicatie zodra hij beschikbaar is, zodat je zowel de actuele als historische cijfers
kunt bekijken.</p>

<h2>Wat betekent het als een locatie geen update heeft deze week?</h2>
<p>Soms publiceert het CBR voor een bepaalde week geen nieuwe cijfers, bijvoorbeeld rond
feestdagen of in specifieke periodes van het examenseizoen. Onze locatiepagina's geven
aan wanneer de laatste beschikbare update dateert.</p>

<h2>Waarom archiveren jullie deze data, terwijl het CBR die al publiceert?</h2>
<p>Het CBR toont alleen de wachttijd van de huidige week en overschrijft dit cijfer bij
de volgende publicatie. Daardoor is er geen manier om te zien hoe de wachttijd zich over
tijd ontwikkelt. Wij bewaren elke wekelijkse publicatie apart, zodat je de trend per
locatie kunt volgen. Lees meer op <a href="../../over.html">over dit archief</a>.</p>

<h2>Is de wachttijd op deze site hetzelfde als wat mijn rijschool mij vertelt?</h2>
<p>Onze cijfers zijn gebaseerd op de wekelijkse publicaties van het CBR. Je rijschool
plant de daadwerkelijke reservering en kan de meest actuele beschikbaarheid op het
moment van reserveren bevestigen, wat kan afwijken van het gepubliceerde gemiddelde.</p>

<h2>Kan ik zelf een andere locatie kiezen als de wachttijd te lang is?</h2>
<p>Je rijschool bepaalt in overleg met jou op welke locatie het examen wordt aangevraagd.
Op het <a href="../../index.html">overzicht per provincie</a> kun je de wachttijden van
verschillende locaties vergelijken.</p>

<h2>Waar komt de data vandaan?</h2>
<p>De cijfers zijn afkomstig uit de officiële, openbare publicaties van het CBR. Meer
over onze werkwijze staat op <a href="../../over.html">over dit archief</a>.</p>

<h2>Hoe vaak wordt deze website bijgewerkt?</h2>
<p>Wekelijks, in lijn met het publicatieschema van het CBR.</p>
""",
    },
    {
        "slug": "wachttijd-theorie-examen",
        "title": "Hoe lang is de wachttijd voor het CBR theorie-examen?",
        "description": "Uitleg over de wachttijd voor het CBR theorie-examen: hoe je het "
                        "aanvraagt, wat de wachttijd beïnvloedt, en hoe dit zich verhoudt "
                        "tot het praktijkexamen.",
        "body": """
<h1>Hoe lang is de wachttijd voor het CBR theorie-examen?</h1>
<p class="lead">De wachttijd voor het theorie-examen is het aantal weken tussen het
aanvragen van een examendatum en de eerst beschikbare datum bij het CBR. Deze wachttijd
staat los van de wachttijd voor het praktijkexamen en verschilt per locatie.</p>

<h2>Theorie-examen aanvragen: hoe werkt dat?</h2>
<p>Je kunt het theorie-examen zelf aanvragen via Mijn CBR, of via je rijschool laten
regelen. Sinds 2024 geldt dat je pas een praktijkexamen kunt reserveren nadat je
theorie-examen is behaald &mdash; dat maakt de wachttijd voor theorie een belangrijke
eerste stap in je totale traject naar het rijbewijs.</p>

<h2>Waarom verschilt de wachttijd per locatie?</h2>
<p>Net als bij het praktijkexamen speelt drukte, beschikbare capaciteit en regionale
spreiding een rol. Grotere, populairdere examenlocaties kunnen een langere wachttijd
hebben dan kleinere locaties, ook al ligt het landelijk gemiddelde vaak lager voor
theorie dan voor praktijk. Lees meer over deze factoren in <a
href="../waarom-verschilt-wachttijd-per-locatie/">waarom verschilt de wachttijd per
examenlocatie?</a></p>

<h2>Theorie-examen vs. praktijkexamen: twee aparte wachttijden</h2>
<p>De wachttijd voor theorie en praktijk worden apart bijgehouden en lopen niet
gelijk op. Omdat je theorie-examen inmiddels bepalend is voor wanneer je je
praktijkexamen kunt inplannen, is het slim om de wachttijd voor beide examens
tegelijk in de gaten te houden &mdash; niet alleen op het moment dat je aan de beurt
bent voor theorie.</p>

<h2>Actuele cijfers per locatie</h2>
<p>Op elke locatiepagina in het <a href="../../index.html">overzicht per provincie</a>
vind je naast praktijkexamen en herexamen ook de actuele en historische wachttijd voor
het theorie-examen, inclusief het verloop over de afgelopen weken.</p>

<p>Lees ook <a href="../hoe-lang-wachttijd-praktijkexamen/">hoe lang is de wachttijd
voor het CBR praktijkexamen?</a> voor het vervolg van je traject na het theorie-examen.</p>
""",
    },
]

KENNISBANK_FAQ_SCHEMA = """<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {"@type": "Question", "name": "Wanneer publiceert het CBR nieuwe wachttijden?",
     "acceptedAnswer": {"@type": "Answer", "text": "Het CBR publiceert wekelijks nieuwe wachttijden per examenlocatie. Wij archiveren deze publicatie zodra hij beschikbaar is, zodat je zowel de actuele als historische cijfers kunt bekijken."}},
    {"@type": "Question", "name": "Wat betekent het als een locatie geen update heeft deze week?",
     "acceptedAnswer": {"@type": "Answer", "text": "Soms publiceert het CBR voor een bepaalde week geen nieuwe cijfers, bijvoorbeeld rond feestdagen of in specifieke periodes van het examenseizoen. Onze locatiepagina's geven aan wanneer de laatste beschikbare update dateert."}},
    {"@type": "Question", "name": "Waarom archiveren jullie deze data, terwijl het CBR die al publiceert?",
     "acceptedAnswer": {"@type": "Answer", "text": "Het CBR toont alleen de wachttijd van de huidige week en overschrijft dit cijfer bij de volgende publicatie. Wij bewaren elke wekelijkse publicatie apart, zodat je de trend per locatie kunt volgen."}},
    {"@type": "Question", "name": "Is de wachttijd op deze site hetzelfde als wat mijn rijschool mij vertelt?",
     "acceptedAnswer": {"@type": "Answer", "text": "Onze cijfers zijn gebaseerd op de wekelijkse publicaties van het CBR. Je rijschool plant de daadwerkelijke reservering en kan de meest actuele beschikbaarheid bevestigen, wat kan afwijken van het gepubliceerde gemiddelde."}},
    {"@type": "Question", "name": "Kan ik zelf een andere locatie kiezen als de wachttijd te lang is?",
     "acceptedAnswer": {"@type": "Answer", "text": "Je rijschool bepaalt in overleg met jou op welke locatie het examen wordt aangevraagd. Op de homepagina kun je de wachttijden van verschillende locaties vergelijken."}},
    {"@type": "Question", "name": "Waar komt de data vandaan?",
     "acceptedAnswer": {"@type": "Answer", "text": "De cijfers zijn afkomstig uit de officiële, openbare publicaties van het CBR."}},
    {"@type": "Question", "name": "Hoe vaak wordt deze website bijgewerkt?",
     "acceptedAnswer": {"@type": "Answer", "text": "Wekelijks, in lijn met het publicatieschema van het CBR."}}
  ]
}
</script>"""


def build_kennisbank_pages(out_dir):
    """Background/explainer content -- gives Google (and AI answer engines)
    topical-authority signals beyond the raw data pages, and interlinks
    back to locatie/index/over pages."""
    for entry in KENNISBANK:
        extra_head = KENNISBANK_FAQ_SCHEMA if entry["slug"] == "veelgestelde-vragen" else ""
        d = out_dir / "kennisbank" / entry["slug"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(
            page(f"{entry['title']} | rijexamenwachttijden.nl",
                 entry["description"], entry["body"], root="../../",
                 extra_head=extra_head, canonical=f"/kennisbank/{entry['slug']}/"))


def build_kennisbank_index(out_dir):
    rows = "".join(
        f'<li><a href="{e["slug"]}/">{e["title"]}</a></li>' for e in KENNISBANK
    )
    body = f"""
<h1>Kennisbank: alles over CBR-wachttijden</h1>
<p class="lead">Achtergrondartikelen over hoe CBR-wachttijden werken, waarom ze
verschillen per locatie, en hoe je de cijfers het beste gebruikt bij het plannen van je
praktijkexamen.</p>
<ul>{rows}</ul>
<p class="source-note">Bekijk ook het <a href="../index.html">overzicht per provincie</a>
of lees <a href="../over.html">over dit archief</a>.</p>
"""
    d = out_dir / "kennisbank"
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(
        page("Kennisbank: alles over CBR-wachttijden | rijexamenwachttijden.nl",
             "Uitleg, achtergrond en veelgestelde vragen over CBR-wachttijden voor het "
             "praktijkexamen \u2014 per locatie, per examentype, en over tijd.",
             body, root="../", canonical="/kennisbank/"))


def build_calculator_page(out_dir):
    """Interactive 'wat kost een rijbewijs' calculator. Uses official 2026
    CBR-tarieven (published by cbr.nl, 14-10-2025) so numbers are real, not
    guesses. All calculation happens client-side in vanilla JS, matching the
    site's existing no-framework approach."""
    body = """
<h1>Wat kost een rijbewijs?</h1>
<p class="lead">Bereken je verwachte totale kosten voor het CBR-praktijkexamen,
theorie-examen en rijlessen &mdash; op basis van de officiële CBR-tarieven voor 2026.
Pas de getallen aan naar jouw situatie.</p>

<div class="calc">
  <div class="calc-row">
    <label for="lessen">Aantal rijlessen</label>
    <input type="number" id="lessen" value="41" min="0" step="1">
    <span class="calc-hint">Landelijk gemiddelde volgens het CBR: 41 lessen</span>
  </div>
  <div class="calc-row">
    <label for="lesprijs">Prijs per rijles (&euro;)</label>
    <input type="number" id="lesprijs" value="58" min="0" step="1">
    <span class="calc-hint">Landelijk betaalt 80% tussen &euro;50 en &euro;72 per uur (bron: CBR)</span>
  </div>
  <div class="calc-row">
    <label for="theoriepogingen">Theorie-examen: aantal pogingen</label>
    <select id="theoriepogingen">
      <option value="1" selected>1 (in &eacute;&eacute;n keer geslaagd)</option>
      <option value="2">2</option>
      <option value="3">3</option>
    </select>
  </div>
  <div class="calc-row">
    <label for="praktijkpogingen">Praktijkexamen: aantal pogingen</label>
    <select id="praktijkpogingen">
      <option value="1" selected>1 (in &eacute;&eacute;n keer geslaagd)</option>
      <option value="2">2</option>
      <option value="3">3</option>
    </select>
  </div>
  <div class="calc-row">
    <label for="ttt"><input type="checkbox" id="ttt"> Tussentijdse toets (TTT)</label>
    <span class="calc-hint">Optioneel, door veel rijscholen geadviseerd</span>
  </div>
  <div class="calc-row">
    <label for="gezondheid"><input type="checkbox" id="gezondheid" checked> Gezondheidsverklaring</label>
  </div>

  <div class="calc-total">
    <table id="calc-breakdown"></table>
    <div class="calc-grand-total">Totaal: <span id="calc-total-bedrag">&euro;0</span></div>
  </div>
</div>

<p class="source-note">Tarieven: officiële CBR-tarieven 2026 (bekendgemaakt 14-10-2025) voor
examens en gezondheidsverklaring. Rijlesprijs op basis van CBR-onderzoek onder
examenkandidaten: 80% betaalt tussen &euro;50 en &euro;72 per uur. Gemeentekosten voor het
rijbewijs: landelijk gemiddeld &euro;52,10, met een wettelijk maximum van &euro;53,65.
CBR-tarieven zijn niet onderhandelbaar en gelden landelijk; rijlesprijzen verschillen per
rijschool en regio. Dit is een indicatie, geen offerte.</p>

<h2>Rijschool nodig?</h2>
<p>Bekijk <a href="widgets.html">rijscholen in jouw regio</a> via onze locatiepagina's, of
vergelijk direct de <a href="kortste-wachttijden.html">wachttijd per examenlocatie</a> zodat
je weet waar je het snelst terecht kunt.</p>

<h2>Wanneer ben je klaar?</h2>
<p>Gebruik ook onze <a href="planning.html">planningstool</a> om te berekenen wanneer je,
gegeven de actuele wachttijd van jouw locatie, je rijbewijs kunt verwachten.</p>

<h2>Meer weten over de kosten?</h2>
<p>Lees ook <a href="kennisbank/hoe-lang-wachttijd-praktijkexamen/">hoe lang is de
wachttijd voor het CBR praktijkexamen?</a> en <a
href="kennisbank/wachttijd-theorie-examen/">hoe lang is de wachttijd voor het CBR
theorie-examen?</a> om je hele traject te plannen.</p>

<script>
(function() {
  var TARIEVEN = {
    theorie: 50.50,
    praktijk: 143.50,
    ttt: 143.50,
    gezondheidsverklaring: 46.90,
    gemeente: 52.10
  };

  var lessen = document.getElementById('lessen');
  var lesprijs = document.getElementById('lesprijs');
  var theoriepogingen = document.getElementById('theoriepogingen');
  var praktijkpogingen = document.getElementById('praktijkpogingen');
  var ttt = document.getElementById('ttt');
  var gezondheid = document.getElementById('gezondheid');
  var breakdown = document.getElementById('calc-breakdown');
  var totaalEl = document.getElementById('calc-total-bedrag');

  function eur(n) {
    return '\\u20ac' + n.toLocaleString('nl-NL', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  }

  function bereken() {
    var rows = [];
    var totaal = 0;

    var lessenKosten = (parseFloat(lessen.value) || 0) * (parseFloat(lesprijs.value) || 0);
    rows.push(['Rijlessen (' + lessen.value + ' \\u00d7 ' + eur(parseFloat(lesprijs.value) || 0) + ')', lessenKosten]);
    totaal += lessenKosten;

    var theorieKosten = TARIEVEN.theorie * (parseInt(theoriepogingen.value) || 1);
    rows.push(['Theorie-examen (' + theoriepogingen.value + '\\u00d7)', theorieKosten]);
    totaal += theorieKosten;

    var praktijkKosten = TARIEVEN.praktijk * (parseInt(praktijkpogingen.value) || 1);
    rows.push(['Praktijkexamen (' + praktijkpogingen.value + '\\u00d7)', praktijkKosten]);
    totaal += praktijkKosten;

    if (ttt.checked) {
      rows.push(['Tussentijdse toets', TARIEVEN.ttt]);
      totaal += TARIEVEN.ttt;
    }
    if (gezondheid.checked) {
      rows.push(['Gezondheidsverklaring', TARIEVEN.gezondheidsverklaring]);
      totaal += TARIEVEN.gezondheidsverklaring;
    }

    rows.push(['Rijbewijs aanvragen (gemeente)', TARIEVEN.gemeente]);
    totaal += TARIEVEN.gemeente;

    breakdown.innerHTML = rows.map(function(r) {
      return '<tr><td>' + r[0] + '</td><td>' + eur(r[1]) + '</td></tr>';
    }).join('');
    totaalEl.textContent = eur(totaal);
  }

  [lessen, lesprijs, theoriepogingen, praktijkpogingen, ttt, gezondheid].forEach(function(el) {
    el.addEventListener('input', bereken);
    el.addEventListener('change', bereken);
  });
  bereken();
})();
</script>
"""
    (out_dir / "kosten-rijbewijs.html").write_text(
        page("Wat kost een rijbewijs? Kostencalculator 2026 | rijexamenwachttijden.nl",
             "Bereken de kosten van je rijbewijs op basis van de officiële CBR-tarieven "
             "2026: rijlessen, theorie-examen, praktijkexamen en meer.", body,
             canonical="/kosten-rijbewijs.html"))


def build_planning_page(out_dir):
    """'Wanneer haal ik mijn rijbewijs?' -- combines this site's unique
    per-location wachttijd data with the person's own situation (lessons
    remaining, theorie status) to estimate a real target date. Fetches
    data.json client-side, same pattern as the homepage search."""
    body = """
<h1>Wanneer haal ik mijn rijbewijs?</h1>
<p class="lead">Combineer de actuele wachttijd van jouw examenlocatie met je eigen
planning &mdash; hoeveel lessen je nog nodig hebt en of je al geslaagd bent voor je
theorie-examen &mdash; voor een realistische inschatting van je einddatum.</p>

<div class="calc">
  <div class="calc-row">
    <label for="plan-locatie">Examenlocatie</label>
    <select id="plan-locatie"><option value="">Locatie laden&hellip;</option></select>
  </div>
  <div class="calc-row">
    <label for="plan-theorie"><input type="checkbox" id="plan-theorie"> Ik heb mijn
    theorie-examen al gehaald</label>
  </div>
  <div class="calc-row">
    <label for="plan-lessen">Nog benodigde rijlessen</label>
    <input type="number" id="plan-lessen" value="20" min="0" step="1">
  </div>
  <div class="calc-row">
    <label for="plan-tempo">Lessen per week</label>
    <input type="number" id="plan-tempo" value="1" min="0.5" step="0.5">
  </div>

  <div class="calc-total">
    <table id="plan-breakdown"></table>
    <div class="calc-grand-total">Verwachte einddatum: <span id="plan-datum">&mdash;</span></div>
  </div>
</div>

<p class="source-note">Inschatting op basis van de actuele wachttijd van de gekozen
locatie zoals door ons gearchiveerd, plus je eigen lestempo. Wachttijden kunnen
wekelijks veranderen &mdash; zie de <a href="index.html">actuele cijfers</a> voor de
laatste stand. Dit is een indicatie, geen garantie.</p>

<h2>Kosten in beeld?</h2>
<p>Bekijk ook de <a href="kosten-rijbewijs.html">kostencalculator</a> om naast je
planning ook je verwachte totale kosten te berekenen.</p>

<script>
(function() {
  var select = document.getElementById('plan-locatie');
  var theorie = document.getElementById('plan-theorie');
  var lessen = document.getElementById('plan-lessen');
  var tempo = document.getElementById('plan-tempo');
  var breakdown = document.getElementById('plan-breakdown');
  var datumEl = document.getElementById('plan-datum');
  var DATA = null;

  fetch('data.json').then(function(r) { return r.json(); }).then(function(json) {
    DATA = json;
    var entries = Object.keys(json).map(function(slug) {
      return {slug: slug, name: json[slug].name, province: json[slug].province};
    }).sort(function(a, b) { return a.name.localeCompare(b.name, 'nl'); });
    select.innerHTML = entries.map(function(e) {
      return '<option value="' + e.slug + '">' + e.name + ' (' + e.province + ')</option>';
    }).join('');
    bereken();
  }).catch(function() {
    select.innerHTML = '<option value="">Kon locaties niet laden</option>';
  });

  function bereken() {
    if (!DATA) return;
    var loc = DATA[select.value];
    if (!loc) return;

    var rows = [];
    var weken = 0;

    if (!theorie.checked) {
      var wt = parseFloat(loc.weeks['wanneer-theorie-examen']);
      if (!isNaN(wt)) {
        rows.push(['Wachttijd theorie-examen (' + loc.name + ')', wt + ' wk']);
        weken += wt;
      }
    } else {
      rows.push(['Theorie-examen', 'al gehaald']);
    }

    var lesWeken = (parseFloat(tempo.value) || 1) > 0
      ? (parseFloat(lessen.value) || 0) / (parseFloat(tempo.value) || 1)
      : 0;
    rows.push(['Resterende lessen (' + lessen.value + ' \\u00f7 ' + tempo.value + '/wk)',
      Math.ceil(lesWeken) + ' wk']);
    weken += lesWeken;

    var wp = parseFloat(loc.weeks['wanneer-praktijkexamen']);
    if (!isNaN(wp)) {
      rows.push(['Wachttijd praktijkexamen (' + loc.name + ')', wp + ' wk']);
      weken += wp;
    }

    breakdown.innerHTML = rows.map(function(r) {
      return '<tr><td>' + r[0] + '</td><td>' + r[1] + '</td></tr>';
    }).join('');

    var totaalWeken = Math.ceil(weken);
    var datum = new Date();
    datum.setDate(datum.getDate() + totaalWeken * 7);
    var maanden = ['jan', 'feb', 'mrt', 'apr', 'mei', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec'];
    datumEl.textContent = '\\u00b1 ' + datum.getDate() + ' ' + maanden[datum.getMonth()] + ' '
      + datum.getFullYear() + ' (over ' + totaalWeken + ' weken)';
  }

  [select, theorie, lessen, tempo].forEach(function(el) {
    el.addEventListener('input', bereken);
    el.addEventListener('change', bereken);
  });
})();
</script>
"""
    (out_dir / "planning.html").write_text(
        page("Wanneer haal ik mijn rijbewijs? Planningstool | rijexamenwachttijden.nl",
             "Bereken wanneer je je rijbewijs kunt halen op basis van de actuele "
             "wachttijd van jouw examenlocatie en je eigen lesplanning.", body,
             canonical="/planning.html"))


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
             "Methodologie en achtergrond van het CBR-wachttijden archief.", body,
             canonical="/over.html"))


SITE_URL = "https://rijexamenwachttijden.nl"


def build_sitemap(locations, out_dir):
    """Lists homepage, over.html, and every location page so Google can
    discover pages that aren't reachable purely by crawling links."""
    urls = [
        f"{SITE_URL}/",
        f"{SITE_URL}/over.html",
        f"{SITE_URL}/widgets.html",
        f"{SITE_URL}/kortste-wachttijden.html",
        f"{SITE_URL}/kosten-rijbewijs.html",
        f"{SITE_URL}/planning.html",
        f"{SITE_URL}/kennisbank/",
    ]
    for lslug in locations:
        urls.append(f"{SITE_URL}/locatie/{lslug}/")
    for entry in KENNISBANK:
        urls.append(f"{SITE_URL}/kennisbank/{entry['slug']}/")

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
        "\n"
        "# Explicitly welcomed AI answer-engine crawlers\n"
        "User-agent: GPTBot\n"
        "Allow: /\n"
        "\n"
        "User-agent: ClaudeBot\n"
        "Allow: /\n"
        "\n"
        "User-agent: PerplexityBot\n"
        "Allow: /\n"
        "\n"
        "User-agent: Google-Extended\n"
        "Allow: /\n"
        "\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n"
    )


def build_llms_txt(locations, out_dir):
    """A plain-text summary some AI crawlers use as a shortcut to understand
    site structure -- an emerging convention, cheap to maintain."""
    location_lines = "\n".join(
        f"- [{e['name']}]({SITE_URL}/locatie/{lslug}/)"
        for lslug, e in sorted(locations.items(), key=lambda t: t[1]["name"])
    )
    text = f"""# rijexamenwachttijden.nl

> Wekelijks gearchiveerde wachttijden voor het CBR-praktijkexamen, herexamen en
> theorie-examen, per examenlocatie in Nederland. CBR publiceert alleen de
> actuele week; dit archief bewaart elke wekelijkse publicatie apart sinds
> week 27, 2026, zodat de trend per locatie zichtbaar is.

Dit is geen officieel CBR-kanaal. Data afkomstig uit publiek gepubliceerde
CBR-wachttijden, wekelijks gearchiveerd.

## Belangrijke pagina's

- [Overzicht per provincie]({SITE_URL}/)
- [Kortste wachttijden]({SITE_URL}/kortste-wachttijden.html)
- [Kennisbank: alles over CBR-wachttijden]({SITE_URL}/kennisbank/)
- [Over dit archief \u2014 methodologie]({SITE_URL}/over.html)
- [Broncode & ruwe data (GitHub)](https://github.com/mansikapahi/cbr-wachttijden-archief)

## Examenlocaties

{location_lines}
"""
    (out_dir / "llms.txt").write_text(text)


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


def build_rss(locations, latest_by_exam, out_dir):
    """A lightweight RSS feed of the current snapshot -- lets aggregators and
    subscribers discover this site's updates without any outreach. Rebuilt
    fresh on every run, so it always reflects 'as of this archive run'."""
    import html
    from datetime import datetime, timezone
    from email.utils import format_datetime

    now = datetime.now(timezone.utc)
    build_date = format_datetime(now)

    items = []
    for lslug, entry in sorted(locations.items(), key=lambda t: t[1]["name"]):
        w = latest_by_exam.get("wanneer-praktijkexamen", {}).get(lslug)
        if w is None:
            continue
        title = html.escape(f"{entry['name']}: {w} weken wachttijd praktijkexamen")
        link = f"{SITE_URL}/locatie/{lslug}/"
        desc_bits = [f"Praktijkexamen: {w} weken."]
        wt = latest_by_exam.get("wanneer-theorie-examen", {}).get(lslug)
        if wt is not None:
            desc_bits.append(f"Theorie-examen: {wt} weken.")
        wh = latest_by_exam.get("wanneer-herexamen", {}).get(lslug)
        if wh is not None:
            desc_bits.append(f"Herexamen: {wh} weken.")
        description = html.escape(" ".join(desc_bits))
        items.append(f"""  <item>
    <title>{title}</title>
    <link>{link}</link>
    <guid isPermaLink="true">{link}</guid>
    <description>{description}</description>
    <pubDate>{build_date}</pubDate>
  </item>""")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>rijexamenwachttijden.nl &#8212; actuele wachttijden</title>
  <link>{SITE_URL}/</link>
  <description>Wekelijkse CBR-wachttijden per examenlocatie in Nederland.</description>
  <language>nl-nl</language>
  <lastBuildDate>{build_date}</lastBuildDate>
{chr(10).join(items)}
</channel>
</rss>
"""
    (out_dir / "feed.xml").write_text(xml)


def build_og_image(out_dir):
    """Copies a static Open Graph preview image into dist/ if present in the
    repo root. Missing file just means no OG image yet -- degrades
    gracefully like the optional rijscholen.json feature."""
    import shutil
    src = ROOT / "og-image.png"
    if src.exists():
        shutil.copy(src, out_dir / "og-image.png")


def main():
    DIST.mkdir(exist_ok=True)
    (DIST / "style.css").write_text(CSS)
    locations, latest_by_exam = load_history()
    rijscholen = load_rijscholen()
    build_homepage(locations, latest_by_exam, DIST)
    build_over_page(DIST)
    build_calculator_page(DIST)
    build_planning_page(DIST)
    build_ranking_page(locations, latest_by_exam, DIST)
    build_kennisbank_index(DIST)
    build_kennisbank_pages(DIST)
    for lslug, entry in locations.items():
        build_location_page(lslug, entry, DIST, rijscholen)
        build_location_csv(lslug, entry, DIST)
        build_widget(lslug, entry, DIST)
    build_widgets_page(locations, DIST)
    build_sitemap(locations, DIST)
    build_robots(DIST)
    build_llms_txt(locations, DIST)
    build_data_json(locations, latest_by_exam, DIST)
    build_rss(locations, latest_by_exam, DIST)
    build_og_image(DIST)
    print(f"Built {len(locations)} location pages + {len(locations)} widgets + "
          f"{len(KENNISBANK)} kennisbank pages + homepage + over.html + widgets.html + "
          f"data.json + sitemap.xml + robots.txt + feed.xml + llms.txt into dist/")


if __name__ == "__main__":
    main()
