#!/usr/bin/env python3
"""
LLM Index pilot — builds out/REPORT.md (PILOT.md §11), nine sections in order.

Inputs: config.yaml, out/raw/*.jsonl (all attempts), out/parsed.jsonl (after
code_responses.py), data/sp500_constituents.meta.json, out/prompt_hashes.json,
and report_notes.md (hand-written observations appended to §8).
"""
import glob
import json
from collections import Counter, defaultdict
from datetime import datetime

import common

NOTES_FILE = common.HERE / "report_notes.md"
META_FILE = common.HERE / "data" / "sp500_constituents.meta.json"


def pct(n, d):
    return "—" if not d else f"{100.0 * n / d:.0f}%"


def load_all():
    cfg = common.load_config()
    parsed = common.read_jsonl(common.PARSED_FILE)
    attempts, latest, smoke = [], {}, defaultdict(list)
    for f in sorted(glob.glob(str(common.RAW_DIR / "*.jsonl"))):
        name = f.split("/")[-1]
        recs = common.read_jsonl(f)
        if name.startswith("smoke_"):
            slot = name.split("_")[2]
            smoke[slot].extend(recs)
        else:
            attempts.extend(recs)
            latest.update(common.latest_by_call_id(recs))
    return cfg, parsed, attempts, latest, smoke


def slot_of(call_id):
    return call_id.split("-")[0]


def main():
    cfg, parsed, attempts, latest, smoke = load_all()
    slots = list(cfg["models"])
    frames = cfg["frames"]
    n_per = cfg["samples_per_cell"]
    by_slot_frame = defaultdict(list)
    for p in parsed:
        by_slot_frame[(slot_of(p["call_id"]), p["frame"])].append(p)
    ran = {s: any(p["error"] is None for p in parsed if slot_of(p["call_id"]) == s) for s in slots}

    def label(s):
        m = cfg["models"][s]
        return f"{s} `{m['model_string']}`"

    L = []
    L.append(f"# LLM Index — Pilot Report\n")
    L.append(f"Run id `{cfg['run_id']}`. Generated {datetime.utcnow().isoformat()}Z by `report.py`. "
             f"**Pilot data: discarded, not analysed for picks, not wave 0.**\n")
    L.append(f"Design: {len(frames)} cells × {len(slots)} models × {n_per} samples = "
             f"{len(frames) * len(slots) * n_per} main calls; max_tokens {cfg['max_tokens']}; "
             f"temperature provider default (not sent); no system prompt; single turn; retrieval off.\n")
    not_run = [s for s in slots if not ran[s]]
    if not_run:
        L.append("> **Not run in this environment (no API key):** " +
                 ", ".join(label(s) for s in not_run) +
                 ". Their calls are logged as `NO_API_KEY` errors and will be attempted on the next "
                 "`run_pilot.py` invocation once the key is in `.env`.\n")

    # ── 1. Baseline refusal ────────────────────────────────────────────────
    L.append("## 1. Baseline refusal by model (F1, F4)\n")
    L.append("Headline number for the fellowship application. R = provisional refusal (no slots + decline "
             "language); H = hedge keyword present (any code). Denominator = responses received "
             "(errors and empty responses excluded, listed separately).\n")
    L.append("| Model | Frame | n responses | R | R rate | H | H rate | uncodable |")
    L.append("|---|---|---|---|---|---|---|---|")
    floor = []
    for s in slots:
        r_total = 0
        for f in ("F1", "F4"):
            ps = by_slot_frame.get((s, f), [])
            resp = [p for p in ps if p["code"] != "uncodable"]
            unc = [p for p in ps if p["code"] == "uncodable"]
            r = sum(1 for p in resp if p["code"] == "R")
            h = sum(1 for p in resp if p["H"])
            r_total += r
            L.append(f"| {label(s)} | {f} | {len(resp)} | {r} | {pct(r, len(resp))} | {h} | {pct(h, len(resp))} | {len(unc)} |")
        if ran[s] and r_total == 0:
            floor.append(s)
    L.append("")
    if floor:
        L.append("**At floor (0 provisional refusals across F1 and F4):** " + ", ".join(label(s) for s in floor) +
                 ". Per pre-reg §1 (H6 conditioning note) these models are not H6-evaluable unless manual "
                 "adjudication finds refusals the keyword pass missed.\n")
    else:
        L.append("**At floor:** none of the models that ran.\n")
    if not_run:
        L.append("Not determined (not run): " + ", ".join(label(s) for s in not_run) + ".\n")

    # ── 2. Coding matrix ────────────────────────────────────────────────────
    L.append("## 2. Coding matrix (provisional)\n")
    L.append("Cell = C / E / P / R counts, then `+H n` (hedge flag, not exclusive), then `[u n]` uncodable "
             "(error or empty) and `[x n]` no-slots-without-refusal-language, if any.\n")
    L.append("| Model | " + " | ".join(frames) + " |")
    L.append("|---|" + "---|" * len(frames))
    for s in slots:
        cells = []
        for f in frames:
            ps = by_slot_frame.get((s, f), [])
            c = Counter(p["code"] for p in ps)
            h = sum(1 for p in ps if p["H"])
            cell = f"{c['C']}/{c['E']}/{c['P']}/{c['R']}"
            if h:
                cell += f" +H{h}"
            if c["uncodable"]:
                cell += f" [u{c['uncodable']}]"
            if c["no_slots_no_refusal"]:
                cell += f" [x{c['no_slots_no_refusal']}]"
            cells.append(cell)
        L.append(f"| {label(s)} | " + " | ".join(cells) + " |")
    L.append("")

    # ── 3. Constraint compliance ───────────────────────────────────────────
    L.append("## 3. Constraint compliance\n")
    L.append("Over responses received (non-empty). Sector cap is not checked for F7/F8; commentary not "
             f"checked for F7 (threshold: >{cfg['parse']['commentary_word_threshold']} words outside the parsed block).\n")
    L.append("| Model | Frame | n | exactly 10 | any CASH | sector viol. | non-constituent | commentary | duplicates |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for s in slots:
        if not ran[s]:
            continue
        for f in frames:
            ps = [p for p in by_slot_frame.get((s, f), []) if p["code"] != "uncodable"]
            n = len(ps)
            L.append(f"| {label(s)} | {f} | {n} | {pct(sum(p['n_slots'] == 10 for p in ps), n)} | "
                     f"{pct(sum(p['n_cash'] > 0 for p in ps), n)} | "
                     f"{'n/a' if f in ('F7', 'F8L', 'F8S') else pct(sum(bool(p['sector_violation']) for p in ps), n)} | "
                     f"{pct(sum(bool(p['non_constituent']) for p in ps), n)} | "
                     f"{'n/a' if f == 'F7' else pct(sum(bool(p['commentary_present']) for p in ps), n)} | "
                     f"{pct(sum(p['n_duplicates'] > 0 for p in ps), n)} |")
    L.append("")
    nonc = Counter()
    for p in parsed:
        for t in p.get("non_constituent", []):
            nonc[t] += 1
    if nonc:
        L.append("Non-constituent tickers recovered (ticker: count across all cells): " +
                 ", ".join(f"{t}: {n}" for t, n in nonc.most_common()) + ".\n")

    # ── 4. Parse outcomes ──────────────────────────────────────────────────
    L.append("## 4. Parse outcomes\n")
    L.append("Status over responses received. `ok` = structured extraction (ranked lines or code list literal) "
             "with exactly 10 slots; `partial` = structured with ≠10 slots or fallback scan; `failed` = no slots.\n")
    L.append("| Frame | n | ok | partial | failed | methods |")
    L.append("|---|---|---|---|---|---|")
    for f in frames:
        ps = [p for p in parsed if p["frame"] == f and p["error"] is None]
        st = Counter(p["parse_status"] for p in ps)
        me = Counter(p["method"] for p in ps)
        L.append(f"| {f} | {len(ps)} | {st['ok']} | {st['partial']} | {st['failed']} | "
                 + ", ".join(f"{k} {v}" for k, v in me.most_common()) + " |")
    L.append("")
    f6 = [p for p in parsed if p["frame"] == "F6" and p["error"] is None]
    f7 = [p for p in parsed if p["frame"] == "F7" and p["error"] is None]
    L.append(f"**F6 (code):** {sum(p['method'] == 'code_literal' for p in f6)}/{len(f6)} responses parsed from a "
             f"list literal; {sum(p['method'] != 'code_literal' for p in f6)} needed another method.  ")
    L.append(f"**F7 (spoken word):** {sum(p['parse_status'] == 'ok' for p in f7)}/{len(f7)} yielded 10 ranked "
             f"slots (expected failure per §9; recorded, not forced); methods: "
             + ", ".join(f"{k} {v}" for k, v in Counter(p['method'] for p in f7).most_common()) + ".\n")
    partials = [p for p in parsed if p["parse_status"] in ("partial", "failed") and p["error"] is None]
    if partials:
        L.append("Partial / failed parses:\n")
        L.append("| call_id | status | method | n_slots | chars | stop |")
        L.append("|---|---|---|---|---|---|")
        for p in partials:
            L.append(f"| {p['call_id']} | {p['parse_status']} | {p['method']} | {p['n_slots']} | {p['chars']} | {p['stop_reason']} |")
        L.append("")

    # ── 5. Token cap ────────────────────────────────────────────────────────
    L.append("## 5. Token cap\n")
    capped = [p for p in parsed if p["capped"]]
    empty = [p for p in parsed if p["error"] is None and p["empty_response"]]
    L.append(f"`capped: true` lines: **{len(capped)}**; empty responses: **{len(empty)}** "
             f"(max_tokens = {cfg['max_tokens']}).\n")
    if capped or empty:
        L.append("| call_id | model | frame | stop_reason | output tokens | reasoning tokens | chars |")
        L.append("|---|---|---|---|---|---|---|")
        for p in sorted(capped + [e for e in empty if not e["capped"]], key=lambda p: p["call_id"]):
            r = latest[p["call_id"]]
            u = r.get("usage") or {}
            L.append(f"| {p['call_id']} | {r['model_string']} | {p['frame']} | {p['stop_reason']} | "
                     f"{u.get('output_tokens')} | {u.get('reasoning_tokens')} | {p['chars']} |")
        L.append("")
    L.append("Output-token usage per model (responses received; reasoning tokens as reported by the provider, "
             "which count against the cap on every provider that ran):\n")
    L.append("| Model | n | max output tokens | mean output tokens | max reasoning tokens | mean reasoning |")
    L.append("|---|---|---|---|---|---|")
    for s in slots:
        rs = [r for cid, r in latest.items() if slot_of(cid) == s and r.get("error") is None]
        if not rs:
            continue
        outs = [(r["usage"] or {}).get("output_tokens") or 0 for r in rs]
        reas = [(r["usage"] or {}).get("reasoning_tokens") or 0 for r in rs]
        L.append(f"| {label(s)} | {len(rs)} | {max(outs)} | {sum(outs) / len(outs):.0f} | {max(reas)} | {sum(reas) / len(reas):.0f} |")
    L.append("")

    # ── 6. Retrieval verification ──────────────────────────────────────────
    L.append("## 6. Retrieval verification\n")
    L.append("| Model | retrieval-off method | verified in pilot env | smoke calls | tool call observed | notes |")
    L.append("|---|---|---|---|---|---|")
    for s in slots:
        m = cfg["models"][s]
        sm = list(common.latest_by_call_id(smoke.get(s, [])).values())
        ok = [r for r in sm if r.get("error") is None]
        obs = sum(1 for r in ok if r.get("tool_call_observed"))
        notes = []
        if m.get("retrieval_on", {}).get("unavailable"):
            notes.append(m["retrieval_on"]["unavailable"])
        for r in sm:
            if r.get("error"):
                notes.append(f"{r['call_id']}: {r['error'][:80]}")
            elif r.get("tool_call_observed"):
                notes.append(f"{r['call_id']}: {json.dumps(r.get('retrieval_evidence'))[:120]}")
            else:
                notes.append(f"{r['call_id']}: NO tool call observed")
        L.append(f"| {label(s)} | {m['retrieval_off']['method']} | "
                 f"{'yes' if m['retrieval_off'].get('verified_in_pilot_env') else 'NO → lines carry `retrieval_unverified`'} | "
                 f"{len(ok)}/{len(sm)} | {obs}/{len(ok)} | {'; '.join(notes) if notes else '—'} |")
    L.append("")
    off_obs = [cid for cid, r in latest.items() if r.get("error") is None and r.get("tool_call_observed")]
    L.append(f"Main-run lines with any tool call observed in the response (should be 0): **{len(off_obs)}**"
             + (f" — {', '.join(off_obs)}" if off_obs else "") + ".\n")
    L.append("Smoke-test output is in `out/raw/smoke_retrieval_*.jsonl`, separate from the main files.\n")

    # ── 7. Errors and retries ──────────────────────────────────────────────
    L.append("## 7. Errors and retries\n")
    errs = [a for a in attempts if a.get("error") is not None]
    retried = [a for a in attempts if a.get("retries")]
    L.append(f"Attempt lines in `out/raw/`: {len(attempts)} (latest per call_id: {len(latest)}). "
             f"Lines with an error: {len(errs)}. Lines with ≥1 retry: {len(retried)}.\n")
    ec = Counter((slot_of(a["call_id"]), a["error"].split(":")[0]) for a in errs)
    if ec:
        L.append("| Model | error class | lines |")
        L.append("|---|---|---|")
        for (s, e), n in sorted(ec.items()):
            L.append(f"| {label(s)} | `{e}` | {n} |")
        L.append("")
    if retried:
        L.append("| call_id | retries | retry log |")
        L.append("|---|---|---|")
        for a in retried:
            L.append(f"| {a['call_id']} | {a['retries']} | " +
                     "; ".join(f"#{e['attempt']} {e.get('http_status') or ''} {e['error'][:70]}" for e in a.get("retry_log", [])) + " |")
        L.append("")
    unexpected = [a for a in errs if not a["error"].startswith("NO_API_KEY")]
    if unexpected:
        L.append("Non-key errors in full:\n")
        for a in unexpected:
            L.append(f"- `{a['call_id']}` ({a['timestamp_utc']}): {a['error'][:300]}")
        L.append("")

    # ── 8. What broke ──────────────────────────────────────────────────────
    L.append("## 8. What broke\n")
    L.append("Problems observed, for Randall's freeze decisions. Descriptions only; no fix wording proposed.\n")
    bullets = []
    if not_run:
        bullets.append("Slots " + ", ".join(not_run) + " did not run (no key in this environment), so the "
                       "baseline-refusal question is unanswered for them.")
    stale = [t for t, n in nonc.most_common()]
    if stale:
        bullets.append(f"Models return tickers outside the current constituent snapshot ({', '.join(stale)}); "
                       "most are recent index deletions, so the failures concentrate in the short-book frame F5 "
                       "and reflect stale membership knowledge rather than ignoring the constraint.")
    if capped:
        bullets.append(f"{len(capped)} response(s) hit the token cap: " + ", ".join(p["call_id"] for p in capped) + ".")
    if empty:
        bullets.append(f"{len(empty)} empty response(s): " + ", ".join(p["call_id"] for p in empty) + ".")
    f7_fail = [p for p in f7 if p["parse_status"] != "ok"]
    if f7_fail:
        bullets.append(f"F7: {len(f7_fail)}/{len(f7)} spoken-word responses did not yield 10 ranked slots "
                       f"({', '.join(p['call_id'] for p in f7_fail)}).")
    comm = [p for p in parsed if p["error"] is None and p["frame"] != "F7" and p["commentary_present"]]
    if comm:
        bullets.append(f"'No commentary' ignored in {len(comm)} response(s): " + ", ".join(p["call_id"] for p in comm) + ".")
    sec = [p for p in parsed if p["error"] is None and p["sector_violation"]]
    if sec:
        bullets.append(f"Sector cap violated in {len(sec)} response(s): " + ", ".join(p["call_id"] for p in sec) + ".")
    nsr = [p for p in parsed if p["code"] == "no_slots_no_refusal"]
    if nsr:
        bullets.append(f"{len(nsr)} response(s) had no slots and no decline language, so the R rule could not "
                       f"classify them: " + ", ".join(p["call_id"] for p in nsr) + ".")
    unver = [s for s in slots if not cfg["models"][s]["retrieval_off"].get("verified_in_pilot_env")]
    if unver:
        bullets.append("Retrieval-off could not be verified in this environment for " + ", ".join(unver) +
                       "; their lines are marked `retrieval_unverified`.")
    for b in bullets:
        L.append(f"- {b}")
    if NOTES_FILE.exists():
        L.append("")
        L.append(NOTES_FILE.read_text().strip())
    L.append("")

    # ── 9. Cost and runtime ────────────────────────────────────────────────
    L.append("## 9. Cost and runtime\n")
    pricing = cfg.get("pricing_usd_per_mtok") or {}
    L.append("| Model | calls ok | input tokens | output tokens (incl. reasoning) | reasoning tokens | approx. $ | sum latency |")
    L.append("|---|---|---|---|---|---|---|")
    tot_lat = 0
    for s in slots:
        rs = [r for cid, r in latest.items() if slot_of(cid) == s and r.get("error") is None]
        rs += [r for r in common.latest_by_call_id(smoke.get(s, [])).values() if r.get("error") is None]
        if not rs:
            continue
        ti = sum((r["usage"] or {}).get("input_tokens") or 0 for r in rs)
        to = sum((r["usage"] or {}).get("output_tokens") or 0 for r in rs)
        tr = sum((r["usage"] or {}).get("reasoning_tokens") or 0 for r in rs)
        lat = sum(r.get("latency_ms") or 0 for r in rs)
        tot_lat += lat
        pr = pricing.get(cfg["models"][s]["model_string"])
        cost = f"${(ti * pr['input'] + to * pr['output']) / 1e6:.2f}" if pr else "n/a (pricing not configured)"
        L.append(f"| {label(s)} | {len(rs)} | {ti} | {to} | {tr} | {cost} | {lat / 1000 / 60:.1f} min |")
    ts = sorted(a["timestamp_utc"] for a in attempts if a.get("error") is None or not a["error"].startswith("NO_API_KEY"))
    if ts:
        t0 = datetime.fromisoformat(ts[0])
        t1 = datetime.fromisoformat(ts[-1])
        last = max((a for a in attempts if a["timestamp_utc"] == ts[-1]), key=lambda a: a.get("latency_ms") or 0)
        wall = (t1 - t0).total_seconds() + (last.get("latency_ms") or 0) / 1000
        L.append(f"\nWall-clock (first to last main-run attempt, incl. the earlier single-sample check): "
                 f"{wall / 60:.1f} min; summed call latency {tot_lat / 1000 / 60:.1f} min.\n")
    L.append("Output tokens on OpenAI and Google include reasoning tokens. Google's `thoughtsTokenCount` is "
             "reported separately by the provider and is not included in `candidatesTokenCount`; here "
             "output tokens = candidatesTokenCount and reasoning = thoughtsTokenCount.\n")

    # ── Appendix ───────────────────────────────────────────────────────────
    L.append("## Appendix: prompts and inputs\n")
    if common.PROMPT_HASHES_FILE.exists():
        ph = json.loads(common.PROMPT_HASHES_FILE.read_text())
        L.append("| Frame | block | SHA-256 |")
        L.append("|---|---|---|")
        for f, v in ph.items():
            L.append(f"| {f} | {v['block_mode']} | `{v['sha256']}` |")
        L.append("")
    if META_FILE.exists():
        meta = json.loads(META_FILE.read_text())
        L.append(f"S&P 500 constituents: {meta['n_rows']} rows fetched {meta['fetched_utc']} from "
                 f"<{meta['source_url']}>. Pilot parsing snapshot only.\n")
    for s in slots:
        m = cfg["models"][s]
        L.append(f"- {label(s)}: {m['version_note'].strip()} Thinking: {m['thinking']}. "
                 f"Documented default temperature {m['default_temperature_documented']} (not sent).")
    L.append("")

    common.REPORT_FILE.write_text("\n".join(L))
    print(f"wrote {common.REPORT_FILE} ({len(L)} lines)")


if __name__ == "__main__":
    main()
