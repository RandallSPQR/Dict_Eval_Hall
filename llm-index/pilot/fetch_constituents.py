#!/usr/bin/env python3
"""
Fetch a current S&P 500 constituent list (PILOT.md §5) and write
data/sp500_constituents.csv with columns ticker, name, gics_sector, plus
data/sp500_constituents.meta.json recording the source URL and fetch time.

The pilot needs this only for parsing. The frozen snapshot for the real run
is Randall's call. Standard library only (no pandas / bs4 in the pilot env).
"""
import csv
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
OUT_CSV = HERE / "data" / "sp500_constituents.csv"
OUT_META = HERE / "data" / "sp500_constituents.meta.json"
SOURCE_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def _cells(row_html):
    cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.S)
    return [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in cells]


def main():
    if OUT_CSV.exists() and "--force" not in sys.argv:
        print(f"{OUT_CSV} exists; pass --force to refetch")
        return
    r = requests.get(SOURCE_URL, headers={"User-Agent": "Mozilla/5.0 (llm-index pilot fetch)"}, timeout=60)
    r.raise_for_status()
    m = re.search(r'<table[^>]*id="constituents"[^>]*>(.*?)</table>', r.text, re.S)
    if not m:
        sys.exit("constituents table not found in page")
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(1), re.S)
    header = [h.lower() for h in _cells(rows[0])]
    i_sym = next(i for i, h in enumerate(header) if h.startswith("symbol"))
    i_name = next(i for i, h in enumerate(header) if h.startswith("security"))
    i_sec = next(i for i, h in enumerate(header) if h.startswith("gics sector"))
    out = []
    for row in rows[1:]:
        c = _cells(row)
        if len(c) <= max(i_sym, i_name, i_sec) or not c[i_sym]:
            continue
        out.append({"ticker": c[i_sym], "name": c[i_name], "gics_sector": c[i_sec]})
    if len(out) < 490:
        sys.exit(f"only {len(out)} rows parsed; page layout may have changed")
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ticker", "name", "gics_sector"])
        w.writeheader()
        w.writerows(out)
    meta = {
        "source_url": SOURCE_URL,
        "fetched_utc": datetime.now(timezone.utc).isoformat(),
        "n_rows": len(out),
        "sectors": sorted({o["gics_sector"] for o in out}),
        "note": "Pilot parsing snapshot only; not the frozen list for the real run.",
    }
    OUT_META.write_text(json.dumps(meta, indent=2) + "\n")
    print(f"wrote {len(out)} constituents to {OUT_CSV}")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
