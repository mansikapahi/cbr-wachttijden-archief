"""Verify a weekly run of the CBR wachttijden archiver.

Checks the things a green CI run does NOT prove:
  - all three publications fetched AND parsed ("parse_status": "ok")
  - the fetched publication is actually fresh (cover week vs fetch week)
  - each publication produced a plausible number of location rows
  - location sets are stable vs the previous week (diff printed)
  - weeks values are sane (0..30; ranges only where expected)
  - history.csv actually grew for this iso_week
  - parse warnings are surfaced for human eyes

Usage (from repo root, after the Monday run has committed):
  python verify_week.py                 # verifies current ISO week vs previous
  python verify_week.py 2026-W29        # verify a specific week
Exit code 0 = all good, 1 = at least one FAIL (warnings don't fail).
"""

import csv
import json
import re
import sys
import datetime as dt
from pathlib import Path

DATA = Path(__file__).parent / "data"

PUBLICATIONS = [
    "wanneer-praktijkexamen",
    "wanneer-herexamen",
    "wanneer-theorie-examen",
]

# Publications where range values like "1-4" are legitimate
RANGE_OK = {"wanneer-herexamen"}

# Sanity bounds for a weeks value
WEEKS_MIN, WEEKS_MAX = 0, 30

# If a publication's location count moves more than this vs last week, flag it
MAX_COUNT_DRIFT = 3

VALUE_RE = re.compile(r"^\d{1,2}(-\d{1,2})?$")

fails, warns = [], []


def fail(msg):
    fails.append(msg)
    print(f"  FAIL  {msg}")


def warn(msg):
    warns.append(msg)
    print(f"  warn  {msg}")


def ok(msg):
    print(f"  ok    {msg}")


def iso_week_str(date=None):
    iso = (date or dt.date.today()).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def prev_iso_week_str(week_str):
    year, wk = int(week_str[:4]), int(week_str[6:])
    monday = dt.date.fromisocalendar(year, wk, 1) - dt.timedelta(weeks=1)
    return iso_week_str(monday)


def load_week_jsons(week_str):
    out = {}
    wdir = DATA / week_str
    for slug in PUBLICATIONS:
        p = wdir / f"{slug}.json"
        if p.exists():
            out[slug] = json.loads(p.read_text())
    return out


def check_files(week_str):
    print(f"\n[1] Files in data/{week_str}/")
    wdir = DATA / week_str
    if not wdir.exists():
        fail(f"week directory data/{week_str}/ does not exist — did the run happen?")
        return
    for slug in PUBLICATIONS:
        pdf, js = wdir / f"{slug}.pdf", wdir / f"{slug}.json"
        if not pdf.exists():
            fail(f"{slug}.pdf missing (raw evidence not preserved!)")
        elif pdf.stat().st_size < 10_000:
            fail(f"{slug}.pdf suspiciously small ({pdf.stat().st_size} bytes)")
        else:
            ok(f"{slug}.pdf present ({pdf.stat().st_size//1024} KB)")
        if not js.exists():
            fail(f"{slug}.json missing")


def check_parse_status(jsons):
    print("\n[2] Parse status per publication")
    for slug in PUBLICATIONS:
        rec = jsons.get(slug)
        if rec is None:
            fail(f"{slug}: no JSON record")
            continue
        status = rec.get("parse_status", "?")
        if status == "ok":
            n = len(rec.get("locations", {}))
            if n == 0:
                fail(f"{slug}: parse_status ok but 0 locations — "
                     f"layout change? (silent-empty trap)")
            else:
                ok(f"{slug}: ok, {n} locations, "
                   f"cover week {rec.get('cover', {}).get('week')}")
        else:
            fail(f"{slug}: {status}")
        for w in rec.get("parse_warnings", []):
            warn(f"{slug}: {w}")


def check_freshness(week_str, jsons):
    """CBR does not always publish weekly. A stale cover week is CBR's
    behavior (worth recording loudly), not a pipeline failure — so warn,
    don't fail. A red CI should mean OUR pipeline broke."""
    print("\n[2b] Publication freshness")
    fetch_week = int(week_str[6:])
    for slug, rec in jsons.items():
        cover = rec.get("cover", {}).get("week")
        if cover is None:
            warn(f"{slug}: no cover week parsed")
        elif fetch_week - cover >= 2:
            warn(f"{slug}: STALE — cover says week {cover}, fetched in week "
                 f"{fetch_week}; CBR has not published for "
                 f"{fetch_week - cover} week(s)")
        elif fetch_week - cover == 1:
            ok(f"{slug}: cover week {cover} (normal 1-week lag)")
        else:
            ok(f"{slug}: cover week {cover}, current")


def check_values(jsons):
    print("\n[3] Value sanity")
    for slug, rec in jsons.items():
        for loc, info in rec.get("locations", {}).items():
            v = info.get("weeks")
            sv = str(v)
            if not VALUE_RE.match(sv):
                fail(f"{slug}/{loc}: weeks value {v!r} has unexpected shape")
                continue
            if "-" in sv:
                if slug not in RANGE_OK:
                    warn(f"{slug}/{loc}: range value {sv!r} in a publication "
                         f"that normally has plain integers")
                lo, hi = (int(x) for x in sv.split("-"))
                if not (WEEKS_MIN <= lo <= hi <= WEEKS_MAX):
                    fail(f"{slug}/{loc}: range {sv!r} out of bounds")
            else:
                if not (WEEKS_MIN <= int(sv) <= WEEKS_MAX):
                    fail(f"{slug}/{loc}: value {sv} outside "
                         f"[{WEEKS_MIN},{WEEKS_MAX}]")
    ok("value scan complete")


def check_vs_previous(week_str, jsons):
    prev_str = prev_iso_week_str(week_str)
    print(f"\n[4] Comparison vs previous week ({prev_str})")
    prev = load_week_jsons(prev_str)
    if not prev:
        warn(f"no data for {prev_str}; skipping diff (first weeks of archive)")
        return
    for slug in PUBLICATIONS:
        cur_locs = set(jsons.get(slug, {}).get("locations", {}))
        old_locs = set(prev.get(slug, {}).get("locations", {}))
        if not cur_locs or not old_locs:
            continue
        added, dropped = cur_locs - old_locs, old_locs - cur_locs
        drift = abs(len(cur_locs) - len(old_locs))
        if drift > MAX_COUNT_DRIFT:
            fail(f"{slug}: location count moved {len(old_locs)} -> "
                 f"{len(cur_locs)} (> {MAX_COUNT_DRIFT}); parser or layout issue?")
        if added:
            warn(f"{slug}: new locations vs last week: {sorted(added)}")
        if dropped:
            warn(f"{slug}: locations disappeared vs last week: {sorted(dropped)}")
        if not added and not dropped:
            ok(f"{slug}: location set identical ({len(cur_locs)})")
        # big single-location jumps are usually parser mispairs, worth eyes
        for loc in cur_locs & old_locs:
            a = str(prev[slug]["locations"][loc]["weeks"])
            b = str(jsons[slug]["locations"][loc]["weeks"])
            if "-" in a or "-" in b:
                continue
            if abs(int(a) - int(b)) >= 6:
                warn(f"{slug}/{loc}: jumped {a} -> {b} weken; "
                     f"check against the raw PDF")


def check_history(week_str, jsons):
    print("\n[5] history.csv")
    hist = DATA / "history.csv"
    if not hist.exists():
        fail("history.csv missing")
        return
    per_pub = {}
    with hist.open() as f:
        rdr = csv.reader(f)
        header = next(rdr, None)
        for row in rdr:
            if len(row) < 8:
                warn(f"malformed history row: {row}")
                continue
            if row[1] == week_str:
                per_pub[row[2]] = per_pub.get(row[2], 0) + 1
    for slug in PUBLICATIONS:
        expected = len(jsons.get(slug, {}).get("locations", {}))
        got = per_pub.get(slug, 0)
        if expected and got != expected:
            fail(f"{slug}: {got} history rows for {week_str}, "
                 f"but JSON has {expected} locations")
        elif expected:
            ok(f"{slug}: {got} rows in history.csv")
        else:
            warn(f"{slug}: no rows (parse failed or empty)")


def main():
    week_str = sys.argv[1] if len(sys.argv) > 1 else iso_week_str()
    print(f"Verifying {week_str} against {prev_iso_week_str(week_str)}")
    check_files(week_str)
    jsons = load_week_jsons(week_str)
    check_parse_status(jsons)
    check_freshness(week_str, jsons)
    check_values(jsons)
    check_vs_previous(week_str, jsons)
    check_history(week_str, jsons)
    print(f"\nResult: {len(fails)} fail(s), {len(warns)} warning(s)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

