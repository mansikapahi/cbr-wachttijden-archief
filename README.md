# CBR wachttijden archief

Weekly archive of the wait times ("wachttijden") that CBR publishes every
Monday for praktijkexamens, herexamens and theorie-examens, per examenlocatie.

CBR only shows the **current** week and overwrites it — no history exists
anywhere. This repo preserves every weekly snapshot: the raw PDF (evidence)
plus parsed JSON, and an append-only `data/history.csv` ready for charting.

## How it works
- `fetch_publitas.py` — resolves this week's PDF URL from the CBR Publitas
  viewer page and downloads it
- `parse_cbr_pdf.py` — extracts per-location week numbers from the PDF,
  pairing number badges to location labels by coordinates
- `archive.py` — orchestrates all publications, writes
  `data/<YYYY>-W<nn>/…`, appends `history.csv`, refreshes `latest.json`
- `.github/workflows/archive.yml` — runs it every Monday (Tuesday backstop)

Raw PDFs are always kept, even when parsing fails — reparse later, never
lose a week.

## Local test
    pip install -r requirements.txt
    python archive.py --local-pdf wanneer-praktijkexamen=path/to/file.pdf

## Data notes
- `cover_week`/`cover_period` = the week the data describes (from the PDF);
  `iso_week` = when it was fetched.
- Weeks value = "vanaf hoeveel weken zijn er voldoende examenplekken"
  (CBR's own definition, see PDF footnote) — not a guaranteed wait time.
- Source: CBR (public sector body), robots.txt allows all; fetched once
  per week with an identifying User-Agent.
