"""
Evaluate argument-grounding methods on ArgGround-Bench (benchmarks/argground_bench.json).

Methods (all deterministic unless noted):
  exact       any string/number argument whose literal text is not a substring of the context -> block (SAAG-style exact match)
  arg_ground  per-argument type-aware normalised matching (server/pipeline/arg_ground.py)
Reported: false-block rate (consistent calls blocked), detection rate (injected errors blocked), accuracy, balanced accuracy,
per-mutation detection, bootstrap 95% CIs, and the 'legitimately ungrounded' share of gold calls.

Usage:  PYTHONPATH=. python benchmarks/eval_argground.py [--split dev]
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.pipeline.arg_ground import call_is_grounded, call_score, conformal_threshold  # noqa: E402
from benchmarks.splits import load_split  # noqa: E402


def exact_ok(args, context):
    ctx = re.sub(r"\s+", " ", context.lower())
    for v in args.values():
        if isinstance(v, bool) or v is None:
            continue
        if isinstance(v, (int, float, str)):
            s = str(v).lower().strip()
            if isinstance(v, float) and v == int(v):
                s = str(int(v))
            if s and s not in ctx:
                return False
    return True


def split_cases(cases, seed=11):
    rng = random.Random(seed)
    ids = sorted({c["premise"] for c in cases})
    rng.shuffle(ids)
    dev_prem = set(ids[: len(ids) // 2])
    dev = [c for c in cases if c["premise"] in dev_prem]
    test = [c for c in cases if c["premise"] not in dev_prem]
    return dev, test


def summarize(cases, preds_ok):
    y = np.array([c["label"] for c in cases], bool)         # True = consistent
    ok = np.array(preds_ok, bool)                           # True = allowed
    fb = float((~ok[y]).mean())                             # false-block rate among consistent calls
    det = float((~ok[~y]).mean())                           # detection rate among injected errors
    acc = float((ok == y).mean())
    return {"n": len(cases), "false_block_rate": fb, "detection_rate": det, "accuracy": acc, "balanced_accuracy": (1 - fb + det) / 2}


def boot(cases, preds_ok, n=1000, seed=0):
    rng = np.random.default_rng(seed)
    y = np.array([c["label"] for c in cases], bool); ok = np.array(preds_ok, bool)
    fbs, dets = [], []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        yy, oo = y[i], ok[i]
        if yy.all() or (~yy).all():
            continue
        fbs.append((~oo[yy]).mean()); dets.append((~oo[~yy]).mean())
    q = lambda a: [round(float(np.percentile(a, 2.5)), 4), round(float(np.percentile(a, 97.5)), 4)]
    return {"false_block_rate_95ci": q(fbs), "detection_rate_95ci": q(dets)}


def conformal_eval(dev, test, alphas=(0.02, 0.05, 0.10, 0.15)):
    """Calibrate 'block iff call_score < tau' on DEV genuine calls for each alpha; report FBR / detection on TEST."""
    gold_dev = [call_score(c["call"]["arguments"], c["premise"]) for c in dev if c["label"]]
    sc_test = [call_score(c["call"]["arguments"], c["premise"]) for c in test]
    rows = {}
    for a in alphas:
        tau = conformal_threshold(gold_dev, a)
        ok = [s >= tau for s in sc_test]
        m = summarize(test, ok); m.update(boot(test, ok)); m["tau"] = round(float(tau), 4); m["alpha"] = a
        m["guarantee_met_on_test"] = bool(m["false_block_rate"] <= a + 1e-12)
        rows[str(a)] = m
        print(f"  conformal alpha={a:<5} tau={tau:.3f}  FBR={m['false_block_rate']:.3f} {m['false_block_rate_95ci']}  DET={m['detection_rate']:.3f}  {'(<= alpha)' if m['guarantee_met_on_test'] else '(> alpha)'}")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", default=str(ROOT / "benchmarks" / "argground_bench.json"))
    ap.add_argument("--split", default="dev", choices=["dev", "test", "all"])
    ap.add_argument("--allow-test", action="store_true", help="required for --split test (pre-registration guard)")
    ap.add_argument("--note", default="", help="reason/purpose for loading test split")
    ap.add_argument("--output", default=str(ROOT / "benchmarks" / "argground_results.json"))
    a = ap.parse_args()

    use = load_split(
        dataset="argground",
        split=a.split,
        purpose="eval_argground evaluation",
        reason=a.note,
        allow_test=a.allow_test,
    )

    methods = {"exact": lambda c: exact_ok(c["call"]["arguments"], c["premise"]),
               "arg_ground": lambda c: call_is_grounded(c["call"]["arguments"], c["premise"]),
               "arg_ground+schema": lambda c: call_is_grounded(c["call"]["arguments"], c["premise"], c["call"].get("schema"), "required_only")}
    out = {"split": a.split, "n": len(use), "methods": {}}
    for name, fn in methods.items():
        preds = [fn(c) for c in use]
        m = summarize(use, preds); m.update(boot(use, preds))
        bym = defaultdict(list)
        for c, p in zip(use, preds):
            if not c["label"]:
                bym[c["mutation"]].append(not p)
        m["detection_by_mutation"] = {k: round(float(np.mean(v)), 3) for k, v in sorted(bym.items())}
        out["methods"][name] = m
        print(f"{name:11s} FBR={m['false_block_rate']:.3f} {m['false_block_rate_95ci']} DET={m['detection_rate']:.3f} {m['detection_rate_95ci']} "
              f"acc={m['accuracy']:.3f} bal={m['balanced_accuracy']:.3f}  by mutation: {m['detection_by_mutation']}")
    if a.split == "test":
        print("conformal calibration (tau from DEV genuine calls, evaluated on TEST):")
        dev = load_split("argground", split="dev")
        out["conformal"] = conformal_eval(dev, use)
    Path(a.output).write_text(json.dumps(out, indent=2))
    print("n =", len(use), "(consistent", sum(c['label'] for c in use), ")  wrote", a.output)


if __name__ == "__main__":
    main()
