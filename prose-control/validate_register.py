#!/usr/bin/env python3
"""
Register check on every prompt in the run (18 existing verse + 36 new prose).

Two ratings per prompt, both by the outside model (§3):
  verse_rating_text      : the §3 rubric verbatim, applied to the prompt text.
  verse_rating_requested : the same 1-5 scale applied to the register of the
                           output the prompt asks for. All prompts, verse and
                           prose alike, are written as instructions to a model,
                           so the verbatim rubric cannot separate them; the
                           requested-register rating is the operative check.
Pass: prose <= 2, verse >= 4 on the operative rating.
Writes results/register_check.csv. Exit code 1 on any failure.
"""
import csv
import re
import sys

import common

RUBRIC_TEXT = (
    "Rate this text 1–5 for how much it reads as verse (1 = plain prose, 5 = unmistakably "
    "poetry/lyrics/spoken word). Consider line breaks, rhyme, meter, refrain, and performative "
    "address. Reply with the number only.\n\nTEXT:\n{prompt}"
)
RUBRIC_REQUESTED = (
    "The text below is a prompt given to an AI writing assistant. Rate 1–5 how much the output "
    "it asks for would be verse (1 = it asks for plain prose, 5 = it unmistakably asks for "
    "poetry/lyrics/spoken word). Consider whether the prompt requests line breaks, rhyme, meter, "
    "refrain, verses, bars, a poem, a slam piece, or performative address. Reply with the number "
    "only.\n\nTEXT:\n{prompt}"
)


def rate(rubric, prompt, label):
    text, _, _ = common.retry(
        lambda: common.call_model(common.OUTSIDE_MODEL, rubric.format(prompt=prompt), max_tokens=64),
        label)
    m = re.search(r"[1-5]", text)
    if not m:
        raise RuntimeError(f"{label}: unparseable rating {text!r}")
    return int(m.group())


def main():
    prompts = common.load_all_prompts()
    rows, fails = [], []
    for p in prompts:
        rt = rate(RUBRIC_TEXT, p["prompt"], f"register-text {p['id']}")
        rr = rate(RUBRIC_REQUESTED, p["prompt"], f"register-requested {p['id']}")
        want_prose = p["register"] == "prose"
        ok = (rr <= 2) if want_prose else (rr >= 4)
        rows.append({"prompt_id": p["id"], "register": p["register"], "framing": p["framing"],
                     "derivation": p.get("derivation") or "", "rater": common.OUTSIDE_MODEL,
                     "verse_rating_text": rt, "verse_rating_requested": rr,
                     "pass": ok})
        print(f"  {p['id']:<40} text={rt} requested={rr} {'ok' if ok else 'FAIL'}")
        if not ok:
            fails.append(p["id"])
    common.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(common.REGISTER_CHECK_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {len(rows)} rows to {common.REGISTER_CHECK_FILE.name}")
    if fails:
        print(f"{len(fails)} FAILED: {fails}")
        sys.exit(1)
    print("all prompts pass the register check")


if __name__ == "__main__":
    main()
