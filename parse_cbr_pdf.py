"""Parse CBR 'wanneer examen' PDFs (Publitas weekly publications) into JSON.

Handles all three publication dialects (verified against week-27 documents):
  praktijkexamen : plain integer badges above location labels
  herexamen      : range badges ("1-4") + occasional integers; files may
                   contain stray leftover tokens from the design template
  theorie-examen : integer badges with a small 'wk' word beneath them,
                   an address list at the bottom (whose street numbers must
                   NOT be read as badges), and a national average on page 1

Core algorithm (badge-driven):
  1. find badge tokens: \\d{1,2} or \\d{1,2}-\\d{1,2}, size >= 15, inside the
     map zone; if the page uses 'wk' badges, require a 'wk' anchored beneath
  2. find label clusters (location names), size 15..23.5, merging multi-word
     and two-line names
  3. assign each badge to the nearest label BELOW it (max 150pt); if two
     badges claim one label, the closer wins and the loser is logged
"""

import re
import sys
import json

import pdfplumber

SIZE_HEADING = 24.0      # province chip (top of page)
HEADING_TOP_MAX = 90.0
SIZE_LABEL_MIN = 15.0
SIZE_LABEL_MAX = 23.5    # includes theorie's 'Examenlocatie(s)'/list rows
SIZE_VALUE_MIN = 15.0    # badges: 17.2 normal, 24 theorie, 42 highlighted
TITLE_TOP_MAX = 130.0    # repeated question-title zone
FOOT_TOP_MIN = 700.0     # footnote zone
MAX_PAIR_DIST = 150.0

VALUE_RE = re.compile(r"^\d{1,2}(-\d{1,2})?$")


def _center(w):
    return ((w["x0"] + w["x1"]) / 2.0, (w["top"] + w["bottom"]) / 2.0)


def _cluster_label_words(words):
    words = sorted(words, key=lambda w: (round(w["top"]), w["x0"]))
    lines = []
    for w in words:
        placed = False
        for line in lines:
            last = line[-1]
            if abs(w["top"] - last["top"]) <= 4 and 0 <= (w["x0"] - last["x1"]) <= 12:
                line.append(w)
                placed = True
                break
        if not placed:
            lines.append([w])
    line_objs = []
    for line in lines:
        line_objs.append({
            "text": " ".join(w["text"] for w in line),
            "x0": min(w["x0"] for w in line), "x1": max(w["x1"] for w in line),
            "top": min(w["top"] for w in line),
            "bottom": max(w["bottom"] for w in line)})
    line_objs.sort(key=lambda l: l["top"])
    merged = []
    for l in line_objs:
        target = None
        for m in merged:
            v_gap = l["top"] - m["bottom"]
            h_overlap = min(l["x1"], m["x1"]) - max(l["x0"], m["x0"])
            w_min = min(l["x1"] - l["x0"], m["x1"] - m["x0"])
            ratio = h_overlap / w_min if w_min > 0 else 0
            if -2 <= v_gap <= 14 and h_overlap > 0 and (
                    ratio >= 0.5 or l["text"][:1].islower()):
                target = m
                break
        if target:
            target["text"] += " " + l["text"]
            target["x0"] = min(target["x0"], l["x0"])
            target["x1"] = max(target["x1"], l["x1"])
            target["bottom"] = max(target["bottom"], l["bottom"])
        else:
            merged.append(dict(l))
    for m in merged:  # 'Venlo- Blerick' -> 'Venlo-Blerick'
        m["text"] = re.sub(r"-\s+", "-", m["text"])
    return merged


def parse_cover(page):
    text = page.extract_text() or ""
    meta = {}
    m = re.search(r"Stand week (\d{1,2})", text)
    if m:
        meta["week"] = int(m.group(1))
    m = re.search(r"(\d{1,2}\s+\w+)\s*-\s*(\d{1,2}\s+\w+)", text)
    if m:
        meta["period"] = f"{m.group(1)} - {m.group(2)}"
    for kind in ("Eerste examen", "Herexamen", "Theorie-examen"):
        if kind.lower() in text.lower():
            meta["exam"] = kind
            break
    if "landelijk" in text.lower():
        m = re.search(r"(\d{1,2}[.,]\d)", text)
        if m:
            meta["national_avg_weeks"] = float(m.group(1).replace(",", "."))
    return meta


def _value_of(token_text):
    """'7' -> 7 ; '1-4' -> '1-4' (kept verbatim, plus min/max derivable)."""
    if "-" in token_text:
        return token_text
    return int(token_text)


def parse_province_page(page, warnings):
    words = page.extract_words(extra_attrs=["size"])
    heading = [w for w in words
               if w["size"] >= SIZE_HEADING and w["top"] < HEADING_TOP_MAX
               and not VALUE_RE.match(w["text"])]
    province = " ".join(w["text"] for w in
                        sorted(heading, key=lambda w: w["x0"])) or None

    wk_tokens, values, label_words = [], [], []
    for w in words:
        if w["top"] < TITLE_TOP_MAX or w["top"] > FOOT_TOP_MIN:
            continue
        if w["text"] == "wk":
            wk_tokens.append(w)
        elif VALUE_RE.match(w["text"]) and w["size"] >= SIZE_VALUE_MIN:
            values.append(w)
        elif SIZE_LABEL_MIN <= w["size"] <= SIZE_LABEL_MAX and w["text"] != "*":
            label_words.append(w)

    if wk_tokens:  # theorie dialect: real badges have 'wk' anchored beneath
        anchored = []
        for v in values:
            vx, _ = _center(v)
            for wk in wk_tokens:
                wx, _ = _center(wk)
                if abs(wx - vx) <= 15 and -3 <= wk["top"] - v["bottom"] <= 25:
                    anchored.append(v)
                    break
        values = anchored

    labels = _cluster_label_words(label_words)
    # badge-driven assignment: nearest label below each badge; closest wins
    assignment = {}   # label-index -> (dist, badge)
    for v in values:
        vx, vy = _center(v)
        best_i, best_d = None, None
        for i, lab in enumerate(labels):
            if lab["top"] < v["bottom"] - 2:
                continue  # label must sit below the badge
            lx = (lab["x0"] + lab["x1"]) / 2.0
            d = ((lx - vx) ** 2 + (lab["top"] - vy) ** 2) ** 0.5
            if d <= MAX_PAIR_DIST and (best_d is None or d < best_d):
                best_i, best_d = i, d
        if best_i is None:
            warnings.append(f"{province}: badge '{v['text']}' "
                            f"at ({v['x0']:.0f},{v['top']:.0f}) unassigned")
            continue
        if best_i in assignment and assignment[best_i][0] <= best_d:
            warnings.append(
                f"{province}/{labels[best_i]['text']}: extra badge "
                f"'{v['text']}' ignored (kept closer one)")
            continue
        if best_i in assignment:
            old = assignment[best_i][1]
            warnings.append(
                f"{province}/{labels[best_i]['text']}: extra badge "
                f"'{old['text']}' ignored (kept closer one)")
        assignment[best_i] = (best_d, v)

    result = {labels[i]["text"]: _value_of(b["text"])
              for i, (_, b) in assignment.items()}
    return province, result


def parse_pdf(path):
    out = {"source_file": path.split("/")[-1], "cover": {}, "provinces": {},
           "locations": {}, "parse_warnings": []}
    with pdfplumber.open(path) as pdf:
        out["cover"] = parse_cover(pdf.pages[0])
        for page in pdf.pages[1:]:
            province, locs = parse_province_page(page, out["parse_warnings"])
            if not province:
                out["parse_warnings"].append(
                    f"page {page.page_number}: no province heading found")
                continue
            out["provinces"].setdefault(province, {}).update(locs)
            for name, weeks in locs.items():
                entry = {"province": province, "weeks": weeks}
                if isinstance(weeks, str) and "-" in weeks:
                    lo, hi = weeks.split("-")
                    entry["weeks_min"], entry["weeks_max"] = int(lo), int(hi)
                out["locations"][name] = entry
    return out


if __name__ == "__main__":
    print(json.dumps(parse_pdf(sys.argv[1]), indent=2, ensure_ascii=False))
