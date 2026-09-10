# LLM Index — pilot

**This is pilot data. It is discarded. It is not wave 0.** The pilot exists to
verify the elicitation pipeline end-to-end before the pre-registration
(`llm-index-preregistration.md` v0.4) is frozen: does each model have a
nonzero baseline refusal rate under F1/F4, do models honor the constraint
block, does the parser recover ranked tickers, and do responses hit the token
cap. Pick content is out of scope and is never analysed, compared across
models, or priced. See [`PILOT.md`](PILOT.md) for the full handoff spec and
[`out/REPORT.md`](out/REPORT.md) for the generated report.

## Layout

```
PILOT.md                 handoff spec (verbatim)
.env.example             keys template; copy to .env (gitignored)
config.yaml              models, n, max_tokens, retry, smoke test
prompts/frames.yaml      F1–F8 + constraint block, verbatim from pre-reg §4
data/sp500_constituents.csv  parsing snapshot (source + fetch date in .meta.json)
hedge_keywords.txt       starter hedge list (§10)
refusal_keywords.txt     decline/deflect phrases used for provisional R
fetch_constituents.py    refetch the snapshot (--force)
run_pilot.py             elicitation; --smoke for the §7 retrieval smoke test
parse.py                 ticker extraction + constraint checks → out/parsed.jsonl
code_responses.py        provisional C/E/P/H/R → adds fields to out/parsed.jsonl
report.py                builds out/REPORT.md (+ report_notes.md into §8)
out/raw/*.jsonl          one file per model, one line per attempt (failures included)
out/raw/smoke_retrieval_*.jsonl   retrieval-ON smoke test, kept separate
```

## Running

```bash
cd llm-index/pilot
cp .env.example .env          # fill in keys; never committed
python3 fetch_constituents.py # once
python3 run_pilot.py          # 450 main calls; idempotent, re-attempts failed call_ids
python3 run_pilot.py --smoke  # 10 retrieval-ON calls
python3 parse.py && python3 code_responses.py && python3 report.py
```

Needs Python 3.11+, `requests`, `pyyaml`. Models whose key is missing get one
`NO_API_KEY` line per call and are picked up on the next run.
