"""Rebuild one week's rows in data/history.csv from that week's JSONs.

The JSONs are authoritative (they hold the latest parse of the raw PDF).
Appending + dedupe keeps stale rows when a bad parse produced phantom
location names — this script fixes that by replacing ALL rows for the
given iso_week with rows regenerated from the JSONs.

Usage (from repo root):
  python3 rebuild_history_week.py 2026-W29
  python3 rebuild_history_week.py 2026-W29 2026-07-14   # explicit fetched_date
"""

import csv
import json
import sys
import datetime as dt
from pathlib import Path

DATA = Path(__file__).parent / "data"


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: rebuild_history_week.py <iso_week> [fetched_date]")
    week = sys.argv[1]
    fetched = sys.argv[2] if len(sys.argv) > 2 else dt.date.today().isoformat()

    hist = DATA / "history.csv"
    rows = list(csv.reader(hist.open()))
    header, body = rows[0], rows[1:]
    kept = [r for r in body if r[1] != week]
    dropped = len(body) - len(kept)

    rebuilt = []
    for js in sorted((DATA / week).glob("*.json")):
        rec = json.loads(js.read_text())
        if rec.get("parse_status") != "ok":
            print(f"  skipping {js.name}: parse_status={rec.get('parse_status')}")
            continue
        cover = rec.get("cover", {})
        for loc, info in rec.get("locations", {}).items():
            rebuilt.append([fetched, week, rec["slug"], cover.get("week"),
                            cover.get("period"), info["province"], loc,
                            info["weeks"]])

    with hist.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(kept + rebuilt)

    print(f"[rebuild] {week}: dropped {dropped} old rows, "
          f"wrote {len(rebuilt)} rows from JSONs, kept {len(kept)} other rows")


if __name__ == "__main__":
    main()
