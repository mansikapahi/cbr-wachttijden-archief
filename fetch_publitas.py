"""Fetch the current weekly PDF for a CBR Publitas publication.

The viewer page embeds a JSON blob containing "downloadPdfUrl" — the UUID
changes every week, so we resolve it fresh on each run.
"""

import re
import sys

import requests

BASE = "https://view.publitas.com/cbr/{slug}/"
UA = ("cbr-wachttijden-archief/1.0 "
      "(non-commercial weekly archive of public CBR data; contact: see repo)")


def resolve_pdf_url(slug: str) -> str:
    html = requests.get(BASE.format(slug=slug), headers={"User-Agent": UA},
                        timeout=30).text
    m = re.search(r'"downloadPdfUrl"\s*:\s*"([^"]+)"', html)
    if not m:
        raise RuntimeError(f"{slug}: downloadPdfUrl not found in viewer HTML")
    url = m.group(1).replace("\\u0026", "&").replace("\\/", "/")
    return url


def fetch_pdf(slug: str, dest_path: str) -> str:
    url = resolve_pdf_url(slug)
    r = requests.get(url, headers={"User-Agent": UA}, timeout=60)
    r.raise_for_status()
    if not r.content.startswith(b"%PDF"):
        raise RuntimeError(f"{slug}: response is not a PDF ({len(r.content)} bytes)")
    with open(dest_path, "wb") as f:
        f.write(r.content)
    return url


if __name__ == "__main__":
    slug = sys.argv[1] if len(sys.argv) > 1 else "wanneer-praktijkexamen"
    print(resolve_pdf_url(slug))
