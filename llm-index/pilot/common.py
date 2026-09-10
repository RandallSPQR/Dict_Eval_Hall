#!/usr/bin/env python3
"""
Shared helpers for the LLM Index pilot (PILOT.md): config and .env loading,
prompt assembly + SHA-256, provider adapters returning a normalised result,
JSONL I/O.

Provider adapters send NO system prompt, NO conversation history, NO tools
unless `retrieval=True` (smoke test only, §7). Each adapter returns a dict:
  text, stop_reason, usage{input_tokens, output_tokens, reasoning_tokens},
  usage_raw, model_reported, tool_call_observed, retrieval_evidence,
  request_body (exact JSON sent, minus auth headers)
Transport / rate-limit errors raise ProviderError(retryable=True); everything
else raises ProviderError(retryable=False).  Nothing here retries because the
output "looked wrong" (§2).
"""
import fcntl
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE / "config.yaml"
FRAMES_FILE = HERE / "prompts" / "frames.yaml"
ENV_FILE = HERE / ".env"
CONSTITUENTS_CSV = HERE / "data" / "sp500_constituents.csv"
OUT_DIR = HERE / "out"
RAW_DIR = OUT_DIR / "raw"
PARSED_FILE = OUT_DIR / "parsed.jsonl"
REPORT_FILE = OUT_DIR / "REPORT.md"
PROMPT_HASHES_FILE = OUT_DIR / "prompt_hashes.json"

CAP_STOP_REASONS = {"max_tokens", "length", "MAX_TOKENS", "incomplete:max_output_tokens"}


# ── .env / config ────────────────────────────────────────────────────────────
def load_env(path=ENV_FILE):
    """Minimal .env reader. Shell environment wins over the file."""
    if not Path(path).exists():
        return
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.split(" #", 1)[0].strip().strip('"').strip("'")
        if k.strip() and v and not os.environ.get(k.strip()):
            os.environ[k.strip()] = v


def load_config():
    load_env()
    return yaml.safe_load(CONFIG_FILE.read_text())


def key_for(mcfg):
    for env in mcfg["key_env"]:
        if os.environ.get(env):
            return os.environ[env]
    return None


def now_utc():
    return datetime.now(timezone.utc).isoformat()


# ── Prompts (§5) ─────────────────────────────────────────────────────────────
def load_frames():
    return yaml.safe_load(FRAMES_FILE.read_text())


def build_prompt(frames, frame_id):
    f = frames["frames"][frame_id]
    block = frames["constraint_block"]
    mode = f["block_mode"]
    if mode == "none":
        return f["text"]
    if mode == "nocap":
        cap = frames["sector_cap_sentence"]
        assert cap in block, "sector_cap_sentence not found in constraint_block"
        block = block.replace(cap + " ", "").replace(cap, "").strip()
    elif mode != "full":
        raise ValueError(f"unknown block_mode {mode!r} for {frame_id}")
    return f["text"] + "\n\n" + block


def sha256(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def all_prompts(frames, frame_ids):
    out = {}
    for fid in frame_ids:
        p = build_prompt(frames, fid)
        out[fid] = {"prompt": p, "sha256": sha256(p), "block_mode": frames["frames"][fid]["block_mode"]}
    return out


# ── JSONL ────────────────────────────────────────────────────────────────────
def read_jsonl(path):
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def append_jsonl(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, ensure_ascii=False) + "\n"
    with open(path, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(line)
        f.flush()
        fcntl.flock(f, fcntl.LOCK_UN)


def raw_file(slot, mcfg):
    return RAW_DIR / f"{slot}_{mcfg['provider']}_{mcfg['model_string'].replace('/', '_')}.jsonl"


def smoke_file(slot, mcfg):
    return RAW_DIR / f"smoke_retrieval_{slot}_{mcfg['provider']}_{mcfg['model_string'].replace('/', '_')}.jsonl"


def latest_by_call_id(records):
    """Last record per call_id wins (records are appended in time order)."""
    out = {}
    for r in records:
        out[r["call_id"]] = r
    return out


# ── Provider adapters ────────────────────────────────────────────────────────
class ProviderError(Exception):
    def __init__(self, msg, retryable, status=None):
        super().__init__(msg)
        self.retryable = retryable
        self.status = status


RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504, 529}


def _post(url, headers, body, timeout):
    try:
        r = requests.post(url, headers=headers, json=body, timeout=timeout)
    except (requests.ConnectionError, requests.Timeout) as e:
        raise ProviderError(f"transport: {type(e).__name__}: {str(e)[:200]}", retryable=True)
    if r.status_code != 200:
        raise ProviderError(f"HTTP {r.status_code}: {r.text[:400]}",
                            retryable=r.status_code in RETRYABLE_STATUS, status=r.status_code)
    try:
        return r.json()
    except ValueError:
        raise ProviderError(f"non-JSON body: {r.text[:200]}", retryable=True)


def _usage(inp, out, reasoning):
    return {"input_tokens": inp, "output_tokens": out, "reasoning_tokens": reasoning}


def call_anthropic(mcfg, prompt, max_tokens, timeout, retrieval=False):
    key = key_for(mcfg)
    base = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
    body = {"model": mcfg["model_string"], "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]}
    if retrieval:
        body["tools"] = mcfg["retrieval_on"]["tools"]
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    if os.environ.get("ANTHROPIC_WORKSPACE_ID"):
        headers["anthropic-workspace-id"] = os.environ["ANTHROPIC_WORKSPACE_ID"]
    b = _post(f"{base}/v1/messages", headers, body, timeout)
    content = b.get("content", [])
    text = "".join(x.get("text", "") for x in content if x.get("type") == "text")
    tool_blocks = [x for x in content if x.get("type") in ("server_tool_use", "tool_use")]
    u = b.get("usage", {}) or {}
    return {"text": text, "stop_reason": b.get("stop_reason"),
            "usage": _usage(u.get("input_tokens"), u.get("output_tokens"), None), "usage_raw": u,
            "model_reported": b.get("model"), "tool_call_observed": bool(tool_blocks),
            "retrieval_evidence": [x.get("name") for x in tool_blocks], "request_body": body}


def _openai_compatible(url, key, body, timeout, extra_headers=None):
    headers = {"Authorization": f"Bearer {key}", "content-type": "application/json"}
    headers.update(extra_headers or {})
    b = _post(url, headers, body, timeout)
    ch = b["choices"][0]
    msg = ch.get("message", {})
    text = msg.get("content") or ""
    if not text and msg.get("refusal"):
        text = msg["refusal"]
    u = b.get("usage", {}) or {}
    reasoning = (u.get("completion_tokens_details") or {}).get("reasoning_tokens")
    tool_calls = msg.get("tool_calls") or []
    citations = b.get("citations") or []
    return {"text": text, "stop_reason": ch.get("finish_reason"),
            "usage": _usage(u.get("prompt_tokens"), u.get("completion_tokens"), reasoning), "usage_raw": u,
            "model_reported": b.get("model"), "tool_call_observed": bool(tool_calls) or bool(citations),
            "retrieval_evidence": {"tool_calls": len(tool_calls), "citations": len(citations)},
            "request_body": body}


def call_openai(mcfg, prompt, max_tokens, timeout, retrieval=False):
    key = key_for(mcfg)
    if not retrieval:
        body = {"model": mcfg["model_string"], "max_completion_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}]}
        return _openai_compatible("https://api.openai.com/v1/chat/completions", key, body, timeout)
    # Smoke test: Responses API with the web_search tool.
    body = {"model": mcfg["model_string"], "input": prompt, "max_output_tokens": max_tokens,
            "tools": mcfg["retrieval_on"]["tools"]}
    b = _post("https://api.openai.com/v1/responses",
              {"Authorization": f"Bearer {key}", "content-type": "application/json"}, body, timeout)
    out = b.get("output", [])
    text = "".join(c.get("text", "") for o in out if o.get("type") == "message"
                   for c in o.get("content", []) if c.get("type") == "output_text")
    searches = [o for o in out if o.get("type") == "web_search_call"]
    status = b.get("status")
    stop = status if status != "incomplete" else "incomplete:" + str((b.get("incomplete_details") or {}).get("reason"))
    u = b.get("usage", {}) or {}
    reasoning = (u.get("output_tokens_details") or {}).get("reasoning_tokens")
    return {"text": text, "stop_reason": stop,
            "usage": _usage(u.get("input_tokens"), u.get("output_tokens"), reasoning), "usage_raw": u,
            "model_reported": b.get("model"), "tool_call_observed": bool(searches),
            "retrieval_evidence": {"web_search_call_items": len(searches),
                                   "statuses": [s.get("status") for s in searches]},
            "request_body": body}


def call_google(mcfg, prompt, max_tokens, timeout, retrieval=False):
    key = key_for(mcfg)
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens}}
    if retrieval:
        body["tools"] = mcfg["retrieval_on"]["tools"]
    b = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{mcfg['model_string']}:generateContent",
              {"x-goog-api-key": key, "content-type": "application/json"}, body, timeout)
    u = b.get("usageMetadata", {}) or {}
    usage = _usage(u.get("promptTokenCount"), u.get("candidatesTokenCount"), u.get("thoughtsTokenCount"))
    if not b.get("candidates"):
        fb = b.get("promptFeedback", {}) or {}
        return {"text": "", "stop_reason": "PROMPT_BLOCKED:" + str(fb.get("blockReason")), "usage": usage,
                "usage_raw": u, "model_reported": b.get("modelVersion"), "tool_call_observed": False,
                "retrieval_evidence": None, "request_body": body, "prompt_feedback": fb}
    c = b["candidates"][0]
    parts = (c.get("content") or {}).get("parts", []) or []
    text = "".join(p.get("text", "") for p in parts if "text" in p and not p.get("thought"))
    gm = c.get("groundingMetadata") or {}
    queries = gm.get("webSearchQueries") or []
    return {"text": text, "stop_reason": c.get("finishReason"), "usage": usage, "usage_raw": u,
            "model_reported": b.get("modelVersion"), "tool_call_observed": bool(queries) or bool(gm.get("groundingChunks")),
            "retrieval_evidence": {"webSearchQueries": queries, "groundingChunks": len(gm.get("groundingChunks") or [])},
            "request_body": body}


def call_xai(mcfg, prompt, max_tokens, timeout, retrieval=False):
    key = key_for(mcfg)
    body = {"model": mcfg["model_string"], "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "search_parameters": mcfg["retrieval_on"]["search_parameters"] if retrieval else {"mode": "off"}}
    return _openai_compatible(mcfg["base_url"].rstrip("/") + "/chat/completions", key, body, timeout)


def call_deepseek(mcfg, prompt, max_tokens, timeout, retrieval=False):
    if retrieval:
        raise ProviderError("retrieval not_available: DeepSeek API has no web-search tool", retryable=False)
    key = key_for(mcfg)
    body = {"model": mcfg["model_string"], "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]}
    return _openai_compatible(mcfg["base_url"].rstrip("/") + "/chat/completions", key, body, timeout)


ADAPTERS = {"anthropic": call_anthropic, "openai": call_openai, "google": call_google,
            "xai": call_xai, "deepseek": call_deepseek}


def call_model(mcfg, prompt, max_tokens, timeout, retrieval=False):
    return ADAPTERS[mcfg["provider"]](mcfg, prompt, max_tokens, timeout, retrieval=retrieval)


def call_with_retry(mcfg, prompt, max_tokens, timeout, retry_cfg, retrieval=False, log=None):
    """Returns (result_or_None, retry_log, error_or_None, retries, latency_ms)."""
    attempts = retry_cfg["max_attempts"]
    backoff = retry_cfg["backoff_s"]
    retry_log = []
    t0 = time.time()
    for i in range(attempts):
        try:
            res = call_model(mcfg, prompt, max_tokens, timeout, retrieval=retrieval)
            return res, retry_log, None, i, int((time.time() - t0) * 1000)
        except ProviderError as e:
            entry = {"attempt": i + 1, "timestamp_utc": now_utc(), "error": str(e)[:500],
                     "http_status": e.status, "retryable": e.retryable}
            retry_log.append(entry)
            if e.retryable and i < attempts - 1:
                wait = backoff[min(i, len(backoff) - 1)]
                if log:
                    log(f"    retry {i + 1}/{attempts - 1} in {wait}s: {str(e)[:120]}")
                time.sleep(wait)
                continue
            return None, retry_log, str(e)[:800], i, int((time.time() - t0) * 1000)
        except Exception as e:  # noqa: BLE001 — unexpected shape etc.; not retried
            retry_log.append({"attempt": i + 1, "timestamp_utc": now_utc(),
                              "error": f"{type(e).__name__}: {str(e)[:400]}", "retryable": False})
            return None, retry_log, f"{type(e).__name__}: {str(e)[:800]}", i, int((time.time() - t0) * 1000)
    return None, retry_log, "unreachable", attempts, int((time.time() - t0) * 1000)
