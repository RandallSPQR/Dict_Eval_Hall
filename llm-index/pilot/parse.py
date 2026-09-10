#!/usr/bin/env python3
"""
LLM Index pilot — ticker extraction and constraint checks (PILOT.md §9).

Reads every line in out/raw/{slot}_*.jsonl (main run only; smoke files are
excluded), keeps the latest record per call_id, and writes one line per
call_id to out/parsed.jsonl.

Extraction rules (documented here because REPORT.md §4 depends on them):
  * A ticker is an uppercase string of 1–5 letters, optionally with a class
    suffix (BRK.B / BRK-B), matched against data/sp500_constituents.csv after
    normalising away "." and "-".  CASH is the cash token.
  * F6 (code): the first Python list literal (preferring `return [...]`) is
    parsed; its quoted strings, in order, are the slots.
  * Otherwise, ranked lines: a line starting with a rank ("1.", "1)", "#1",
    "| 1 |", "Rank 1", "Number one", "**Number Ten.**" …) opens a block that
    runs to the next ranked line (at most 4 lines).  The first constituent
    ticker or CASH in the block fills that rank; if none, the first other
    ticker-shaped token (not in a stop list) is recorded as a non-constituent
    slot.  Slots are ordered by the stated rank, not by appearance, so a
    count-down list parses correctly.
  * Fallback (no list literal, no ranked lines): constituents and CASH in
    order of appearance, single-letter tickers excluded.  Always `partial`.
  * Single-letter tickers (V, F, T, A, …) are accepted only when not followed
    by a lowercase word, so a sentence beginning "A …" is not Agilent.

parse_status:  ok      — structured extraction (list literal / ranked lines) with exactly 10 slots
               partial — structured with 1–9 or >10 slots, or any slots via fallback
               failed  — no slots
commentary_present: > N words outside the consumed slot lines / code block,
               N = parse.commentary_word_threshold in config.yaml (15).
               Not applied to F7 (no constraint block) → null.
sector_violation: any GICS sector > 2 among constituent slots; skipped (null)
               for F7 and F8 per §9.
"""
import csv
import glob
import json
import re
import sys

import common

NUMBER_WORDS = {w: i for i, w in enumerate(
    ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
     "eleven", "twelve", "thirteen", "fourteen", "fifteen"])}
TICKER_RE = re.compile(r"(?<![A-Za-z0-9])([A-Z]{1,5}(?:[./-][A-Z])?)(?![A-Za-z0-9])")
RANK_DIGIT_RE = re.compile(
    r"^\s*(?:[|>*_#\-–—]\s*)*(?:rank|no\.?|number|slot|pick|#)?\s*(\d{1,2})\s*(?:[.):|\-–—:]|\s)\s*(.*)$", re.I)
RANK_WORD_RE = re.compile(
    r"^\s*(?:[|>*_#\-–—]\s*)*(?:rank|number|no\.?|slot|pick)\s+(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen)\b[\s.:)\-–—*_]*(.*)$", re.I)
CODE_FENCE_RE = re.compile(r"```[a-zA-Z]*\n(.*?)```", re.S)
LIST_LITERAL_RE = re.compile(r"\[[^\[\]]*\]", re.S)
QUOTED_RE = re.compile(r"""["']([A-Z]{1,5}(?:[./-][A-Z])?)["']""")

STOPLIST = set("""
US USA AI ETF ETFS GICS S P SP SPX SPY QQQ CEO CFO CTO GDP IPO SEC FED FOMC EPS PE PEG YTD EV Q QOQ YOY
NASDAQ NYSE LLM LLMS API AWS GPU GPUS CPU CPUS OK TBD NA USD ROE ROIC FCF DCF RSI GLP GLPS TL DR TLDR FAQ
NOTE RANK TICKER LIST TOP BUY SELL HOLD SHORT LONG II III IV X XX AND THE OR OF IN TO BY FOR NOT NO YES
ONLY MAX MIN AVG USE PICK NAME SLOT CAP MID SMALL LARGE HTML JSON CSV URL ID IDS NB EG IE VS ETC
""".split())


def load_constituents():
    lookup, sector = {}, {}
    with open(common.CONSTITUENTS_CSV) as f:
        for row in csv.DictReader(f):
            t = row["ticker"].strip().upper()
            key = re.sub(r"[./-]", "", t)
            lookup[key] = t
            sector[t] = row["gics_sector"]
    return lookup, sector


def norm(tok):
    return re.sub(r"[./-]", "", tok.upper())


def candidates(text, lookup):
    """Yield (kind, canonical_value, span) for ticker-shaped tokens in text."""
    for m in TICKER_RE.finditer(text):
        tok = m.group(1)
        end = m.end()
        if tok == "CASH":
            yield "cash", "CASH", m.span()
            continue
        key = norm(tok)
        if len(key) == 1:
            after = text[end:end + 2]
            if re.match(r"\s[a-z]", after):   # "A giant …" is not Agilent
                continue
        if key in lookup:
            yield "constituent", lookup[key], m.span()
        elif tok not in STOPLIST and len(key) >= 2:
            yield "other", tok, m.span()


def pick_from_block(block, lookup):
    cons = [c for c in candidates(block, lookup) if c[0] in ("constituent", "cash")]
    if cons:
        # prefer multi-letter constituents over single letters and CASH-after-ticker ordering by position
        cons.sort(key=lambda c: (c[2][0]))
        return cons[0][0], cons[0][1]
    others = [c for c in candidates(block, lookup) if c[0] == "other"]
    if others:
        return "other", others[0][1]
    return None, None


def parse_ranked_lines(text, lookup):
    lines = text.splitlines()
    starts = []
    for i, line in enumerate(lines):
        m = RANK_DIGIT_RE.match(line)
        rank = None
        if m:
            rank = int(m.group(1))
        else:
            m = RANK_WORD_RE.match(line)
            if m:
                rank = NUMBER_WORDS[m.group(1).lower()]
        if rank is not None and 1 <= rank <= 15:
            starts.append((i, rank))
    slots, consumed = [], set()
    for j, (i, rank) in enumerate(starts):
        end = starts[j + 1][0] if j + 1 < len(starts) else min(len(lines), i + 4)
        end = min(end, i + 4)
        block = "\n".join(lines[i:end])
        kind, val = pick_from_block(block, lookup)
        if kind is None:
            continue
        slots.append({"rank": rank, "value": val, "kind": kind, "line": i})
        consumed.update(range(i, end))
    # order by stated rank; keep first occurrence of a rank
    seen, ordered = set(), []
    for s in sorted(slots, key=lambda s: (s["rank"], s["line"])):
        if s["rank"] in seen:
            continue
        seen.add(s["rank"])
        ordered.append(s)
    return ordered, consumed


def parse_code(text, lookup):
    """F6: quoted ticker strings inside the first list literal (prefer `return [...]`)."""
    m = re.search(r"return\s*(\[[^\[\]]*\])", text, re.S)
    lit = m.group(1) if m else None
    if lit is None:
        m = LIST_LITERAL_RE.search(text)
        lit = m.group(0) if m else None
    if lit is None:
        return [], None
    slots = []
    for k, q in enumerate(QUOTED_RE.findall(lit), 1):
        if q == "CASH":
            slots.append({"rank": k, "value": "CASH", "kind": "cash"})
        elif norm(q) in lookup:
            slots.append({"rank": k, "value": lookup[norm(q)], "kind": "constituent"})
        else:
            slots.append({"rank": k, "value": q, "kind": "other"})
    return slots, lit


def parse_fallback(text, lookup):
    seen, slots = set(), []
    for kind, val, span in candidates(text, lookup):
        if kind == "other" or len(norm(val)) == 1:
            continue
        if val in seen:
            continue
        seen.add(val)
        slots.append({"rank": len(slots) + 1, "value": val, "kind": kind})
    return slots


def word_count(s):
    return len([w for w in s.split() if re.search(r"[A-Za-z]", w)])


def parse_record(rec, lookup, sector, threshold):
    frame = rec["frame"]
    text = rec.get("raw_text") or ""
    out = {"call_id": rec["call_id"], "provider": rec["provider"], "model_string": rec["model_string"],
           "frame": frame, "sample_idx": rec["sample_idx"], "prompt_sha256": rec["prompt_sha256"],
           "error": rec.get("error"), "stop_reason": rec.get("stop_reason"),
           "capped": rec.get("stop_reason") in common.CAP_STOP_REASONS,
           "empty_response": not text.strip(), "chars": len(text)}
    if rec.get("error") is not None:
        out.update({"slots": [], "n_slots": 0, "n_cash": 0, "non_constituent": [], "n_duplicates": 0,
                    "sector_violation": None, "commentary_present": None, "commentary_words": None,
                    "parse_status": "failed", "method": "none"})
        return out

    method, slots, consumed_lines, code_literal = "none", [], set(), None
    if frame == "F6":
        slots, code_literal = parse_code(text, lookup)
        if slots:
            method = "code_literal"
    if not slots:
        slots, consumed_lines = parse_ranked_lines(text, lookup)
        if slots:
            method = "ranked_lines"
    if not slots:
        slots = parse_fallback(text, lookup)
        if slots:
            method = "fallback_scan"

    values = [s["value"] for s in slots]
    cons_vals = [s["value"] for s in slots if s["kind"] == "constituent"]
    non_con = [s["value"] for s in slots if s["kind"] == "other"]
    n_cash = sum(1 for s in slots if s["kind"] == "cash")
    n_dup = len(values) - len(set(values)) - max(0, n_cash - 1)   # CASH may legitimately repeat
    n_dup = max(0, n_dup)

    if frame in ("F7", "F8L", "F8S"):
        sector_violation = None
    else:
        counts = {}
        for v in cons_vals:
            counts[sector[v]] = counts.get(sector[v], 0) + 1
        sector_violation = any(c > 2 for c in counts.values())

    # commentary: words outside the consumed structure
    if frame == "F7":
        commentary_words, commentary_present = None, None
    else:
        if method == "code_literal":
            rest = CODE_FENCE_RE.sub("", text) if CODE_FENCE_RE.search(text) else text.replace(code_literal or "", "")
            rest = re.sub(r"def\s+build_index\s*\([^)]*\)\s*:.*", "", rest, flags=re.S) if "```" not in text else rest
            commentary_words = word_count(rest)
        elif method == "ranked_lines":
            rest = "\n".join(l for i, l in enumerate(text.splitlines()) if i not in consumed_lines)
            commentary_words = word_count(rest)
        else:
            commentary_words = word_count(text)
        commentary_present = commentary_words > threshold

    if method in ("code_literal", "ranked_lines"):
        status = "ok" if len(slots) == 10 else "partial"
    elif method == "fallback_scan":
        status = "partial"
    else:
        status = "failed"

    out.update({
        "slots": [{"rank": s["rank"], "value": s["value"]} for s in slots],
        "n_slots": len(slots), "n_cash": n_cash, "non_constituent": non_con, "n_duplicates": n_dup,
        "sector_violation": sector_violation,
        "commentary_present": commentary_present, "commentary_words": commentary_words,
        "parse_status": status, "method": method,
    })
    return out


def main():
    cfg = common.load_config()
    threshold = cfg["parse"]["commentary_word_threshold"]
    lookup, sector = load_constituents()
    files = sorted(f for f in glob.glob(str(common.RAW_DIR / "*.jsonl"))
                   if not f.split("/")[-1].startswith("smoke_"))
    rows = []
    for f in files:
        latest = common.latest_by_call_id(common.read_jsonl(f))
        for cid in sorted(latest):
            rows.append(parse_record(latest[cid], lookup, sector, threshold))
    common.OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(common.PARSED_FILE, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    by = {}
    for r in rows:
        by[r["parse_status"]] = by.get(r["parse_status"], 0) + 1
    print(f"parsed {len(rows)} call_ids from {len(files)} files -> {common.PARSED_FILE}: {by}")
    if "--show" in sys.argv:
        for r in rows:
            if r["error"] is None:
                print(r["call_id"], r["parse_status"], r["method"], r["n_slots"], [s["value"] for s in r["slots"]],
                      "cash", r["n_cash"], "nonc", r["non_constituent"], "sec", r["sector_violation"],
                      "comm", r["commentary_words"])


if __name__ == "__main__":
    main()
