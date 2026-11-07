"""
Real self-consistency as the ask trigger (playbook Stage 2.3, hypothesis H-A1).

One model answers the 200 BFCL single-turn cases of benchmarks/data/bfcl/consensus_cases.json:
  - one greedy reply (temperature 0)        = the primary call
  - k replies at temperature 0.8            = the samples
Score of an argument = share of the k samples whose value for that argument differs from the primary (a missing argument, a different
function or an unparseable reply counts as different).  Score of a call = maximum over its arguments.  The same primary value is also scored
against the 30 recorded model outputs of the consensus index (peer disagreement).  The primary call is labelled against the BFCL gold; calls
whose only errors are weak labels (format variants, optional arguments gold leaves blank) are dropped, so the evaluation is on strong errors.

  PYTHONPATH=. python benchmarks/selfconsistency_bfcl.py --provider nvidia --model nvidia/nemotron-3.5-bolt-e4b --k 4 --splits 1000

Every reply is cached in benchmarks/llm_selfconsistency_cache.jsonl (empty replies are not cached).  Development-set analysis, not a locked test.
Nothing is read from a precomputed file: if the replies are missing the script calls the API (or stops with --no-api).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))

from analyze_consensus import auroc, canon  # noqa: E402
from ask_policy import boot_tau, cluster_tau, conformal_tau, contract_flag, pac_tau  # noqa: E402
from decidability import relaxed_equal  # noqa: E402
from keys import get_key  # noqa: E402
from llm_judge_args import PROVIDERS, chat  # noqa: E402
from load_bfcl_consensus import align, fname, label_call, load_gorilla, parse_calls  # noqa: E402

CACHE = ROOT / "benchmarks" / "llm_selfconsistency_cache.jsonl"
SYSTEM_V1 = "You are a function-calling assistant. Reply ONLY with the call(s) in python syntax, a list like [func(arg=value)]."
SYSTEM_V2 = SYSTEM_V1 + ' Do not use JSON. Example of the required format: [get_weather(city="Paris", unit="celsius")]'
SYSTEM = SYSTEM_V2     # Deviation 15 of review/PREREGISTRATION.md; --prompt v1 reproduces the playbook wording
_lock = threading.Lock()


def messages_for(rec):
    user = "Available functions:\n" + json.dumps(rec["function_schemas"], indent=1) + "\n\nUser request: " + rec["request"]
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def key_of(model, temp, idx, msgs):
    raw = json.dumps({"m": msgs, "model": model, "t": temp, "i": idx}, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def load_cache():
    out = {}
    if CACHE.exists():
        for ln in CACHE.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                r = json.loads(ln)
                out[r["key"]] = r["text"]
    return out


def reply(cache, provider, model, msgs, temp, idx, no_api):
    k = key_of(model, temp, idx, msgs)
    if k in cache:
        return cache[k]
    if no_api:
        return None
    try:
        out, _ = chat(provider, get_key(PROVIDERS[provider]["key_env"]), model, msgs, max_tokens=400, temperature=temp)
        text = out["choices"][0]["message"].get("content")
    except Exception as e:                      # keep going; the case is reported as missing
        print("API failure:", str(e)[:150], file=sys.stderr)
        return None
    if not text or not text.strip():
        return None
    with _lock:
        cache[k] = text
        with open(CACHE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"key": k, "text": text, "model": model, "temp": temp, "idx": idx}) + "\n")
    return text


def props_of_factory(schemas):
    def props_of(name):
        for s in schemas:
            if fname(s["name"]) == name:
                return s.get("parameters", {}).get("properties", {})
        return {}
    return props_of


def status_and_labels(pred_calls, gold_calls, schemas):
    """-> ('correct'|'weak_only'|'strong'|'unaligned', pairs) with pairs = [(gold_idx, pred_idx)]."""
    props_of = props_of_factory(schemas)
    pairs = align(pred_calls, gold_calls, props_of)
    if pairs is None:
        return "unaligned", None
    status = "correct"
    for gi, pi in pairs:
        gfn = next(iter(gold_calls[gi]))
        gargs = gold_calls[gi][gfn]
        pname, pargs = pred_calls[pi]
        props = props_of(fname(pname))
        labels, _ = label_call(pargs, gargs, props)
        for a, lab in labels.items():
            if lab["label"] == "correct":
                continue
            alts = list(gargs.get(a, []))
            default = props.get(a, {}).get("default")
            weak = relaxed_equal(pargs[a], alts, default) or any(isinstance(g, str) and g == "" for g in alts)
            if not weak:
                return "strong", pairs
            status = "weak_only"
    return status, pairs


def self_score(primary, samples):
    """Per-argument disagreement rates and the call score (max). samples: list of parsed call lists or None."""
    per = {}
    nth = defaultdict(int)
    for pi, (name, args) in enumerate(primary):
        occ = nth[fname(name)]
        nth[fname(name)] += 1
        for a, v in args.items():
            diff = 0
            for sc in samples:
                same = False
                if sc:
                    cands = [c for c in sc if fname(c[0]) == fname(name)]
                    if occ < len(cands) and a in cands[occ][1]:
                        same = canon(cands[occ][1][a]) == canon(v)
                diff += 0 if same else 1
            per[(pi, a)] = diff / max(1, len(samples))
    return per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="nvidia", choices=sorted(PROVIDERS))
    ap.add_argument("--model", default="nvidia/nemotron-3.5-bolt-e4b")
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--splits", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--prompt", choices=("v1", "v2"), default="v2")
    ap.add_argument("--no-api", action="store_true", help="use cached replies only")
    ap.add_argument("--out", default=str(ROOT / "benchmarks" / "selfconsistency_dev.json"))
    a = ap.parse_args()

    global SYSTEM
    SYSTEM = SYSTEM_V1 if a.prompt == "v1" else SYSTEM_V2
    d = json.loads((ROOT / "benchmarks/data/bfcl/consensus_cases.json").read_text(encoding="utf-8"))
    first = {}
    for r in d["records"]:
        first.setdefault(r["test_id"], r)
    ids = sorted(first)[: a.limit or None]
    gold = load_gorilla()
    index = {s: {m: canon(x["value"]) for m, x in pm.items()} for s, pm in d["consensus_index"].items()}
    cache = load_cache()

    jobs = []
    for tid in ids:
        msgs = messages_for(first[tid])
        jobs.append((tid, 0.0, 0, msgs))
        jobs += [(tid, 0.8, i, msgs) for i in range(1, a.k + 1)]
    t0 = time.time()

    def run(j):
        tid, temp, idx, msgs = j
        return j, reply(cache, a.provider, a.model, msgs, temp, idx, a.no_api)

    with ThreadPoolExecutor(a.workers) as ex:
        results = list(ex.map(run, jobs))
    print(f"replies collected in {time.time() - t0:.0f}s")
    text = {(j[0], j[2]): t for j, t in results}

    rows, skipped = [], defaultdict(int)
    for tid in ids:
        rec = first[tid]
        g = gold[tid]["ground_truth"]
        if text.get((tid, 0)) is None:
            skipped["no_primary_reply"] += 1
            continue
        primary, err, _ = parse_calls(text[(tid, 0)])
        if not primary:
            skipped["primary_unparseable"] += 1
            continue
        status, pairs = status_and_labels(primary, g, rec["function_schemas"])
        if status == "unaligned":
            skipped["primary_function_mismatch"] += 1
            continue
        if status == "weak_only":
            skipped["weak_only"] += 1
            continue
        samples = []
        for i in range(1, a.k + 1):
            t = text.get((tid, i))
            samples.append(parse_calls(t)[0] if t else None)
        sc = self_score(primary, samples)
        gold_idx = {pi: gi for gi, pi in pairs}
        peer_best, sc_best = 0.0, 0.0
        for (pi, arg), v in sc.items():
            sc_best = max(sc_best, v)
            slot = index.get(f"{tid}|{gold_idx[pi]}|{arg}")
            if slot and len(slot) >= 5:
                pv = canon(primary[pi][1][arg])
                peer_best = max(peer_best, 1 - sum(x == pv for x in slot.values()) / len(slot))
        cf, _ = contract_flag({"calls": [{"function": n, "arguments": ar} for n, ar in primary], "function_schemas": rec["function_schemas"]})
        rows.append({"test": tid, "ok": status == "correct", "sc": sc_best, "peer": peer_best, "contract": float(cf), "n_replies": sum(s is not None for s in samples)})

    ok = np.array([r["ok"] for r in rows])
    sc = np.array([r["sc"] for r in rows]); peer = np.array([r["peer"] for r in rows]); con = np.array([r["contract"] for r in rows])
    union = sc + peer
    tests = np.array([r["test"] for r in rows]); ut = np.unique(tests)
    res = {"prompt": a.prompt, "model": a.model, "provider": a.provider, "k": a.k, "n_cases": len(ids), "skipped": dict(skipped), "n_calls": len(rows),
           "n_wrong_strong": int((~ok).sum()), "rows": rows, "mean_samples_returned": round(float(np.mean([r["n_replies"] for r in rows])), 2),
           "auroc": {n: round(float(auroc(~ok, s)), 3) for n, s in (("self_consistency", sc), ("peer", peer), ("union_sum", union), ("contract", con))}}
    print(json.dumps({k: v for k, v in res.items()}, indent=1))
    if (~ok).sum() < 5 or ok.sum() < 20:
        print("too few calls to run the conformal analysis"); Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8"); return

    rng = np.random.default_rng(0)
    by_alpha = {}
    for alpha in (0.05, 0.10, 0.20):
        agg = defaultdict(list)
        for _ in range(a.splits):
            perm = rng.permutation(ut); half = set(perm[: len(ut) // 2].tolist())
            cal = np.array([t in half for t in tests]); te = ~cal
            for name, s in (("self", sc), ("peer", peer), ("union", union)):
                for rule in ("conformal", "pac", "cluster", "boot"):
                    cs, ct = s[cal & ok], tests[cal & ok]
                    tau = {"conformal": lambda: conformal_tau(cs, alpha), "pac": lambda: pac_tau(cs, alpha),
                           "cluster": lambda: cluster_tau(cs, ct, alpha), "boot": lambda: boot_tau(cs, ct, alpha)}[rule]()
                    ask = s >= tau
                    agg[f"{name}_{rule}_rate"].append(float(ask[te & ok].mean()))
                    agg[f"{name}_{rule}_caught"].append(float(ask[te & ~ok].mean()) if (te & ~ok).any() else np.nan)
            ask_c = con > 0
            agg["contract_rate"].append(float(ask_c[te & ok].mean()))
            agg["contract_caught"].append(float(ask_c[te & ~ok].mean()) if (te & ~ok).any() else np.nan)
        row = {}
        for k in sorted({x.rsplit("_", 1)[0] for x in agg}):
            rc, cw = np.array(agg[k + "_rate"]), np.array(agg[k + "_caught"])
            row[k] = {"ask_rate_on_correct": round(float(rc.mean()), 3), "share_of_splits_within_alpha": round(float((rc <= alpha).mean()), 3),
                      "wrong_caught": round(float(np.nanmean(cw)), 3), "wrong_caught_p05_p95": [round(float(np.nanpercentile(cw, 5)), 3), round(float(np.nanpercentile(cw, 95)), 3)]}
        by_alpha[str(alpha)] = row
    res["by_alpha"] = by_alpha
    r10 = by_alpha["0.1"]
    delta = (r10["self_conformal"]["wrong_caught"] - r10["contract"]["wrong_caught"]) * 100
    res["H_A1"] = {"alpha": 0.10, "self_consistency_caught": r10["self_conformal"]["wrong_caught"], "contract_caught": r10["contract"]["wrong_caught"],
                   "delta_points": round(delta, 1), "supported_if_delta_ge_15": bool(delta >= 15.0),
                   "peer_caught": r10["peer_conformal"]["wrong_caught"], "union_caught": r10["union_conformal"]["wrong_caught"],
                   "cost_objection_rule": "self-consistency AUROC < 0.70 while peer AUROC > 0.85 means the cost objection stands"}
    Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res["H_A1"], indent=1)); print("wrote", a.out)


if __name__ == "__main__":
    main()
