"""
EXPLORATORY, DEV HALF ONLY: how does the deterministic argument-grounding checker behave on NATURAL tool-call errors?

Data: Ma et al., arXiv 2610.18497, public release lm2445/DeRef (Apache-2.0): fcrb (BFCL, real-model wrong calls) and cfb
(ComplexFuncBench, long tool returns). Each argument has a label (correct/wrong) and a derivation path
(visible / no_source / default / format / history_only / placeholder), assigned by the dataset authors' automatic rules.

Split: by query_id, seed 11; this script only reads the DEV half (the test half is never touched, so it stays clean for the
pre-registered run).  Context = request + all history texts.  Nothing is tuned here.

Usage: PYTHONPATH=. python benchmarks/explore_deref_dev.py --dir <folder with fcrb.jsonl, cfb.jsonl>
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.pipeline.arg_ground import check_value  # noqa: E402


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def context_of(row):
    parts = [str(row.get("request") or "")]
    for h in row.get("history") or []:
        parts.append(str(h.get("text", "")))
    return "\n".join(parts)


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


def run(name, rows, tau):
    qids = sorted({r["query_id"] for r in rows})
    random.Random(11).shuffle(qids)
    dev_q = set(qids[: len(qids) // 2])
    dev = [r for r in rows if r["query_id"] in dev_q]
    print(f"\n=== {name}: dev half = {len(dev)} calls of {len(rows)} ({len(dev_q)} of {len(qids)} queries)")
    by_path = defaultdict(lambda: Counter())
    call_scores, call_wrong = [], []
    exact_blocked = []
    for r in dev:
        ctx = context_of(r)
        ctx_l = " ".join(ctx.lower().split())
        scores = []
        ex_block = False
        for a in r["arguments"]:
            if not a.get("in_analysis"):
                continue
            v = check_value(a["name"], a["value"], ctx)
            ungrounded = v.verdict == "UNGROUNDED"
            by_path[(a["path"], a["label"])]["n"] += 1
            by_path[(a["path"], a["label"])]["ungrounded"] += int(ungrounded)
            if v.verdict != "UNCHECKABLE":
                scores.append(v.score)
            sv = " ".join(str(a["value"]).lower().split())
            if sv and not isinstance(a["value"], bool) and sv not in ctx_l:
                ex_block = True
        call_scores.append(min(scores) if scores else 1.0)
        call_wrong.append(r["call_label"] == "wrong")
        exact_blocked.append(ex_block)
    print("argument level: share flagged UNGROUNDED by (derivation path, label)")
    for (path, label), c in sorted(by_path.items()):
        print(f"  {path:12s} {label:8s} n={c['n']:5d}  ungrounded={c['ungrounded'] / c['n']:.3f}")
    cs = np.array(call_scores); cw = np.array(call_wrong); eb = np.array(exact_blocked)
    print(f"call level (n={len(cs)}: {int((~cw).sum())} correct, {int(cw.sum())} wrong)")
    print(f"  AUROC of (1 - call_score) for wrong calls: {auroc(cw, 1 - cs):.3f}")
    for lab, blocked in (("exact-match", eb), (f"type-aware tau={tau}", cs < tau)):
        print(f"  {lab:22s} false-block (correct calls blocked) = {blocked[~cw].mean():.3f}   detection (wrong calls blocked) = {blocked[cw].mean():.3f}")
    return by_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--tau", type=float, default=0.88)
    a = ap.parse_args()
    for name in ("fcrb", "cfb"):
        run(name, load(Path(a.dir) / f"{name}.jsonl"), a.tau)


if __name__ == "__main__":
    main()
