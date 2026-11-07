"""
Pool the per-model self-consistency results (Deviation 17): the rows of several models answering the same 200 BFCL cases are stacked, so the
number of strong errors grows (add models, not cases).  Reports AUROC with a cluster bootstrap over test cases, and detection at the 5/10/20%
interruption budgets (marginal conformal and Clopper-Pearson rule, 1,000 re-splits by test case).

  python -I benchmarks/selfconsistency_pool.py benchmarks/selfconsistency_sc120.json benchmarks/selfconsistency_sc30.json benchmarks/selfconsistency_sc4k8.json
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))
from analyze_consensus import auroc  # noqa: E402
from ask_policy import conformal_tau, pac_tau  # noqa: E402


def main():
    files = sys.argv[1:]
    rows = []
    for f in files:
        r = json.loads(Path(f).read_text(encoding="utf-8"))
        for x in r["rows"]:
            rows.append({**x, "model": r["model"]})
    ok = np.array([x["ok"] for x in rows]); tests = np.array([x["test"] for x in rows])
    S = {"self_consistency": np.array([x["sc"] for x in rows]), "peer": np.array([x["peer"] for x in rows]),
         "union_sum": np.array([x["sc"] + x["peer"] for x in rows]), "contract": np.array([x["contract"] for x in rows])}
    res = {"models": [Path(f).stem for f in files], "n_calls": len(rows), "n_strong_wrong": int((~ok).sum()),
           "by_model_wrong": {m: int(sum(1 for x in rows if x["model"] == m and not x["ok"])) for m in sorted({x["model"] for x in rows})}}
    rng = np.random.default_rng(0)
    ut = np.unique(tests)
    idx_of = {t: np.where(tests == t)[0] for t in ut}
    res["auroc"] = {}
    for n, s in S.items():
        pt = auroc(~ok, s)
        bs = []
        for _ in range(500):
            pick = np.concatenate([idx_of[t] for t in rng.choice(ut, len(ut))])
            if (~ok[pick]).any() and ok[pick].any():
                bs.append(auroc(~ok[pick], s[pick]))
        res["auroc"][n] = {"auroc": round(float(pt), 3), "boot95": [round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)]}
    res["by_alpha"] = {}
    for alpha in (0.05, 0.10, 0.20):
        agg = defaultdict(list)
        for _ in range(1000):
            perm = rng.permutation(ut); half = set(perm[: len(ut) // 2].tolist())
            cal = np.array([t in half for t in tests]); te = ~cal
            for n in ("self_consistency", "peer", "union_sum"):
                for rule, fn in (("conformal", conformal_tau), ("pac", pac_tau)):
                    tau = fn(S[n][cal & ok], alpha)
                    ask = S[n] >= tau
                    agg[f"{n}|{rule}|rate"].append(float(ask[te & ok].mean()))
                    agg[f"{n}|{rule}|caught"].append(float(ask[te & ~ok].mean()))
            ask = S["contract"] > 0
            agg["contract|flag|rate"].append(float(ask[te & ok].mean())); agg["contract|flag|caught"].append(float(ask[te & ~ok].mean()))
        row = {}
        for k in sorted({x.rsplit("|", 1)[0] for x in agg}):
            rc, cw = np.array(agg[k + "|rate"]), np.array(agg[k + "|caught"])
            row[k] = {"ask_rate_on_correct": round(float(rc.mean()), 3), "share_within_alpha": round(float((rc <= alpha).mean()), 3),
                      "wrong_caught": round(float(cw.mean()), 3), "p05_p95": [round(float(np.percentile(cw, 5)), 3), round(float(np.percentile(cw, 95)), 3)]}
        res["by_alpha"][str(alpha)] = row
    d = res["by_alpha"]["0.1"]
    res["H_A1"] = {"delta_points_self_vs_contract": round((d["self_consistency|conformal"]["wrong_caught"] - d["contract|flag"]["wrong_caught"]) * 100, 1)}
    out = ROOT / "benchmarks" / "selfconsistency_pooled.json"
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("n_calls", "n_strong_wrong", "by_model_wrong", "auroc", "H_A1")}, indent=1))
    for a, row in res["by_alpha"].items():
        print(a, {k: (v["ask_rate_on_correct"], v["share_within_alpha"], v["wrong_caught"]) for k, v in row.items() if k.endswith(("conformal", "pac", "flag"))})


if __name__ == "__main__":
    main()
