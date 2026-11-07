"""
Distribution-shift and guarantee study for the ask/block threshold (playbook Stage 2.5, hypothesis H-A3), on REAL scores.

Score: the deterministic checker's call-level grounding score (server/pipeline/arg_ground.call_score, weakest checkable argument against the
premise).  Non-conformity = 1 - score; the policy asks/blocks when non-conformity >= tau.  This score exists for every dataset, so one
threshold can be moved between them.  Datasets (development splits only; no test half is read):
  bfcl      200 BFCL single-turn cases x 30 models, premise = the request, strong errors only (weak-only calls dropped)
  fcrb      DeRef fcrb dev half (630 cases)
  agenthallu  the 124 cases of the AgentHallu confirmatory slice (its hypotheses are closed; used here only as a score source)
  mcpatlas  2,423 clean MCP-Atlas calls (target for the ask rate only; no errors)
Parts: (A) source -> target transfer of a threshold calibrated on the source; (B) repair by recalibrating on n target correct calls;
(C) the same recipe inside one dataset (guarantee against n).  Draws are made by group (query/test id) so correlated calls stay together.
Rules: plain split conformal (marginal) and the Clopper-Pearson rule (pac_tau, calibration-conditional with confidence 0.9).

  PYTHONPATH=. python benchmarks/shift_study.py            (writes benchmarks/shift_scores_dev.json once, then benchmarks/shift_study_dev.json)
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))
from ask_policy import conformal_tau, pac_tau  # noqa: E402

SCORES = ROOT / "benchmarks" / "shift_scores_dev.json"
ALPHAS = (0.05, 0.10, 0.20)


def _call(c):
    return json.loads(c) if isinstance(c, str) else c


def load_json_cases(path, split=None):
    return [c for c in json.loads(Path(path).read_text(encoding="utf-8"))["cases"] if split is None or c.get("split") == split]


def literal(s):
    import ast
    if not isinstance(s, str):
        return s
    try:
        return json.loads(s)
    except Exception:
        return ast.literal_eval(s)


def build_scores():
    from server.pipeline.arg_ground import call_score
    out = {}

    def run(name, cases):
        rows = []
        for c in cases:
            call = literal(c["call"])
            rows.append({"group": c.get("query_id") or c["id"], "ok": str(c["label"]) in ("True", "true", "1"), "nc": 1 - call_score(call.get("arguments", {}), c["premise"])})
        out[name] = rows
        print(name, len(rows), "wrong:", sum(not r["ok"] for r in rows), flush=True)

    run("fcrb", load_json_cases(ROOT / "benchmarks/data/deref/cases_fcrb.json", "dev"))
    run("agenthallu", load_json_cases(ROOT / "benchmarks/data/agenthallu/cases_eval.json"))
    m = json.loads((ROOT / "benchmarks/data/mcpatlas/cases.json").read_text(encoding="utf-8"))
    run("mcpatlas", m["cases"] if isinstance(m, dict) else m)

    from decidability import bfcl_call_status
    st = bfcl_call_status()
    d = json.loads((ROOT / "benchmarks/data/bfcl/consensus_cases.json").read_text(encoding="utf-8"))
    rows = []
    for r in d["records"]:
        s = st.get(r["test_id"] + "|" + r["model"], "correct")
        if s == "weak_only":
            continue
        nc = max(1 - call_score(c["arguments"], r["request"]) for c in r["calls"])
        rows.append({"group": r["test_id"], "ok": s == "correct", "nc": nc})
    out["bfcl"] = rows
    print("bfcl", len(rows), "wrong:", sum(not r["ok"] for r in rows), flush=True)
    SCORES.write_text(json.dumps(out), encoding="utf-8")
    return out


def arr(rows):
    return (np.array([r["nc"] for r in rows]), np.array([r["ok"] for r in rows]), np.array([r["group"] for r in rows]))


def fast_conformal(s, alpha):
    """Same rule as ask_policy.conformal_tau, vectorised: smallest level t with (#{s >= t} + 1) / (n + 1) <= alpha."""
    s = np.sort(np.asarray(s)); n = len(s)
    lv = np.unique(s)
    cnt = n - np.searchsorted(s, lv, side="left")
    ok = (cnt + 1) / (n + 1) <= alpha
    return float(lv[np.argmax(ok)]) if ok.any() else float("inf")


def fast_pac(s, alpha, delta=0.1):
    """Same rule as ask_policy.pac_tau, vectorised (one-sided Clopper-Pearson upper bound on the ask rate)."""
    from scipy.stats import beta
    s = np.sort(np.asarray(s)); n = len(s)
    lv = np.unique(s)
    k = n - np.searchsorted(s, lv, side="left")
    ub = np.where(k >= n, 1.0, beta.ppf(1 - delta, k + 1, np.maximum(n - k, 1)))
    ok = ub <= alpha
    return float(lv[np.argmax(ok)]) if ok.any() else float("inf")


def tau_of(rule, s, alpha):
    return fast_conformal(s, alpha) if rule == "conformal" else fast_pac(s, alpha)


_GROUP_CACHE = {}


def _groups(g):
    key = id(g)
    if key not in _GROUP_CACHE:
        ug, inv = np.unique(g, return_inverse=True)
        _GROUP_CACHE[key] = (len(ug), inv)
    return _GROUP_CACHE[key]


def draw(rows_arrays, n, rng, rule, alpha):
    """Calibrate on whole groups (shuffled) until at least n correct calls are collected; evaluate on the remaining groups."""
    s, ok, g = rows_arrays
    ng, inv = _groups(g)
    n_ok = np.bincount(inv, weights=ok.astype(float), minlength=ng)
    order = rng.permutation(np.where(n_ok > 0)[0])
    cum = np.cumsum(n_ok[order])
    take = order[: int(np.searchsorted(cum, n) + 1)]
    cal = np.isin(inv, take)
    cal_ok = cal & ok
    te = ~cal
    if (te & ok).sum() < 20 or cal_ok.sum() == 0:
        return None
    tau = tau_of(rule, s[cal_ok], alpha)
    ask = s >= tau
    return float(ask[te & ok].mean()), (float(ask[te & ~ok].mean()) if (te & ~ok).any() else float("nan")), int(cal_ok.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=1000)
    ap.add_argument("--out", default=str(ROOT / "benchmarks" / "shift_study_dev.json"))
    a = ap.parse_args()
    data = json.loads(SCORES.read_text(encoding="utf-8")) if SCORES.exists() else build_scores()
    D = {k: arr(v) for k, v in data.items()}
    rng = np.random.default_rng(0)
    res = {"datasets": {k: {"n": len(v[0]), "n_correct": int(v[1].sum()), "n_wrong": int((~v[1]).sum())} for k, v in D.items()}}

    # (A) transfer: threshold from a random half (by group) of the source correct calls, applied to all target correct calls
    A = {}
    for src in ("bfcl", "fcrb", "agenthallu"):
        for tgt in ("bfcl", "fcrb", "agenthallu", "mcpatlas"):
            if src == tgt:
                continue
            for rule in ("conformal", "pac"):
                for alpha in ALPHAS:
                    rates, dets = [], []
                    s, ok, g = D[src]
                    ts, tok, _ = D[tgt]
                    for _ in range(a.draws):
                        ng, inv = _groups(g)
                        cal = np.isin(inv, rng.permutation(ng)[: ng // 2])
                        tau = tau_of(rule, s[cal & ok], alpha)
                        ask = ts >= tau
                        rates.append(float(ask[tok].mean()))
                        if (~tok).any():
                            dets.append(float(ask[~tok].mean()))
                    rates = np.array(rates)
                    A[f"{src}->{tgt}|{rule}|{alpha}"] = {"ask_rate_on_target_correct": round(float(rates.mean()), 3), "p05_p95": [round(float(np.percentile(rates, 5)), 3), round(float(np.percentile(rates, 95)), 3)],
                                                          "share_draws_within_alpha": round(float((rates <= alpha).mean()), 3),
                                                          "wrong_caught": round(float(np.mean(dets)), 3) if dets else None}
    res["A_transfer"] = A

    # (B)/(C) calibrate on n target correct calls (n=0 uses the source threshold); target = same dataset gives the in-distribution guarantee
    B = {}
    for tgt in ("bfcl", "fcrb", "agenthallu", "mcpatlas"):
        for n in (25, 50, 100, 200, 500):
            if n > 0.6 * int(D[tgt][1].sum()):
                continue
            for rule in ("conformal", "pac"):
                for alpha in ALPHAS:
                    out = [draw(D[tgt], n, rng, rule, alpha) for _ in range(a.draws)]
                    out = [o for o in out if o]
                    if not out:
                        continue
                    rates = np.array([o[0] for o in out]); dets = np.array([o[1] for o in out])
                    B[f"{tgt}|n={n}|{rule}|{alpha}"] = {"draws": len(out), "mean_cal_correct": round(float(np.mean([o[2] for o in out])), 1),
                                                          "ask_rate_on_held_out_correct": round(float(rates.mean()), 3),
                                                          "share_draws_within_alpha": round(float((rates <= alpha).mean()), 3),
                                                          "wrong_caught": None if np.all(np.isnan(dets)) else round(float(np.nanmean(dets)), 3)}
    res["B_recalibration_and_guarantee_vs_n"] = B
    Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("wrote", a.out)
    print(json.dumps(res["datasets"]))
    for k in ("bfcl->agenthallu|conformal|0.1", "bfcl->fcrb|conformal|0.1", "fcrb->agenthallu|conformal|0.1", "fcrb->bfcl|conformal|0.1", "bfcl->mcpatlas|conformal|0.1", "agenthallu->fcrb|conformal|0.1"):
        print(k, A.get(k))


if __name__ == "__main__":
    main()
