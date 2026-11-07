"""
Replicable LLM-AggreFact subsample evaluation of the NLI component (ENTAILMENT-ONLY, no GED).

Compares, on the SAME seeded random test sample and with the claim fed to the NLI model unchanged:
  truncate  : whole document, tokenizer truncation at 512 tokens (the original behaviour)
  windowed  : 180-word windows with 40-word overlap, max entailment over windows (server/pipeline/entailment.py)

Primary metrics are threshold-free (AUROC) and balanced accuracy, because ~78% of test claims are 'supported'.
Threshold is fixed at configs/thresholds.yaml (0.40); nothing is tuned on the sample.

Usage:  PYTHONPATH=. python benchmarks/aggrefact_sample.py --n 500 --seed 42
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import torch  # noqa: E402
from transformers import AutoModelForSequenceClassification, AutoTokenizer  # noqa: E402

from server import config  # noqa: E402
from server.pipeline.entailment import MODEL_NAME, _premise_windows  # noqa: E402


def auroc(y, s):
    y, s = np.asarray(y, bool), np.asarray(s, float)
    n1, n0 = y.sum(), (~y).sum()
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s))
    xs = s[order]
    _, start, cnt = np.unique(xs, return_index=True, return_counts=True)
    ranks[order] = np.repeat(start + (cnt + 1) / 2.0, cnt)
    return float((ranks[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def conf(y, p):
    y, p = np.asarray(y, bool), np.asarray(p, bool)
    return int((p & y).sum()), int((p & ~y).sum()), int((~p & ~y).sum()), int((~p & y).sum())


def summarize(y, s, thr):
    tp, fp, tn, fn = conf(y, s >= thr)
    rec, spec = tp / max(1, tp + fn), tn / max(1, tn + fp)
    prec = tp / max(1, tp + fp)
    return dict(auroc=auroc(y, s), balanced_accuracy=(rec + spec) / 2, accuracy=(tp + tn) / len(y),
                precision=prec, recall=rec, specificity=spec, tp=tp, fp=fp, tn=tn, fn=fn)


def boot(y, a, b, thr, n_boot=1000, seed=0):
    rng = np.random.default_rng(seed)
    y = np.asarray(y, bool)
    out = {"auroc_a": [], "auroc_b": [], "ba_a": [], "ba_b": [], "d_auroc": [], "d_ba": []}
    for _ in range(n_boot):
        i = rng.integers(0, len(y), len(y))
        if y[i].all() or (~y[i]).all():
            continue
        sa, sb = summarize(y[i], a[i], thr), summarize(y[i], b[i], thr)
        out["auroc_a"].append(sa["auroc"]); out["auroc_b"].append(sb["auroc"])
        out["ba_a"].append(sa["balanced_accuracy"]); out["ba_b"].append(sb["balanced_accuracy"])
        out["d_auroc"].append(sb["auroc"] - sa["auroc"]); out["d_ba"].append(sb["balanced_accuracy"] - sa["balanced_accuracy"])
    q = lambda v: [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)]
    return {k: q(v) for k, v in out.items()}


@torch.no_grad()
def score_pairs(tok, model, entail_idx, prem, hyp, batch=16, label=""):
    lengths = np.array([len(p) + len(h) for p, h in zip(prem, hyp)])
    order = np.argsort(-lengths)
    out = np.zeros(len(prem))
    t0 = time.time()
    for b in range(0, len(order), batch):
        idx = order[b:b + batch]
        enc = tok([prem[i] for i in idx], [hyp[i] for i in idx], truncation=True, max_length=512,
                  padding=True, return_tensors="pt")
        probs = torch.softmax(model(**enc).logits.float(), dim=-1)[:, entail_idx].numpy()
        out[idx] = probs
        if (b // batch) % 10 == 0:
            print(f"  [{label}] {b + len(idx)}/{len(order)} pairs  {time.time() - t0:.0f}s", flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--split", default="test")
    ap.add_argument("--out", default=str(ROOT / "benchmarks" / "aggrefact_sample_results.json"))
    args = ap.parse_args()

    df = pd.read_parquet(ROOT / f"{args.split}-00000-of-00001.parquet")
    df = df.sample(n=args.n, random_state=args.seed).reset_index(drop=True)
    y = df["label"].astype(int).values.astype(bool)
    print(f"{len(df)} rows, supported fraction {y.mean():.3f}", flush=True)

    tok = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME).eval()
    ent = [k for k, v in model.config.id2label.items() if v.lower() == "entailment"][0]
    claims = [c.strip() for c in df["claim"]]

    s_trunc = score_pairs(tok, model, ent, df["doc"].tolist(), claims, label="truncate")

    rec, prem, hyp = [], [], []
    for i, (d, c) in enumerate(zip(df["doc"], claims)):
        for w in _premise_windows(d):
            rec.append(i); prem.append(w); hyp.append(c)
    print(f"windowed: {len(prem)} window pairs for {len(df)} rows", flush=True)
    sc = score_pairs(tok, model, ent, prem, hyp, label="windowed")
    s_win = np.zeros(len(df))
    for r, v in zip(rec, sc):
        s_win[r] = max(s_win[r], v)

    thr = config.ENTAILMENT_THRESHOLD
    res = {
        "setup": {"model": MODEL_NAME, "split": args.split, "n": len(df), "seed": args.seed, "threshold_fixed": thr,
                  "claim_fed_unchanged": True, "window_words": 180, "overlap_words": 40,
                  "evaluation": "ENTAILMENT-ONLY (no GED)", "supported_fraction": round(float(y.mean()), 4),
                  "majority_baseline_accuracy": round(float(max(y.mean(), 1 - y.mean())), 4),
                  "windows_total": len(prem)},
        "truncate": summarize(y, s_trunc, thr),
        "windowed": summarize(y, s_win, thr),
        "bootstrap_95ci": boot(y, s_trunc, s_win, thr),
    }
    if "dataset" in df.columns:
        res["per_source"] = {}
        for name, g in df.assign(_t=s_trunc, _w=s_win).groupby("dataset"):
            yy = g["label"].astype(int).values.astype(bool)
            if yy.all() or (~yy).all() or len(g) < 10:
                continue
            res["per_source"][name] = {"n": len(g), "auroc_truncate": round(auroc(yy, g["_t"].values), 3),
                                       "auroc_windowed": round(auroc(yy, g["_w"].values), 3)}
    res["predictions"] = [{"i": i, "label": bool(y[i]), "truncate": round(float(s_trunc[i]), 4),
                           "windowed": round(float(s_win[i]), 4)} for i in range(len(df))]
    Path(args.out).write_text(json.dumps(res, indent=2, default=float))
    for k in ("truncate", "windowed"):
        m = res[k]
        print(f"{k:<9} AUROC={m['auroc']:.3f} balAcc={m['balanced_accuracy']:.3f} acc={m['accuracy']:.3f} "
              f"P={m['precision']:.3f} R={m['recall']:.3f} spec={m['specificity']:.3f}")
    print("95% CI:", json.dumps(res["bootstrap_95ci"]))
    print("majority baseline acc:", res["setup"]["majority_baseline_accuracy"], "| wrote", args.out)


if __name__ == "__main__":
    main()
