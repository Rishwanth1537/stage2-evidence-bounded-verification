"""
Cascade analysis on a DEV half (exploratory): the deterministic checker decides first, a judge is asked only about calls the checker
does not clear.  Stage 1 allows a call when its call score >= tau; every other call is escalated to the judge.

For each judge result file and each tau the table gives
  esc_all     share of calls sent to the judge in this dataset (error prevalence of the dataset)
  esc@5%      share sent to the judge if only 5% of real calls were wrong (re-weights wrong vs correct calls)
  FBR / det   cascade false-block rate and detection (calls the checker clears are allowed)
  d_det       detection lost relative to asking the judge about everything
  random_det  detection if the SAME share of calls were chosen at random for the judge (the routing has to beat this to be worth anything)
  leak        wrong calls the checker clears that the judge would have blocked
and the smallest escalation share whose detection stays within `--margin` of the judge alone.
Test halves are never read here.

  PYTHONPATH=. python benchmarks/analyze_cascade.py --dataset fcrb --judge benchmarks/llm_judge_args_fcrb_agent_opus_dev_v0.json [--judge ...]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))
from analyze_study import blocked_from_row  # noqa: E402

BENCH = {"fcrb": "benchmarks/data/deref/cases_fcrb.json", "cfb": "benchmarks/data/deref/cases_cfb.json", "injected": "benchmarks/argground_bench.json"}
GRID = [1.0, 0.95, 0.88, 0.7, 0.5, 0.3, 0.0]


def case_scores(dataset, ids):
    path = ROOT / BENCH[dataset]
    cases = {c["id"]: c for c in json.loads(path.read_text(encoding="utf-8"))["cases"]}
    out = {}
    for i in ids:
        c = cases[i]
        if "split" in c and c["split"] != "dev":
            sys.exit("test-half case requested; this script only reads dev")
        if dataset == "injected":
            from server.pipeline.arg_ground import call_score
            out[i] = call_score(c["call"]["arguments"], c["premise"])
        else:
            from eval_deref import score_case
            out[i] = score_case(c)[0]
    return out


def table(rows, scores, prevalence=0.05, margin=0.02):
    y = np.array([r["label"] for r in rows], bool)              # True = correct (genuine) call
    jb = np.array([blocked_from_row(r) for r in rows], bool)
    s = np.array([scores[r["id"]] for r in rows])
    J_fbr, J_det = jb[y].mean(), jb[~y].mean()
    out = []
    for tau in GRID:
        esc = s < tau if tau > 0 else np.ones(len(s), bool)     # tau 0 = checker clears nothing (judge-only)
        if tau == 1.0:
            esc = s < 1.0
        cb = esc & jb
        e_g, e_w = esc[y].mean(), esc[~y].mean()
        out.append({"tau": tau, "esc_all": round(float(esc.mean()), 3),
                    "esc_at_5pct_wrong": round(float(prevalence * e_w + (1 - prevalence) * e_g), 3),
                    "fbr": round(float(cb[y].mean()), 3), "det": round(float(cb[~y].mean()), 3),
                    "d_det": round(float(cb[~y].mean() - J_det), 3),
                    "random_det": round(float(esc.mean() * J_det), 3),
                    "leak": int(((~y) & ~esc & jb).sum())})
    ok = [r for r in out if r["d_det"] >= -margin]
    best = min(ok, key=lambda r: r["esc_all"]) if ok else None
    return {"n": int(len(y)), "judge_fbr": round(float(J_fbr), 3), "judge_det": round(float(J_det), 3), "grid": out,
            "smallest_escalation_within_margin": best}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, choices=list(BENCH))
    ap.add_argument("--judge", action="append", required=True)
    ap.add_argument("--margin", type=float, default=0.02)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    results = {}
    for jf in a.judge:
        d = json.loads(Path(jf).read_text(encoding="utf-8"))
        if d.get("split") == "test":
            sys.exit("test-half judge file; this script only reads dev")
        rows = d["rows"]
        sc = case_scores(a.dataset, [r["id"] for r in rows])
        t = table(rows, sc, margin=a.margin)
        results[Path(jf).name] = t
        print(f"\n{Path(jf).name}  n={t['n']}  judge alone: FBR {t['judge_fbr']}  det {t['judge_det']}")
        print("  tau   esc_all esc@5%  FBR    det    d_det  random_det leak")
        for r in t["grid"]:
            print(f"  {r['tau']:<5} {r['esc_all']:<7} {r['esc_at_5pct_wrong']:<7} {r['fbr']:<6} {r['det']:<6} {r['d_det']:<6} {r['random_det']:<10} {r['leak']}")
        b = t["smallest_escalation_within_margin"]
        print("  smallest escalation within margin:", b if b else "none")
    if a.out:
        Path(a.out).write_text(json.dumps(results, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
