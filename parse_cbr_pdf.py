"""Parse CBR 'wanneer examen' PDFs (Publitas weekly publications) into JSON.

Structure of the PDFs (praktijkexamen / herexamen, and similar for theorie):
  page 1     : national map + legend ("Eerste examen", "Stand week 27", "29 juni - 5 juli")
  pages 2..N : one province each; heading (size ~27), location labels (size ~18)
               and week-number badges (size ~17) drawn above each location.

The text layer's *sequence* does not pair numbers with names reliably, so we
pair by coordinates: each badge number is the nearest number ABOVE the label.
"""

import re
import sys
import json

import pdfplumber

# Font-size bands observed in CBR PDFs (points, with tolerance)
SIZE_HEADING = 24.0    # province name / big title: >= this
SIZE_LABEL_MIN = 15.0  # location labels ~18, badges ~17.2
SIZE_LABEL_MAX = 23.0
TITLE_TOP_MAX = 130.0  # the repeated question-title lives above this line
FOOT_TOP_MIN = 700.0   # footnote boilerplate lives below this line

NUM_RE = re.compile(r"^\d{1,2}$")


def _mid(w):
    return ((w["x0"] + w["x1"]) / 2.0, (w["top"] + w["bottom"]) / 2.0)


def _cluster_label_words(words):
    """Group label words into location names (handles 'Den Bosch',
    'Bergen\\nop Zoom', hyphenated single tokens, etc.)."""
    words = sorted(words, key=lambda w: (round(w["top"]), w["x0"]))
    # 1) merge words on the same visual line
    lines = []
    for w in words:
        placed = False
        for line in lines:
            last = line[-1]
            same_row = abs(w["top"] - last["top"]) <= 4
            close_x = 0 <= (w["x0"] - last["x1"]) <= 12
            if same_row and close_x:
                line.append(w)
                placed = True
                break
        if not placed:
            lines.append([w])
    line_objs = []
    for line in lines:
        text = " ".join(w["text"] for w in line)
        x0 = min(w["x0"] for w in line)
        x1 = max(w["x1"] for w in line)
        top = min(w["top"] for w in line)
        bottom = max(w["bottom"] for w in line)
        line_objs.append({"text": text, "x0": x0, "x1": x1,
                          "top": top, "bottom": bottom})
    # 2) merge vertically stacked lines that overlap horizontally
    #    (e.g. 'Bergen' / 'op Zoom') into one label
    line_objs.sort(key=lambda l: l["top"])
    merged = []
    for l in line_objs:
        target = None
        for m in merged:
            v_gap = l["top"] - m["bottom"]
            h_overlap = min(l["x1"], m["x1"]) - max(l["x0"], m["x0"])
            w_min = min(l["x1"] - l["x0"], m["x1"] - m["x0"])
            ratio = h_overlap / w_min if w_min > 0 else 0
            starts_lower = l["text"][:1].islower()
            if -2 <= v_gap <= 14 and h_overlap > 0 and (ratio >= 0.5 or starts_lower):
                target = m
                break
        if target:
            target["text"] += " " + l["text"]
            target["x0"] = min(target["x0"], l["x0"])
            target["x1"] = max(target["x1"], l["x1"])
            target["bottom"] = max(target["bottom"], l["bottom"])
        else:
            merged.append(dict(l))
    return merged


def parse_cover(page):
    """Extract exam type, week number and date range from page 1."""
    text = page.extract_text() or ""
    meta = {}
    m = re.search(r"Stand week (\d{1,2})", text)
    if m:
        meta["week"] = int(m.group(1))
    m = re.search(r"(\d{1,2}\s+\w+)\s*-\s*(\d{1,2}\s+\w+)", text)
    if m:
        meta["period"] = f"{m.group(1)} - {m.group(2)}"
    for kind in ("Eerste examen", "Herexamen", "Theorie-examen", "Theorie examen"):
        if kind.lower() in text.lower():
            meta["exam"] = kind
            break
    return meta


def parse_province_page(page):
    """Return (province, {location: weeks}) for one province page."""
    words = page.extract_words(extra_attrs=["size"])
    heading = [w for w in words if w["size"] >= SIZE_HEADING and not NUM_RE.match(w["text"])]
    province = " ".join(w["text"] for w in sorted(heading, key=lambda w: w["x0"])) or None

    mids = []       # number badges
    label_words = []
    for w in words:
        if w["top"] < TITLE_TOP_MAX or w["top"] > FOOT_TOP_MIN:
            continue  # title question / footnote boilerplate
        if NUM_RE.match(w["text"]) and w["size"] >= SIZE_LABEL_MIN:
            mids.append(w)   # badge numbers, incl. enlarged 'highlight' badges
        elif (SIZE_LABEL_MIN <= w["size"] <= SIZE_LABEL_MAX
              and w["text"] not in {"*"}):
            label_words.append(w)

    labels = _cluster_label_words(label_words)
    result = {}
    for lab in labels:
        lx = (lab["x0"] + lab["x1"]) / 2.0
        ly = lab["top"]
        best, best_d = None, None
        for n in mids:
            nx, ny = _mid(n)
            if ny >= ly + 4:      # badge must sit above the label
                continue
            d = ((nx - lx) ** 2 + (ny - ly) ** 2) ** 0.5
            if best_d is None or d < best_d:
                best, best_d = n, d
        if best is not None:
            result[lab["text"]] = int(best["text"])
        else:
            result[lab["text"]] = None
    return province, result


def parse_pdf(path):
    out = {"source_file": path.split("/")[-1], "cover": {}, "provinces": {},
           "locations": {}, "parse_warnings": []}
    with pdfplumber.open(path) as pdf:
        out["cover"] = parse_cover(pdf.pages[0])
        for page in pdf.pages[1:]:
            province, locs = parse_province_page(page)
            if not province:
                out["parse_warnings"].append(
                    f"page {page.page_number}: no province heading found")
                continue
            out["provinces"][province] = locs
            for name, weeks in locs.items():
                out["locations"][name] = {"province": province, "weeks": weeks}
                if weeks is None:
                    out["parse_warnings"].append(
                        f"{province}/{name}: no number matched")
    return out


if __name__ == "__main__":
    data = parse_pdf(sys.argv[1])
    print(json.dumps(data, indent=2, ensure_ascii=False))
