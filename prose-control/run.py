#!/usr/bin/env python3
"""
Elicitation (§4). All cells in one batch: 18 verse + 36 prose prompts x 3
test models. Temperature 0, no system prompt, single turn, max_tokens 4096.

Appends to results/responses.jsonl. Idempotent: (prompt_id, model) pairs that
already have a successful record are skipped; failed records are retried on
the next run. Options:
  --models claude,gpt,gemini   subset of families (default: all)
  --only PROMPT_ID[,..]        subset of prompts
"""
import argparse
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import common


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="claude,gpt,gemini")
    ap.add_argument("--only", default=None)
    ap.add_argument("--sleep", type=float, default=0.0, help="seconds between calls")
    ap.add_argument("--workers", type=int, default=1, help="concurrent calls")
    args = ap.parse_args()

    prompts = common.load_all_prompts()
    if args.only:
        keep = set(args.only.split(","))
        prompts = [p for p in prompts if p["id"] in keep]
    families = [f.strip() for f in args.models.split(",") if f.strip()]

    done = {(r["prompt_id"], r["model"]) for r in common.read_jsonl(common.RESPONSES_FILE)
            if r.get("status") == "ok"}
    todo = [(p, f) for f in families for p in prompts if (p["id"], f) not in done]
    print(f"{len(prompts)} prompts x {len(families)} models; {len(done)} done, {len(todo)} to run\n")

    counts = {"ok": 0, "fail": 0}
    lock = threading.Lock()

    def work(item):
        i, (p, fam) = item
        model = common.TEST_MODELS[fam]
        label = f"{p['id']} x {fam}"
        rec = {
            "prompt_id": p["id"], "cell": common.cell_of(p), "base_scenario": p["base_scenario"],
            "framing": p["framing"], "register": p["register"], "derivation": p.get("derivation"),
            "model": fam, "model_string": model, "timestamp": common.now(),
            "request": {"model": model, "temperature": common.TEMPERATURE,
                        "max_tokens": common.MAX_TOKENS, "system_prompt": None,
                        "messages": [{"role": "user", "content": p["prompt"]}]},
        }
        try:
            text, finish, meta = common.retry(lambda: common.call_model(model, p["prompt"]), label,
                                              log=lambda m: print(m, flush=True))
            rec.update({"status": "ok", "finish_reason": finish, "response": text, "meta": meta})
            msg = f"ok ({len(text)} chars, finish={finish})"
            key = "ok"
        except Exception as e:  # noqa: BLE001
            rec.update({"status": "error", "finish_reason": None, "response": None,
                        "error": str(e)[:500]})
            msg = f"FAIL {str(e)[:100]}"
            key = "fail"
        common.append_jsonl(common.RESPONSES_FILE, rec)
        with lock:
            counts[key] += 1
            print(f"  [{i}/{len(todo)}] {label} ... {msg}", flush=True)
        if args.sleep:
            time.sleep(args.sleep)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(ex.map(work, enumerate(todo, 1)))
    print(f"\n{counts['ok']} ok, {counts['fail']} failed")
    sys.exit(1 if counts["fail"] else 0)


if __name__ == "__main__":
    main()
