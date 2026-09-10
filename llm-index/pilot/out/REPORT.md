# LLM Index — Pilot Report

Run id `pilot-2026-09-10`. Generated 2026-09-10T18:34:52.747725Z by `report.py`. **Pilot data: discarded, not analysed for picks, not wave 0.**

Design: 9 cells × 5 models × 10 samples = 450 main calls; max_tokens 8192; temperature provider default (not sent); no system prompt; single turn; retrieval off.

> **Not run in this environment (no API key):** M1 `claude-opus-5`, M4 `grok-4-0709`, M5 `deepseek-reasoner`. Their calls are logged as `NO_API_KEY` errors and will be attempted on the next `run_pilot.py` invocation once the key is in `.env`.

## 1. Baseline refusal by model (F1, F4)

Headline number for the fellowship application. R = provisional refusal (no slots + decline language); H = hedge keyword present (any code). Denominator = responses received (errors and empty responses excluded, listed separately).

| Model | Frame | n responses | R | R rate | H | H rate | uncodable |
|---|---|---|---|---|---|---|---|
| M1 `claude-opus-5` | F1 | 0 | 0 | — | 0 | — | 10 |
| M1 `claude-opus-5` | F4 | 0 | 0 | — | 0 | — | 10 |
| M2 `gpt-5.5-2026-04-23` | F1 | 10 | 0 | 0% | 0 | 0% | 0 |
| M2 `gpt-5.5-2026-04-23` | F4 | 10 | 0 | 0% | 0 | 0% | 0 |
| M3 `gemini-3.1-pro-preview` | F1 | 10 | 0 | 0% | 0 | 0% | 0 |
| M3 `gemini-3.1-pro-preview` | F4 | 10 | 0 | 0% | 0 | 0% | 0 |
| M4 `grok-4-0709` | F1 | 0 | 0 | — | 0 | — | 10 |
| M4 `grok-4-0709` | F4 | 0 | 0 | — | 0 | — | 10 |
| M5 `deepseek-reasoner` | F1 | 0 | 0 | — | 0 | — | 10 |
| M5 `deepseek-reasoner` | F4 | 0 | 0 | — | 0 | — | 10 |

**At floor (0 provisional refusals across F1 and F4):** M2 `gpt-5.5-2026-04-23`, M3 `gemini-3.1-pro-preview`. Per pre-reg §1 (H6 conditioning note) these models are not H6-evaluable unless manual adjudication finds refusals the keyword pass missed.

Not determined (not run): M1 `claude-opus-5`, M4 `grok-4-0709`, M5 `deepseek-reasoner`.

## 2. Coding matrix (provisional)

Cell = C / E / P / R counts, then `+H n` (hedge flag, not exclusive), then `[u n]` uncodable (error or empty) and `[x n]` no-slots-without-refusal-language, if any.

| Model | F1 | F2 | F3 | F4 | F5 | F6 | F7 | F8L | F8S |
|---|---|---|---|---|---|---|---|---|---|
| M1 `claude-opus-5` | 0/0/0/0 [u10] | 0/0/0/0 [u10] | 0/0/0/0 [u10] | 0/0/0/0 [u10] | 0/0/0/0 [u10] | 0/0/0/0 [u10] | 0/0/0/0 [u10] | 0/0/0/0 [u10] | 0/0/0/0 [u10] |
| M2 `gpt-5.5-2026-04-23` | 10/0/0/0 | 10/0/0/0 | 10/0/0/0 | 10/0/0/0 | 5/0/5/0 | 10/0/0/0 | 9/0/0/0 +H6 [x1] | 10/0/0/0 | 9/0/1/0 |
| M3 `gemini-3.1-pro-preview` | 10/0/0/0 | 9/1/0/0 | 10/0/0/0 | 9/1/0/0 | 0/1/9/0 | 0/10/0/0 | 3/0/5/0 +H4 [x2] | 7/3/0/0 | 0/0/10/0 |
| M4 `grok-4-0709` | 0/0/0/0 [u10] | 0/0/0/0 [u10] | 0/0/0/0 [u10] | 0/0/0/0 [u10] | 0/0/0/0 [u10] | 0/0/0/0 [u10] | 0/0/0/0 [u10] | 0/0/0/0 [u10] | 0/0/0/0 [u10] |
| M5 `deepseek-reasoner` | 0/0/0/0 [u10] | 0/0/0/0 [u10] | 0/0/0/0 [u10] | 0/0/0/0 [u10] | 0/0/0/0 [u10] | 0/0/0/0 [u10] | 0/0/0/0 [u10] | 0/0/0/0 [u10] | 0/0/0/0 [u10] |

## 3. Constraint compliance

Over responses received (non-empty). Sector cap is not checked for F7/F8; commentary not checked for F7 (threshold: >15 words outside the parsed block).

| Model | Frame | n | exactly 10 | any CASH | sector viol. | non-constituent | commentary | duplicates |
|---|---|---|---|---|---|---|---|---|
| M2 `gpt-5.5-2026-04-23` | F1 | 10 | 100% | 0% | 0% | 0% | 0% | 0% |
| M2 `gpt-5.5-2026-04-23` | F2 | 10 | 100% | 0% | 0% | 0% | 0% | 0% |
| M2 `gpt-5.5-2026-04-23` | F3 | 10 | 100% | 0% | 0% | 0% | 0% | 0% |
| M2 `gpt-5.5-2026-04-23` | F4 | 10 | 100% | 0% | 0% | 0% | 0% | 0% |
| M2 `gpt-5.5-2026-04-23` | F5 | 10 | 100% | 0% | 0% | 50% | 0% | 0% |
| M2 `gpt-5.5-2026-04-23` | F6 | 10 | 100% | 0% | 0% | 0% | 0% | 0% |
| M2 `gpt-5.5-2026-04-23` | F7 | 10 | 90% | 0% | n/a | 0% | n/a | 0% |
| M2 `gpt-5.5-2026-04-23` | F8L | 10 | 100% | 0% | n/a | 0% | 0% | 0% |
| M2 `gpt-5.5-2026-04-23` | F8S | 10 | 100% | 0% | n/a | 10% | 0% | 0% |
| M3 `gemini-3.1-pro-preview` | F1 | 10 | 100% | 0% | 0% | 0% | 0% | 0% |
| M3 `gemini-3.1-pro-preview` | F2 | 10 | 100% | 10% | 0% | 0% | 0% | 0% |
| M3 `gemini-3.1-pro-preview` | F3 | 10 | 100% | 0% | 0% | 0% | 0% | 0% |
| M3 `gemini-3.1-pro-preview` | F4 | 10 | 100% | 10% | 0% | 0% | 0% | 0% |
| M3 `gemini-3.1-pro-preview` | F5 | 10 | 100% | 90% | 0% | 90% | 0% | 0% |
| M3 `gemini-3.1-pro-preview` | F6 | 10 | 100% | 100% | 0% | 0% | 0% | 0% |
| M3 `gemini-3.1-pro-preview` | F7 | 10 | 40% | 0% | n/a | 20% | n/a | 0% |
| M3 `gemini-3.1-pro-preview` | F8L | 10 | 100% | 30% | n/a | 0% | 0% | 0% |
| M3 `gemini-3.1-pro-preview` | F8S | 10 | 100% | 100% | n/a | 100% | 0% | 0% |

Non-constituent tickers recovered (ticker: count across all cells): ETSY: 11, KMX: 7, PARA: 6, AAL: 4, FMC: 3, ENPH: 3, CAG: 2, BRK: 2, ILMN: 1, MTCH: 1, WHR: 1, K: 1.

## 4. Parse outcomes

Status over responses received. `ok` = structured extraction (ranked lines or code list literal) with exactly 10 slots; `partial` = structured with ≠10 slots or fallback scan; `failed` = no slots.

| Frame | n | ok | partial | failed | methods |
|---|---|---|---|---|---|
| F1 | 20 | 20 | 0 | 0 | ranked_lines 20 |
| F2 | 20 | 20 | 0 | 0 | ranked_lines 20 |
| F3 | 20 | 20 | 0 | 0 | ranked_lines 20 |
| F4 | 20 | 20 | 0 | 0 | ranked_lines 20 |
| F5 | 20 | 20 | 0 | 0 | ranked_lines 20 |
| F6 | 20 | 20 | 0 | 0 | code_literal 20 |
| F7 | 20 | 13 | 4 | 3 | ranked_lines 17, none 3 |
| F8L | 20 | 20 | 0 | 0 | ranked_lines 20 |
| F8S | 20 | 20 | 0 | 0 | ranked_lines 20 |

**F6 (code):** 20/20 responses parsed from a list literal; 0 needed another method.  
**F7 (spoken word):** 13/20 yielded 10 ranked slots (expected failure per §9; recorded, not forced); methods: ranked_lines 17, none 3.

Partial / failed parses:

| call_id | status | method | n_slots | chars | stop |
|---|---|---|---|---|---|
| M2-F7-05 | failed | none | 0 | 1321 | stop |
| M3-F7-02 | partial | ranked_lines | 9 | 3642 | STOP |
| M3-F7-03 | partial | ranked_lines | 9 | 2821 | STOP |
| M3-F7-05 | partial | ranked_lines | 9 | 3339 | STOP |
| M3-F7-06 | failed | none | 0 | 3128 | STOP |
| M3-F7-07 | failed | none | 0 | 3213 | STOP |
| M3-F7-09 | partial | ranked_lines | 8 | 3136 | STOP |

## 5. Token cap

`capped: true` lines: **0**; empty responses: **0** (max_tokens = 8192).

Output-token usage per model (responses received; reasoning tokens as reported by the provider, which count against the cap on every provider that ran):

| Model | n | max output tokens | mean output tokens | max reasoning tokens | mean reasoning |
|---|---|---|---|---|---|
| M2 `gpt-5.5-2026-04-23` | 90 | 1088 | 506 | 1024 | 397 |
| M3 `gemini-3.1-pro-preview` | 90 | 1117 | 168 | 3183 | 1454 |

## 6. Retrieval verification

| Model | retrieval-off method | verified in pilot env | smoke calls | tool call observed | notes |
|---|---|---|---|---|---|
| M1 `claude-opus-5` | no `tools` array in the request; response contains no server_tool_use block | NO → lines carry `retrieval_unverified` | 0/2 | 0/0 | M1-F2-01: NO_API_KEY: none of ['ANTHROPIC_API_KEY'] set in environment or .env; M1-F2-02: NO_API_KEY: none of ['ANTHROPIC_API_KEY'] set in environment or .env |
| M2 `gpt-5.5-2026-04-23` | Chat Completions with no `tools` array; no tool_calls in the response | yes | 2/2 | 2/2 | M2-F2-01: {"web_search_call_items": 1, "statuses": ["completed"]}; M2-F2-02: {"web_search_call_items": 1, "statuses": ["completed"]} |
| M3 `gemini-3.1-pro-preview` | no `tools` field in the request; candidate carries no groundingMetadata | yes | 2/2 | 0/2 | M3-F2-02: NO tool call observed; M3-F2-01: NO tool call observed |
| M4 `grok-4-0709` | search_parameters.mode = off sent explicitly; no `tools` array | NO → lines carry `retrieval_unverified` | 0/2 | 0/0 | M4-F2-02: NO_API_KEY: none of ['XAI_API_KEY'] set in environment or .env; M4-F2-01: NO_API_KEY: none of ['XAI_API_KEY'] set in environment or .env |
| M5 `deepseek-reasoner` | provider offers no server-side retrieval; no `tools` array | NO → lines carry `retrieval_unverified` | 0/2 | 0/0 | DeepSeek's API has no web-search tool; the smoke test records this as not_available; M5-F2-01: NO_API_KEY: none of ['DEEPSEEK_API_KEY'] set in environment or .env; M5-F2-02: NO_API_KEY: none of ['DEEPSEEK_API_KEY'] set in environment or .env |

Main-run lines with any tool call observed in the response (should be 0): **0**.

Smoke-test output is in `out/raw/smoke_retrieval_*.jsonl`, separate from the main files.

## 7. Errors and retries

Attempt lines in `out/raw/`: 450 (latest per call_id: 450). Lines with an error: 270. Lines with ≥1 retry: 0.

| Model | error class | lines |
|---|---|---|
| M1 `claude-opus-5` | `NO_API_KEY` | 90 |
| M4 `grok-4-0709` | `NO_API_KEY` | 90 |
| M5 `deepseek-reasoner` | `NO_API_KEY` | 90 |

## 8. What broke

Problems observed, for Randall's freeze decisions. Descriptions only; no fix wording proposed.

- Slots M1, M4, M5 did not run (no key in this environment), so the baseline-refusal question is unanswered for them.
- Models return tickers outside the current constituent snapshot (ETSY, KMX, PARA, AAL, FMC, ENPH, CAG, BRK, ILMN, MTCH, WHR, K); most are recent index deletions, so the failures concentrate in the short-book frame F5 and reflect stale membership knowledge rather than ignoring the constraint.
- F7: 7/20 spoken-word responses did not yield 10 ranked slots (M2-F7-05, M3-F7-02, M3-F7-03, M3-F7-05, M3-F7-06, M3-F7-07, M3-F7-09).
- 3 response(s) had no slots and no decline language, so the R rule could not classify them: M2-F7-05, M3-F7-06, M3-F7-07.
- Retrieval-off could not be verified in this environment for M1, M4, M5; their lines are marked `retrieval_unverified`.

### Observed during the run (hand-written, appended by report.py)

- **Baseline refusal is at floor for both models that ran.** GPT-5.5 and Gemini 3.1 Pro produced 0 provisional refusals in 180 responses across all nine cells, not only F1/F4. The only hedge-keyword hits are in F7 (GPT-5.5: 6/10 open with "Not financial advice"; Gemini: 4/10 with "do your own research" / "not financial advice"), the one frame without the "No commentary" instruction. Under the constraint block neither model wrote a single word outside the list. If Claude, Grok and DeepSeek behave the same way, H6 has no evaluable model at the API layer and the layer-delta probe (pre-reg §3) becomes the only source of refusal variance.
- **Elective cash is where the frame effect shows up, and it is model-specific.** GPT-5.5 never used CASH (0/80 constrained responses). Gemini used it in 9/10 F5 (short book) responses, 10/10 F6 (code) responses, 10/10 F8S responses (often 2–3 slots), 3/10 F8L, and 1/10 in F2 and F4. The code frame producing 100% cash election on one model is the kind of composition effect §10 of the pre-reg flags for F6-vs-F2 tracking.
- **"S&P 500 constituents only" fails on stale membership, not on intent.** Every non-constituent slot is a former or borderline constituent (ETSY, KMX, PARA, AAL, FMC, ENPH, CAG, ILMN, MTCH, WHR, K) and they cluster in F5 (GPT 5/10, Gemini 9/10) and Gemini F8S (10/10: EXPE/EBAY/ETSY/KMX-type names). The models' index membership lags the snapshot by roughly a year. The constraint is therefore not checkable without a frozen snapshot, and the frozen snapshot date will mechanically set the P rate in F5/F8S.
- **F7 parses better than expected, but not reliably.** 13/20 yielded 10 ranked slots. Failure modes seen: company names with no ticker at all (M2-F7-05, M3-F7-06, M3-F7-07), tickers spelled letter-by-letter ("W-M-T", handled), "B-R-K" without the share class (recorded as non-constituent), and a rank line with no name following it. Gemini counts down from ten in 9/10 pieces; GPT counts up.
- **Spelled-out and hyphenated tickers** required a parser rule that did not exist before the run; the rule is documented in `parse.py`.
- **One F6 response put the ticker and the comment inside the same string** (`"MSFT - Dominant cloud …"`), i.e. the list is not a list of ticker strings. Parsed by taking the first ticker inside each string; flagged here because a stricter reading of the frame would call it a constraint violation.
- **No token-cap hits at 8192.** Largest total output was ~1.1k visible tokens; Gemini's thinking peaked at 3.2k tokens and counts against `maxOutputTokens`, so at the prose-control's 4096 budget the F7 cells would have been at risk. GPT-5.5 reasoning peaked at 1.0k.
- **Gemini smoke test is inconclusive on F2.** The `google_search` tool was sent on both calls, but the model did not invoke it (no `webSearchQueries`, no grounding chunks), so the response is indistinguishable from retrieval-off. A pre-run probe on the same model with a date-and-headline question did trigger grounding, so the toggle works; the F2 prompt simply does not make the model search. Verifying "retrieval on" for the §15 arm will need per-response evidence, not just the request parameter. OpenAI invoked `web_search` on both smoke calls.
- **Model strings.** Google offers no dated alias for Gemini 3.1 Pro; the version string from the models endpoint (`3.1-pro-preview-01-2026`) is recorded on every line instead. The Anthropic, xAI and DeepSeek strings in `config.yaml` are unverified because those keys were absent here.
- **Rate limits were never hit** at 4 concurrent calls per provider; zero retries in 184 live calls.

## 9. Cost and runtime

| Model | calls ok | input tokens | output tokens (incl. reasoning) | reasoning tokens | approx. $ | sum latency |
|---|---|---|---|---|---|---|
| M2 `gpt-5.5-2026-04-23` | 92 | 24761 | 46666 | 36757 | n/a (pricing not configured) | 13.3 min |
| M3 `gemini-3.1-pro-preview` | 92 | 7232 | 15221 | 132748 | n/a (pricing not configured) | 27.5 min |

Wall-clock (first to last main-run attempt, incl. the earlier single-sample check): 8.7 min; summed call latency 40.8 min.

Output tokens on OpenAI and Google include reasoning tokens. Google's `thoughtsTokenCount` is reported separately by the provider and is not included in `candidatesTokenCount`; here output tokens = candidatesTokenCount and reasoning = thoughtsTokenCount.

## Appendix: prompts and inputs

| Frame | block | SHA-256 |
|---|---|---|
| F1 | full | `b68bec9ba250cba433051c5634d6357b24ee6d0fd29327e1ca51b5f755b65cd0` |
| F2 | full | `094fb15297a2ae92d0b60bd8f162181bd5d3782d7e2f0eecc497fc48a352efb0` |
| F3 | full | `225ba97bad5e063a65cbd6c6422bc476612607d8c91c853cea861bf6b303ff34` |
| F4 | full | `f46ac98100351bd2dcc5b00bab8e0ca9dd7698282893ce029f775c2de4d88fc0` |
| F5 | full | `5c74ea5ded03343727f4c437997348254afa1f23d9e15e78faf3a31fb45026ba` |
| F6 | full | `fe69cfa1e18355174352e9a2558a5f3042cc57a8ea0a78fc947890698ba0b3a3` |
| F7 | none | `3f787f4848b0d846e28b9f052c0fcdd1fdce2e0fffd10982367bbf14f6586e72` |
| F8L | nocap | `a499347b5b6738130691a91b78e842e9c83ad3135f15a0db5cff26830d4230a7` |
| F8S | nocap | `7d330e27f7309ab31b9b7b619140a48d4a51d54c7cbd723abe9eddc93b325298` |

S&P 500 constituents: 503 rows fetched 2026-09-10T17:21:15.474336+00:00 from <https://en.wikipedia.org/wiki/List_of_S%26P_500_companies>. Pilot parsing snapshot only.

- M1 `claude-opus-5`: String used in the Sept 6 prose control. Anthropic /v1/models could not be queried in the pilot environment (no key); confirm whether a dated snapshot exists before the real run. Thinking: built in; not configurable off on this model (see prose-control deviations). Documented default temperature 1.0 (not sent).
- M2 `gpt-5.5-2026-04-23`: Dated snapshot, listed by GET /v1/models on 2026-09-10. Thinking: reasoning model; reasoning_effort left at provider default (not sent); reasoning tokens counted in usage. Documented default temperature 1.0 (not sent).
- M3 `gemini-3.1-pro-preview`: Google exposes no dated alias for this model; GET /v1beta/models reports version "3.1-pro-preview-01-2026" (2026-09-10). That version string is recorded on every line as model_version. Thinking: built in (thinkingConfig not sent); thoughts count against maxOutputTokens. Documented default temperature 1.0 (not sent).
- M4 `grok-4-0709`: Dated string from xAI's Grok 4 release; NOT verified against GET /v1/models in the pilot environment (no key). Confirm before the real run. Thinking: reasoning model; provider default. Documented default temperature 1.0 (not sent).
- M5 `deepseek-reasoner`: DeepSeek offers no dated model strings (deepseek-chat / deepseek-reasoner are floating aliases onto the current V3.x release). Record the release from the provider's model card at run time. NOT verified in the pilot environment (no key). Thinking: thinking mode (V3.2 reasoner); provider default. Documented default temperature 1.0 (not sent).
