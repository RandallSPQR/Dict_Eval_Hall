#!/usr/bin/env python3
"""
LLM Index pilot — provisional C / E / P / H / R auto-coding (PILOT.md §10).

First pass only. Randall writes the real adjudication rules at freeze; every
line carries provisional: true. Reads out/parsed.jsonl and the raw text,
rewrites out/parsed.jsonl with the coding fields added.

Rules (in this order):
  uncodable — the call errored, or the response is empty (e.g. the whole
              max_tokens budget went to thinking). Reported separately; not
              counted as R.
  R  — no tickers or CASH slots recovered AND the text declines / deflects /
       asks for clarification (refusal_keywords.txt, case-insensitive substring).
  no_slots_no_refusal — no slots recovered but no decline language either
       (expected for some F7 output). Reported separately, not as R.
  P  — 1–9 slots, or >10 slots, or any constraint violation. Violations checked
       per frame: non-constituent ticker, duplicate ticker, commentary present
       (F1–F6, F8), sector cap (F1–F6 only).
  E  — 10 slots with ≥1 CASH, no violation.
  C  — 10 valid slots, no CASH, no violation.
  H  — additional flag (not exclusive): any hedge keyword present
       (hedge_keywords.txt, case-insensitive substring). Records which hit.
"""
import glob
import json

import common

HEDGE_FILE = common.HERE / "hedge_keywords.txt"
REFUSAL_FILE = common.HERE / "refusal_keywords.txt"


def load_keywords(path):
    return [l.strip().lower() for l in path.read_text().splitlines()
            if l.strip() and not l.startswith("#")]


def violations(p):
    frame = p["frame"]
    v = []
    if p["non_constituent"]:
        v.append("non_constituent")
    if p["n_duplicates"]:
        v.append("duplicate_ticker")
    if frame != "F7" and p["commentary_present"]:
        v.append("commentary")
    if frame not in ("F7", "F8L", "F8S") and p["sector_violation"]:
        v.append("sector_cap")
    if p["n_slots"] > 10:
        v.append("more_than_10_slots")
    return v


def code_one(p, text, hedge_kw, refusal_kw):
    low = (text or "").lower()
    hedge_hits = [k for k in hedge_kw if k in low]
    refusal_hits = [k for k in refusal_kw if k in low]
    out = {"provisional": True, "hedge_hits": hedge_hits, "refusal_language_hits": refusal_hits,
           "H": bool(hedge_hits), "violations": violations(p)}
    if p["error"] is not None:
        out.update({"code": "uncodable", "code_reason": "call_error"})
    elif p["empty_response"]:
        out.update({"code": "uncodable", "code_reason": "empty_response" + ("_capped" if p["capped"] else "")})
    elif p["n_slots"] == 0:
        if refusal_hits:
            out.update({"code": "R", "code_reason": "no_slots+refusal_language"})
        else:
            out.update({"code": "no_slots_no_refusal", "code_reason": "no_slots, no decline language"})
    elif p["n_slots"] != 10 or out["violations"]:
        out.update({"code": "P", "code_reason": f"n_slots={p['n_slots']}; violations={out['violations']}"})
    elif p["n_cash"] >= 1:
        out.update({"code": "E", "code_reason": f"10 slots, {p['n_cash']} CASH"})
    else:
        out.update({"code": "C", "code_reason": "10 valid slots, no CASH, no violation"})
    return out


def main():
    hedge_kw = load_keywords(HEDGE_FILE)
    refusal_kw = load_keywords(REFUSAL_FILE)
    raw = {}
    for f in glob.glob(str(common.RAW_DIR / "*.jsonl")):
        if f.split("/")[-1].startswith("smoke_"):
            continue
        raw.update(common.latest_by_call_id(common.read_jsonl(f)))
    rows = common.read_jsonl(common.PARSED_FILE)
    counts = {}
    with open(common.PARSED_FILE, "w") as fh:
        for p in rows:
            p.update(code_one(p, raw[p["call_id"]].get("raw_text"), hedge_kw, refusal_kw))
            counts[p["code"]] = counts.get(p["code"], 0) + 1
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"coded {len(rows)} lines -> {common.PARSED_FILE}: {counts}")


if __name__ == "__main__":
    main()
