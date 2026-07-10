"""Weekly archiver for CBR wachttijden publications.

For each publication:
  1. download the current PDF (raw evidence, kept forever)
  2. parse it into JSON
  3. write data/<YYYY>-W<week>/<slug>.pdf + <slug>.json
  4. append rows to data/history.csv (long format, chart-ready)
  5. refresh data/latest.json

Design rule: NEVER lose the raw PDF. If parsing fails, the PDF is still
committed and the failure is recorded in the JSON — we can re-parse later.

Usage:
  python archive.py                        # live run (fetch from Publitas)
  python archive.py --local-pdf slug=path  # offline test with a local PDF
"""

import csv
import json
import sys
import datetime as dt
from pathlib import Path

from parse_cbr_pdf import parse_pdf

PUBLICATIONS = [
    "wanneer-praktijkexamen",
    "wanneer-herexamen",
    "wanneer-theorie-examen",
]

DATA = Path(__file__).parent / "data"


def week_dir(today: dt.date) -> Path:
    iso = today.isocalendar()
    return DATA / f"{iso.year}-W{iso.week:02d}"


def append_history(rows):
    hist = DATA / "history.csv"
    new = not hist.exists()
    with hist.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["fetched_date", "iso_week", "publication",
                        "cover_week", "cover_period", "province",
                        "location", "weeks"])
        w.writerows(rows)


def dedupe_history():
    """Keep only the last record per (iso_week, publication, location) —
    makes reruns in the same week idempotent."""
    hist = DATA / "history.csv"
    if not hist.exists():
        return
    with hist.open() as f:
        rdr = list(csv.reader(f))
    header, body = rdr[0], rdr[1:]
    seen = {}
    for row in body:
        seen[(row[1], row[2], row[6])] = row   # iso_week, publication, location
    with hist.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(seen.values())


def run(local_pdfs=None):
    today = dt.date.today()
    iso = today.isocalendar()
    iso_week = f"{iso.year}-W{iso.week:02d}"
    wdir = week_dir(today)
    wdir.mkdir(parents=True, exist_ok=True)

    latest = {"fetched_date": today.isoformat(), "iso_week": iso_week,
              "publications": {}}
    rows = []
    failures = []

    for slug in PUBLICATIONS:
        pdf_path = wdir / f"{slug}.pdf"
        record = {"slug": slug, "parse_status": "ok"}
        try:
            if local_pdfs and slug in local_pdfs:
                import shutil
                shutil.copy(local_pdfs[slug], pdf_path)
                record["source_url"] = f"local:{local_pdfs[slug]}"
            elif local_pdfs is not None:
                continue   # offline test: skip slugs without a local file
            else:
                from fetch_publitas import fetch_pdf
                record["source_url"] = fetch_pdf(slug, str(pdf_path))
        except Exception as e:
            record["parse_status"] = f"fetch_failed: {e}"
            failures.append(slug)
            latest["publications"][slug] = record
            continue

        try:
            parsed = parse_pdf(str(pdf_path))
            record.update(parsed)
            (wdir / f"{slug}.json").write_text(
                json.dumps(record, indent=2, ensure_ascii=False))
            for loc, info in parsed["locations"].items():
                rows.append([today.isoformat(), iso_week, slug,
                             parsed["cover"].get("week"),
                             parsed["cover"].get("period"),
                             info["province"], loc, info["weeks"]])
        except Exception as e:
            record["parse_status"] = f"parse_failed: {e}"
            failures.append(slug)
            (wdir / f"{slug}.json").write_text(
                json.dumps(record, indent=2, ensure_ascii=False))
        latest["publications"][slug] = {
            k: record.get(k) for k in
            ("slug", "parse_status", "source_url", "cover")}

    if rows:
        append_history(rows)
        dedupe_history()
    (DATA / "latest.json").write_text(
        json.dumps(latest, indent=2, ensure_ascii=False))

    print(f"[archive] {iso_week}: "
          f"{len(rows)} location rows, failures: {failures or 'none'}")
    # Non-zero exit only if EVERYTHING failed (so partial success still commits)
    if failures and len(failures) == len(PUBLICATIONS):
        sys.exit(1)


if __name__ == "__main__":
    local = None
    for arg in sys.argv[1:]:
        if arg.startswith("--local-pdf"):
            local = local or {}
            slug, path = arg.split(maxsplit=1)[0].removeprefix("--local-pdf="), None
        if "=" in arg and not arg.startswith("--"):
            s, p = arg.split("=", 1)
            local = local or {}
            local[s] = p
    run(local_pdfs=local)
