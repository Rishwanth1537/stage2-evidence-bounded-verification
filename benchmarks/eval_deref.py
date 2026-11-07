"""
Deterministic systems (S1 exact match, S2 type-aware grounding) on the DeRef cases, with a per-derivation-path breakdown.

  python benchmarks/eval_deref.py --dataset fcrb --split dev
  python benchmarks/eval_deref.py --dataset fcrb --split test --allow-test --note "pre-registered run S1/S2"

TEST-HALF GUARD: reading a test half needs --allow-test and appends a line to benchmarks/test_run_ledger.jsonl (committed), so every
look at test data is on record (see review/PREREGISTRATION.md).  Dev-half runs are free.

Per call S2 uses only the arguments the dataset marks in_analysis (as the dataset authors do); S1 flags an argument whose lower-cased
text is not a substring of the context.  Call score = weakest argument match (check_value score); exactly as in the exploratory run.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.pipeline.arg_ground import check_value, conformal_threshold  # noqa: E402

DATA = ROOT / "benchmarks" / "data" / "deref"
LEDGER = ROOT / "benchmarks" / "test_run_ledger.jsonl"


def score_case(case):
    """Return (call_score_s2, exact_blocked, per_arg list of dicts)."""
    ctx = case["premise"]
    ctx_l = " ".join(ctx.lower().split())
    scores, exact_block, per_arg = [], False, []
    for a in case["args_meta"]:
        if not a["in_analysis"]:
            continue
        v = check_value(a["name"], a["value"], ctx)
        sv = " ".join(str(a["value"]).lower().split())
        ex = bool(sv) and not isinstance(a["value"], bool) and a["value"] is not None and sv not in ctx_l
        exact_block |= ex
        if v.verdict != "UNCHECKABLE":
            scores.append(v.score)
        per_arg.append({"name": a["name"], "label": a["label"], "path": a["path"], "s2_ungrounded": v.verdict == "UNGROUNDED",
                        "s1_ungrounded": ex, "score": v.score})
    return (min(scores) if scores else 1.0), exact_block, per_arg


def auroc(y, s):
    y = np.asarray(y, bool); s = np.asarray(s, float)
    n1, n0 = y.sum(), (~y).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s)); xs = s[order]
    _, start, cnt = np.unique(xs, return_index=True, return_counts=True)
    ranks[order] = np.repeat(start + (cnt + 1) / 2.0, cnt)
    return float((ranks[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def evaluate(cases, tau=0.88):
    sc, eb, paths = [], [], defaultdict(lambda: {"n": 0, "s2": 0, "s1": 0})
    for c in cases:
        s, e, pa = score_case(c)
        sc.append(s); eb.append(e)
        for a in pa:
            d = paths[(a["path"], a["label"])]
            d["n"] += 1; d["s2"] += int(a["s2_ungrounded"]); d["s1"] += int(a["s1_ungrounded"])
    sc = np.array(sc); eb = np.array(eb); correct = np.array([c["label"] for c in cases], bool)
    res = {"n": len(cases), "n_correct": int(correct.sum()), "n_wrong": int((~correct).sum()),
           "auroc_s2_wrong_vs_correct": auroc(~correct, 1 - sc),
           "s1_exact": {"false_block": float(eb[correct].mean()), "detection": float(eb[~correct].mean())},
           f"s2_tau_{tau}": {"false_block": float((sc < tau)[correct].mean()), "detection": float((sc < tau)[~correct].mean())},
           "by_path": {f"{p}|{l}": {"n": d["n"], "s1_flagged": d["s1"] / d["n"], "s2_flagged": d["s2"] / d["n"]} for (p, l), d in sorted(paths.items())}}
    return res, sc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["fcrb", "cfb"], required=True)
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    ap.add_argument("--allow-test", action="store_true")
    ap.add_argument("--note", default="")
    ap.add_argument("--tau", type=float, default=0.88)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.split == "test":
        if not a.allow_test:
            sys.exit("test half requested without --allow-test (pre-registration guard)")
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"when": datetime.datetime.now().isoformat(timespec="seconds"), "script": "eval_deref.py",
                                "dataset": a.dataset, "split": "test", "note": a.note}) + "\n")
    data = json.loads((DATA / f"cases_{a.dataset}.json").read_text())
    cases = [c for c in data["cases"] if c["split"] == a.split]
    res, _ = evaluate(cases, a.tau)
    res.update({"dataset": a.dataset, "split": a.split, "meta": data["meta"]})
    out = Path(a.out) if a.out else ROOT / "benchmarks" / f"deref_{a.dataset}_{a.split}_results.json"
    out.write_text(json.dumps(res, indent=2))
    print(f"{a.dataset}/{a.split}: n={res['n']} ({res['n_correct']} correct, {res['n_wrong']} wrong)  AUROC(S2)={res['auroc_s2_wrong_vs_correct']:.3f}")
    for k in ("s1_exact", f"s2_tau_{a.tau}"):
        print(f"  {k:14s} false-block={res[k]['false_block']:.3f}  detection={res[k]['detection']:.3f}")
    for k, v in res["by_path"].items():
        print(f"  {k:22s} n={v['n']:4d}  S1 flagged={v['s1_flagged']:.3f}  S2 flagged={v['s2_flagged']:.3f}")
    print("wrote", out)


if __name__ == "__main__":
    main()
