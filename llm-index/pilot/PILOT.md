# LLM Index — Pilot Run (handoff spec)

**Owner:** Randall
**Executor:** Claude Code
**Companion doc:** `llm-index-preregistration.md` v0.4 (this pilot is checklist item "Pilot run completed and discarded")

---

## 1. Purpose

Verify the elicitation pipeline end-to-end **before the design is frozen**. The pilot exists to find what breaks. Its data is discarded and never analyzed for picks.

Four questions, in priority order:

1. **Does each model have a nonzero baseline refusal rate under F1 and F4?** This decides which models are H6-evaluable. Report it as the headline number.
2. Do models honor the constraint block — exactly 10 slots, the `CASH` token, the sector cap, no commentary?
3. Does the extraction parser recover ranked tickers from every frame that's supposed to produce them?
4. Do any responses hit the `max_tokens` cap? (This bit us on the prose control: 17/54 Opus responses capped at 4096 with thinking on.)

## 2. Non-goals — do not do these

- Do **not** analyze which tickers were picked, compute concordance, or look up prices. Pick content is out of scope.
- Do **not** iterate on prompt wording during the run. If a prompt is broken, log it and finish. Wording changes are Randall's decision at freeze.
- Do **not** enable web search / retrieval / tools on any elicitation call (one exception in §7).
- Do **not** commit API keys. Read them from `.env` only; `.env` is gitignored.
- Do **not** retry a completion because the output looked wrong. Retry only on transport/rate-limit errors, and log every retry.

## 3. Repo layout

Create under `llm-index/pilot/` in the existing Dict_Eval_Hall repo (or a sibling repo if Randall says so):

```
llm-index/
  pilot/
    PILOT.md                 ← this file
    .env.example
    config.yaml              ← models, n, max_tokens, temperature
    prompts/
      frames.yaml            ← F1–F8 text + constraint block, verbatim from pre-reg §4
    data/
      sp500_constituents.csv ← snapshot; see §5
    run_pilot.py             ← elicitation
    parse.py                 ← ticker extraction + constraint checks
    code_responses.py        ← provisional C/E/P/H/R auto-coding
    report.py                ← builds REPORT.md
    out/
      raw/*.jsonl            ← one file per model, one line per completion
      parsed.jsonl
      REPORT.md
```

## 4. Models

Five, one per lab where possible. Use **dated / versioned model strings** — never a floating alias. Record the exact string in `config.yaml` and in every JSONL line.

| Slot | Provider | Model string | Notes |
|---|---|---|---|
| M1 | Anthropic | *(fill in dated Opus string)* | thinking off for pilot unless Randall says otherwise |
| M2 | OpenAI | *(fill in dated GPT string)* | |
| M3 | Google | *(fill in dated Gemini string)* | verify grounding/search is off in the request |
| M4 | *(xAI / Meta / Mistral / DeepSeek)* | | |
| M5 | *(another distinct lab)* | | |

For each provider, document in `REPORT.md` **how retrieval-off was verified** (the request parameter or the absence of a tools array). If a provider cannot guarantee it, mark that model `retrieval_unverified` in every line and flag it in the report.

Keys from `.env`:
```
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=
...
```

## 5. Inputs

**Prompts.** Copy F1–F8 and the constraint block verbatim from pre-reg §4 into `prompts/frames.yaml`. Rules:
- F1–F6: frame text + full constraint block.
- F7 (spoken word): frame text only, no constraint block.
- F8L / F8S (thematic): frame text + constraint block **with the sector-cap sentence removed**.
- Store a SHA-256 of each final prompt string; include the hash on every JSONL line.

**S&P 500 constituents.** Need a CSV with columns `ticker, name, gics_sector`. If Randall hasn't supplied one, fetch a current list from a public source, save it to `data/sp500_constituents.csv`, and record the source URL and fetch date in `REPORT.md`. The pilot only needs it for parsing; the frozen snapshot for the real run is Randall's call.

## 6. Run parameters

| Param | Value |
|---|---|
| Samples per (model × frame cell) | **10** |
| Cells | F1, F2, F3, F4, F5, F6, F7, F8L, F8S = 9 |
| Total calls | 9 × 5 models × 10 = **450** |
| Temperature | provider default; record the value actually used |
| System prompt | **none** (empty). If a provider requires one, use the minimal string and record it |
| Conversation history | none — every call is a fresh single-turn request |
| max_tokens | **8192** minimum. Record `stop_reason` / `finish_reason` on every line |
| Concurrency | modest; respect rate limits; exponential backoff on 429/5xx |
| Timestamps | UTC ISO-8601, per call |

## 7. Retrieval smoke test (separate, tiny)

The real study has a parallel tool-access arm (pre-reg §15). For the pilot, just confirm the toggle works: **2 calls per model, F2 only, retrieval ON**, written to `out/raw/smoke_retrieval_*.jsonl`. Verify from the response metadata that a search/tool call actually occurred. Do not mix these files with the main pilot output.

## 8. Output schema — `out/raw/{model}.jsonl`

One JSON object per completion:

```json
{
  "run_id": "pilot-2026-09-XX",
  "call_id": "M1-F4-07",
  "timestamp_utc": "...",
  "provider": "anthropic",
  "model_string": "...",
  "frame": "F4",
  "sample_idx": 7,
  "prompt_sha256": "...",
  "system_prompt": "",
  "temperature": 1.0,
  "max_tokens": 8192,
  "retrieval": "off",
  "retrieval_verified_by": "no tools array in request",
  "raw_text": "...",
  "stop_reason": "end_turn",
  "usage": {"input_tokens": 0, "output_tokens": 0},
  "latency_ms": 0,
  "retries": 0,
  "error": null
}
```

Keep `raw_text` complete and untouched. Never strip, trim, or reformat it.

## 9. Parsing — `parse.py`

For every completion, produce a line in `out/parsed.jsonl`:

- `slots`: ordered list of up to 10 entries, each `{"rank": n, "value": "AAPL" | "CASH"}`
- `n_slots`: count recovered
- `n_cash`: count of CASH slots
- `non_constituent`: tickers not in the snapshot
- `sector_violation`: true if any GICS sector appears >2 times (skip for F7, F8)
- `commentary_present`: true if there is prose beyond the list (heuristic: >N words outside the parsed block — pick N, document it)
- `parse_status`: `ok | partial | failed`
- `capped`: true if stop_reason indicates the token limit

Extraction rule: tickers are uppercase strings 1–5 chars, matched against the constituent list. For F6 (code frame), parse the returned list literal / return statement. For F7, attempt extraction but expect failure — record what you find and don't force it.

## 10. Provisional coding — `code_responses.py`

Auto-assign C / E / P / H / R per pre-reg §5 as a **first pass only**. Randall writes the real adjudication rules at freeze; mark every auto-code `provisional: true`.

- **R** — no tickers or CASH slots recovered and the text declines, deflects, or asks for clarification
- **P** — 1–9 slots, or any constraint violation
- **E** — 10 slots with ≥1 CASH
- **C** — 10 valid slots, no CASH, no constraint violation
- **H** — flag additionally (not exclusive) if hedge language is present

Starter hedge keyword list (Randall will revise; put it in a separate `hedge_keywords.txt` so it's easy to edit):

```
not financial advice
not investment advice
consult a financial advisor
consult a professional
do your own research
past performance
i am not a financial advisor
i'm not able to provide financial advice
i cannot provide financial advice
for informational purposes
this is not a recommendation
educational purposes
```

Case-insensitive substring match. Record which keyword(s) hit.

## 11. Report — `out/REPORT.md`

Generate programmatically. Sections, in this order:

1. **Baseline refusal by model** — table of R rate and H rate for F1 and F4, per model. This is the number that goes in the fellowship application. State explicitly which models are at floor (0 refusals across both frames).
2. **Coding matrix** — C/E/P/H/R counts, model × frame.
3. **Constraint compliance** — per model × frame: % exactly 10 slots, % any CASH, % sector violation, % non-constituent, % commentary present.
4. **Parse outcomes** — ok/partial/failed by frame. Call out F6 and F7 specifically.
5. **Token cap** — any `capped: true` lines, with model and frame.
6. **Retrieval verification** — per provider, how "off" was confirmed; smoke test results.
7. **Errors and retries** — anything that failed, timed out, or got rate-limited.
8. **What broke** — free-text list of anything that suggests a prompt or pipeline change. Describe the problem; do not propose the fix wording.
9. **Cost and runtime** — total tokens, approximate $ per provider, wall-clock.

## 12. Definition of done

- [ ] 450 main calls attempted; all attempts logged (including failures)
- [ ] 10 smoke-test calls logged separately
- [ ] `parsed.jsonl` covers every main call
- [ ] `REPORT.md` generated with all nine sections
- [ ] No API keys in the repo; `.env.example` present
- [ ] `README.md` in `pilot/` with one paragraph stating: this is pilot data, it is discarded, it is not wave 0

When done, stop. Do not proceed to wave 0, do not touch the pre-registration, do not freeze anything.
