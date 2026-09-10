#!/usr/bin/env python3
"""
LLM Index pilot — elicitation (PILOT.md §4–§8).

Main run:   python3 run_pilot.py                 # 9 frames x 5 models x 10 samples
Subset:     python3 run_pilot.py --models M2,M3 --frames F1,F4 --n 2
Smoke test: python3 run_pilot.py --smoke         # §7: 2 calls/model, F2, retrieval ON
Plan only:  python3 run_pilot.py --dry-run

Every attempt is appended to out/raw/{slot}_{provider}_{model}.jsonl, including
failures (a model with no key in .env gets one NO_API_KEY line per call).
Idempotent: a call_id whose latest line has error == null is skipped; failed
call_ids are re-attempted and the new line is appended (the old one stays).
Retries happen only on transport / 429 / 5xx (§2) and are logged on the line.
"""
import argparse
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import common


def make_record(cfg, slot, mcfg, frame_id, sample_idx, prompt_info, retrieval):
    ro = mcfg["retrieval_off"]
    if retrieval:
        verified_by = mcfg.get("retrieval_on", {}).get("evidence", "n/a")
        status = "on"
    else:
        verified_by = ro["method"] if ro.get("verified_in_pilot_env") else "retrieval_unverified"
        status = "off"
    return {
        "run_id": cfg["run_id"] + ("-smoke" if retrieval else ""),
        "call_id": f"{slot}-{frame_id}-{sample_idx:02d}",
        "timestamp_utc": common.now_utc(),
        "provider": mcfg["provider"],
        "model_string": mcfg["model_string"],
        "model_version": mcfg.get("model_version"),
        "frame": frame_id,
        "sample_idx": sample_idx,
        "prompt_sha256": prompt_info["sha256"],
        "prompt": prompt_info["prompt"],
        "system_prompt": cfg["system_prompt"],
        "temperature": mcfg["default_temperature_documented"],
        "temperature_sent": False,
        "max_tokens": cfg["max_tokens"],
        "retrieval": status,
        "retrieval_verified_by": verified_by,
        "raw_text": None,
        "stop_reason": None,
        "usage": None,
        "latency_ms": None,
        "retries": 0,
        "error": None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=None, help="comma-separated slots, e.g. M2,M3 (default: all)")
    ap.add_argument("--frames", default=None, help="comma-separated frame ids (default: config)")
    ap.add_argument("--n", type=int, default=None, help="samples per cell (default: config)")
    ap.add_argument("--smoke", action="store_true", help="run the §7 retrieval smoke test instead")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=None, help="override per-model concurrency")
    args = ap.parse_args()

    cfg = common.load_config()
    frames = common.load_frames()
    slots = args.models.split(",") if args.models else list(cfg["models"])
    if args.smoke:
        frame_ids = [cfg["smoke_test"]["frame"]]
        n = cfg["smoke_test"]["calls_per_model"]
    else:
        frame_ids = args.frames.split(",") if args.frames else cfg["frames"]
        n = args.n or cfg["samples_per_cell"]
    prompts = common.all_prompts(frames, frame_ids)
    if not args.smoke:
        common.OUT_DIR.mkdir(parents=True, exist_ok=True)
        common.PROMPT_HASHES_FILE.write_text(
            __import__("json").dumps({f: {"sha256": p["sha256"], "block_mode": p["block_mode"], "prompt": p["prompt"]}
                                      for f, p in prompts.items()}, indent=2, ensure_ascii=False) + "\n")

    # Plan
    todo = []
    for slot in slots:
        mcfg = cfg["models"][slot]
        path = common.smoke_file(slot, mcfg) if args.smoke else common.raw_file(slot, mcfg)
        latest = common.latest_by_call_id(common.read_jsonl(path))
        for fid in frame_ids:
            for i in range(1, n + 1):
                cid = f"{slot}-{fid}-{i:02d}"
                if cid in latest and latest[cid].get("error") is None:
                    continue
                todo.append((slot, mcfg, fid, i, path))
    total = len(slots) * len(frame_ids) * n
    print(f"{'SMOKE TEST (retrieval ON)' if args.smoke else 'MAIN RUN (retrieval OFF)'}: "
          f"{len(slots)} models x {len(frame_ids)} frames x {n} = {total} calls; "
          f"{total - len(todo)} already done, {len(todo)} to run")
    for slot in slots:
        mcfg = cfg["models"][slot]
        has_key = bool(common.key_for(mcfg))
        print(f"  {slot} {mcfg['provider']:9s} {mcfg['model_string']:28s} key={'yes' if has_key else 'NO'}")
    if args.dry_run:
        for fid, p in prompts.items():
            print(f"\n--- {fid} [{p['block_mode']}] sha256={p['sha256']}\n{p['prompt']}")
        return

    counts = {"ok": 0, "fail": 0}
    lock = threading.Lock()
    sems = {slot: threading.Semaphore(args.workers or cfg["models"][slot].get("concurrency", 2)) for slot in slots}
    done_n = [0]

    def work(item):
        slot, mcfg, fid, i, path = item
        rec = make_record(cfg, slot, mcfg, fid, i, prompts[fid], args.smoke)
        label = rec["call_id"]
        if not common.key_for(mcfg):
            rec["error"] = f"NO_API_KEY: none of {mcfg['key_env']} set in environment or .env"
            rec["retry_log"] = []
            msg = "FAIL no key"
            key = "fail"
        else:
            with sems[slot]:
                res, retry_log, err, retries, latency = common.call_with_retry(
                    mcfg, rec["prompt"], cfg["max_tokens"], cfg["request_timeout_s"], cfg["retry"],
                    retrieval=args.smoke, log=lambda m: print(f"  {label}{m}", flush=True))
            rec.update({"retries": retries, "retry_log": retry_log, "latency_ms": latency})
            if res is None:
                rec["error"] = err
                msg = f"FAIL {err[:100]}"
                key = "fail"
            else:
                rec.update({
                    "raw_text": res["text"], "stop_reason": res["stop_reason"], "usage": res["usage"],
                    "usage_raw": res.get("usage_raw"), "model_reported": res.get("model_reported"),
                    "empty_response": not (res["text"] or "").strip(),
                    "tool_call_observed": res.get("tool_call_observed"),
                    "retrieval_evidence": res.get("retrieval_evidence"),
                    "request_body": res.get("request_body"),
                })
                if "prompt_feedback" in res:
                    rec["prompt_feedback"] = res["prompt_feedback"]
                if args.smoke:
                    rec["retrieval_verified_by"] = (
                        f"tool call observed: {res.get('retrieval_evidence')}" if res.get("tool_call_observed")
                        else "NO TOOL CALL OBSERVED in response")
                capped = res["stop_reason"] in common.CAP_STOP_REASONS
                msg = (f"ok {len(res['text'])} chars stop={res['stop_reason']}"
                       f"{' CAPPED' if capped else ''}{' EMPTY' if rec['empty_response'] else ''}"
                       f" out={res['usage'].get('output_tokens')} reasoning={res['usage'].get('reasoning_tokens')}"
                       f" {latency / 1000:.0f}s")
                key = "ok"
        common.append_jsonl(path, rec)
        with lock:
            counts[key] += 1
            done_n[0] += 1
            print(f"  [{done_n[0]}/{len(todo)}] {label} {msg}", flush=True)

    workers = sum(sems[s]._value for s in slots) or 1
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(work, todo))
    print(f"\n{counts['ok']} ok, {counts['fail']} failed (all attempts logged under {common.RAW_DIR})")
    sys.exit(1 if counts["fail"] else 0)


if __name__ == "__main__":
    main()
