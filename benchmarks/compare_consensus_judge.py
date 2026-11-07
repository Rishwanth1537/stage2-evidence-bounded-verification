"""
Control experiment for the cross-model consensus verifier: a frozen judge versus consensus on the SAME BFCL calls, at matched false-block rate.

Inputs: a judge result file made by llm_judge_args.py on benchmarks/data/bfcl/cases_bfcl_consensus.json (dev), and the consensus data.
Consensus call score = maximum over the call's arguments of the disagreement with the other models (all 29 other models, including the
nine other models of the 10 judged here); a call is blocked when the score >= threshold.  The threshold is set so that consensus has the same
false-block rate as the judge (largest threshold not exceeding it), then detection is compared; also AUROC of consensus and the union
judge OR consensus at the judge's rate.  Cluster bootstrap over test cases.  Exploratory, dev only.

  PYTHONPATH=. python benchmarks/compare_consensus_judge.py --judge benchmarks/llm_judge_args_bfcl_custom_agent_sonnet_dev_v0.json
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
from analyze_consensus import canon, auroc  # noqa: E402
from analyze_study import blocked_from_row  # noqa: E402


def call_scores():
    d = json.loads((ROOT / "benchmarks/data/bfcl/consensus_cases.json").read_text(encoding="utf-8"))
    idx = d["consensus_index"]
    vals = {s: {m: canon(x["value"]) for m, x in pm.items()} for s, pm in idx.items()}
    out = {}
    for r in d["records"]:
        best = 0.0
        for call in r["calls"]:
            for arg in call["arg_labels"]:
                slot = f"{r['test_id']}|{call['gold_call_index']}|{arg}"
                v = vals.get(slot)
                if not v or r["model"] not in v or len(v) < 5:
                    continue
                others = [m for m in v if m != r["model"]]
                best = max(best, 1 - sum(v[o] == v[r["model"]] for o in others) / len(others))
        out[f"{r['test_id']}|{r['model']}"] = best
    return out


def match_threshold(score, ok, target_fbr):
    best_t, best_f = None, -1
    for t in sorted(set(score.tolist())):
        b = score >= t
        f = float(b[ok].mean())
        if f <= target_fbr and f > best_f:
            best_t, best_f = t, f
    return best_t, best_f


def metrics(rows, cs, seed=None, tests=None):
    ok = np.array([bool(r["label"]) for r in rows]); jb = np.array([blocked_from_row(r) for r in rows])
    sc = np.array([cs[r["id"]] for r in rows])
    jf, jd = float(jb[ok].mean()), float(jb[~ok].mean())
    t, f = match_threshold(sc, ok, jf)
    cb = sc >= t if t is not None else np.zeros(len(sc), bool)
    u = jb | cb
    return {"n": len(rows), "n_wrong": int((~ok).sum()), "judge_fbr": round(jf, 3), "judge_det": round(jd, 3),
            "consensus_fbr": round(float(cb[ok].mean()), 3), "consensus_det": round(float(cb[~ok].mean()), 3),
            "consensus_auroc": round(auroc(~ok, sc), 3), "union_fbr": round(float(u[ok].mean()), 3), "union_det": round(float(u[~ok].mean()), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", required=True)
    ap.add_argument("--boot", type=int, default=500)
    ap.add_argument("--strong", action="store_true", help="drop calls whose only errors are weak labels")
    a = ap.parse_args()
    rows = json.loads(Path(a.judge).read_text(encoding="utf-8"))["rows"]
    if a.strong:
        from decidability import bfcl_call_status
        st = bfcl_call_status()
        keep = [r for r in rows if st.get(r["id"], "correct") != "weak_only"]
        print("strong mode:", len(keep), "of", len(rows), "judged calls kept")
        # the judge file holds the benchmark's call label; recompute labels from the strong status
        for r in keep:
            r["label"] = st.get(r["id"], "correct") == "correct"
        rows = keep
    if json.loads(Path(a.judge).read_text(encoding="utf-8")).get("split") == "test":
        sys.exit("dev only")
    cs = call_scores()
    res = metrics(rows, cs)
    tests = np.array([r["id"].split("|")[0] for r in rows]); ut = np.unique(tests)
    rng = np.random.default_rng(0); diffs = []
    for _ in range(a.boot):
        pick = rng.choice(ut, len(ut))
        sel = [rows[i] for t in pick for i in np.where(tests == t)[0]]
        if not any(not r["label"] for r in sel) or all(not r["label"] for r in sel):
            continue
        m = metrics(sel, cs)
        diffs.append(m["consensus_det"] - m["judge_det"])
    res["det_diff_consensus_minus_judge_ci95"] = [round(float(np.percentile(diffs, 2.5)), 3), round(float(np.percentile(diffs, 97.5)), 3)]
    print(json.dumps(res, indent=1))
    out = Path(a.judge).with_name(Path(a.judge).stem + "_vs_consensus.json")
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
