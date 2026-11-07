"""
Ask-policy experiment (dev, exploratory): instead of blocking a suspicious tool call, ASK the user.  Signals per call (BFCL, 30 models,
all 200 single-turn cases, 5,427 usable calls):

  consensus   maximum over the call's arguments of the disagreement with the other 29 models
  contract    1 if any argument violates the tool's own definition (type, enum, documented format, undeclared name)
  combined    contract + consensus (a contract violation ranks above any consensus score)

The policy asks when the score >= tau.  tau is set on a calibration half by a finite-sample split-conformal rule so that
P(ask | correct call) <= alpha:  the smallest score level t with (#correct calibration calls scoring >= t + 1) / (n_correct + 1) <= alpha.
Evaluation repeats 1000 random splits BY TEST CASE (calls of one test case never straddle the halves) and reports, per alpha, the realised
interruption rate on correct calls, the share of wrong calls caught, and in what share of splits the realised rate stays <= alpha.

  PYTHONPATH=. python benchmarks/ask_policy.py [--splits 1000] [--out benchmarks/ask_policy_dev.json]
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
from analyze_consensus import canon, auroc  # noqa: E402
from contract_tier import violations  # noqa: E402


def norm(n):
    return n.replace(".", "_")


def schema_for(call, schemas):
    for s in schemas:
        if s["name"] == call["function"]:
            return s
    for s in schemas:
        if norm(s["name"]) == norm(call["function"]):
            return s
    return None


def contract_flag(rec):
    seen = False
    covered = False
    for call in rec["calls"]:
        sch = schema_for(call, rec["function_schemas"])
        if sch is None:
            continue
        covered = True
        props = sch.get("parameters", {}).get("properties", {})
        for a, v in call["arguments"].items():
            viol = ["unknown_arg"] if a not in props else violations(props[a], v)
            if any(k in viol for k in ("type", "enum", "fmt_city_state", "fmt_date", "fmt_time", "unknown_arg")):
                seen = True
    return seen, covered


def build_rows():
    d = json.loads((ROOT / "benchmarks/data/bfcl/consensus_cases.json").read_text(encoding="utf-8"))
    vals = {s: {m: canon(x["value"]) for m, x in pm.items()} for s, pm in d["consensus_index"].items()}
    rows = []
    for r in d["records"]:
        best = 0.0
        for call in r["calls"]:
            for arg in call["arg_labels"]:
                v = vals.get(f"{r['test_id']}|{call['gold_call_index']}|{arg}")
                if not v or r["model"] not in v or len(v) < 5:
                    continue
                others = [m for m in v if m != r["model"]]
                best = max(best, 1 - sum(v[o] == v[r["model"]] for o in others) / len(others))
        cf, cov = contract_flag(r)
        ok = all(a["label"] == "correct" for c in r["calls"] for a in c["arg_labels"].values())
        rows.append({"test": r["test_id"], "model": r["model"], "ok": ok, "cons": best, "contract": float(cf), "covered": cov})
    return rows


def conformal_tau(cal_scores_correct, alpha):
    s = np.sort(np.asarray(cal_scores_correct))
    n = len(s)
    for t in np.unique(s):
        if ((s >= t).sum() + 1) / (n + 1) <= alpha:
            return float(t)
    return float("inf")


def pac_tau(cal_scores_correct, alpha, delta=0.1):
    """Calibration-conditional rule: smallest level whose one-sided Clopper-Pearson upper bound (confidence 1 - delta) on
    P(ask | correct) is <= alpha, so that the realised rate stays <= alpha with probability >= 1 - delta over calibration draws
    (calls of one test case are correlated, so the effective sample is smaller than n and the bound is optimistic; reported as such)."""
    from scipy.stats import beta
    s = np.sort(np.asarray(cal_scores_correct))
    n = len(s)
    for t in np.unique(s):
        k = int((s >= t).sum())
        ub = 1.0 if k >= n else float(beta.ppf(1 - delta, k + 1, n - k))
        if ub <= alpha:
            return float(t)
    return float("inf")


def cluster_tau(cal_scores_correct, cal_tests_correct, alpha, delta=0.1):
    """Cluster-aware rule: the unit is the TEST CASE.  For a level t let r_j be the share of correct calls of test case j scoring >= t; the
    one-sided Hoeffding bound mean(r_j) + sqrt(ln(1/delta) / (2 m)) over the m calibration test cases must be <= alpha.  Valid when test cases
    are exchangeable draws; conservative, and independent of how many models answered each case."""
    s = np.asarray(cal_scores_correct); tj = np.asarray(cal_tests_correct)
    groups = {t: np.where(tj == t)[0] for t in np.unique(tj)}
    m = len(groups)
    if m == 0:
        return float("inf")
    pad = float(np.sqrt(np.log(1 / delta) / (2 * m)))
    for t in np.unique(s):
        r = np.mean([(s[ix] >= t).mean() for ix in groups.values()])
        if r + pad <= alpha:
            return float(t)
    return float("inf")


def boot_tau(cal_scores_correct, cal_tests_correct, alpha, delta=0.1, n_boot=300, seed=0):
    """Approximate cluster-aware rule: bootstrap the TEST CASES of the calibration half; the (1 - delta) quantile of the resampled mean of the
    per-case ask shares must be <= alpha.  Not a proof (percentile bootstrap, about 100 clusters) but far less conservative than the Hoeffding bound."""
    s = np.asarray(cal_scores_correct); tj = np.asarray(cal_tests_correct)
    groups = [np.where(tj == t)[0] for t in np.unique(tj)]
    m = len(groups)
    if m == 0:
        return float("inf")
    rng = np.random.default_rng(seed)
    levels = np.unique(s)
    R = np.array([[(s[ix] >= t).mean() for ix in groups] for t in levels])      # levels x clusters
    idx = rng.integers(0, m, size=(n_boot, m))
    for li, t in enumerate(levels):
        q = np.quantile(R[li][idx].mean(axis=1), 1 - delta)
        if q <= alpha:
            return float(t)
    return float("inf")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", type=int, default=1000)
    ap.add_argument("--strong", action="store_true", help="drop calls whose only errors are weak labels (format variants, optional arguments left blank by gold)")
    ap.add_argument("--out", default=str(ROOT / "benchmarks" / "ask_policy_dev.json"))
    a = ap.parse_args()
    rows = build_rows()
    if a.strong:
        from decidability import bfcl_call_status
        st = bfcl_call_status()
        rows = [r for r in rows if st.get(r["test"] + "|" + r["model"], "correct") != "weak_only"]
        print("strong mode:", len(rows), "calls kept")
    ok = np.array([r["ok"] for r in rows]); cons = np.array([r["cons"] for r in rows]); con = np.array([r["contract"] for r in rows])
    comb = con + cons
    tests = np.array([r["test"] for r in rows]); ut = np.unique(tests)
    res = {"n_calls": len(rows), "n_wrong": int((~ok).sum()), "wrong_rate": round(float((~ok).mean()), 4),
           "contract_coverage": round(float(np.mean([r["covered"] for r in rows])), 3),
           "contract_flag_rate_correct": round(float(con[ok].mean()), 3), "contract_flag_rate_wrong": round(float(con[~ok].mean()), 3),
           "auroc": {"consensus": round(auroc(~ok, cons), 3), "contract": round(auroc(~ok, con), 3), "combined": round(auroc(~ok, comb), 3)}}
    # reach of the signals: wrong calls with no signal at all (the residue only a user can settle)
    none = (~ok) & (con == 0) & (cons == 0)
    res["wrong_calls_with_no_signal"] = {"n": int(none.sum()), "share": round(float(none.sum() / (~ok).sum()), 3)}
    rng = np.random.default_rng(0)
    out = {}
    for alpha in (0.05, 0.10, 0.20):
        agg = defaultdict(list)
        for _ in range(a.splits):
            perm = rng.permutation(ut); half = set(perm[: len(ut) // 2].tolist())
            cal = np.array([t in half for t in tests]); te = ~cal
            for name, sc in (("consensus", cons), ("combined", comb), ("consensus_pac", cons), ("consensus_cluster", cons), ("consensus_boot", cons)):
                if name.endswith("_boot"):
                    tau = boot_tau(sc[cal & ok], tests[cal & ok], alpha)
                elif name.endswith("_cluster"):
                    tau = cluster_tau(sc[cal & ok], tests[cal & ok], alpha)
                elif name.endswith("_pac"):
                    tau = pac_tau(sc[cal & ok], alpha)
                else:
                    tau = conformal_tau(sc[cal & ok], alpha)
                ask = sc >= tau
                agg[name + "_rate_correct"].append(float(ask[te & ok].mean()))
                agg[name + "_caught_wrong"].append(float(ask[te & ~ok].mean()))
            ask_c = con > 0
            agg["contract_rate_correct"].append(float(ask_c[te & ok].mean()))
            agg["contract_caught_wrong"].append(float(ask_c[te & ~ok].mean()))
        row = {}
        for name in ("consensus", "consensus_pac", "consensus_cluster", "consensus_boot", "combined", "contract"):
            rc, cw = np.array(agg[name + "_rate_correct"]), np.array(agg[name + "_caught_wrong"])
            row[name] = {"ask_rate_on_correct_mean": round(float(rc.mean()), 3), "ask_rate_p05_p95": [round(float(np.percentile(rc, 5)), 3), round(float(np.percentile(rc, 95)), 3)],
                         "share_of_splits_within_alpha": round(float((rc <= alpha).mean()), 3), "wrong_caught_mean": round(float(cw.mean()), 3),
                         "wrong_caught_p05_p95": [round(float(np.percentile(cw, 5)), 3), round(float(np.percentile(cw, 95)), 3)]}
        out[str(alpha)] = row
    res["by_alpha"] = out
    Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
