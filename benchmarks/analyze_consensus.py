"""
Cross-model consensus as a verifier of tool-call arguments (exploratory; public BFCL outputs, 30 models, one identical prompt).

For every argument slot (test case, gold-call index, argument) and every model, the score is the DISAGREEMENT of that model's value with
the values of the OTHER models: 1 - (share of the other models that gave the same value).  A wrong argument should have higher
disagreement.  Labels are BFCL gold labels from benchmarks/data/bfcl/consensus_cases.json (built by load_bfcl_consensus.py).

Reported (all by argument instance; CIs by cluster bootstrap over test cases):
  * AUROC of disagreement, overall and split into
      lone errors       wrong, and fewer than half of the other models are also wrong at this slot
      systematic errors wrong, and at least half of the other models are wrong too (gold/label artefacts and genuinely hard slots)
  * detection (TPR) at false-block rates of 1%, 5%, 10% on correct arguments
  * plurality-vote baseline: block when the value differs from the most common value
  * error correlation: mean pairwise phi between models, within and across families
Nothing here is tuned; there is no train/test split because nothing is fitted (the score has no parameters).

  python benchmarks/analyze_consensus.py [--data benchmarks/data/bfcl/consensus_cases.json] [--out benchmarks/consensus_results.json]
"""
import argparse
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def canon(v):
    if isinstance(v, bool):
        return ("b", v)
    if isinstance(v, (int, float)):
        return ("n", round(float(v), 9))
    if isinstance(v, str):
        s = " ".join(v.strip().lower().split())
        try:
            return ("n", round(float(s), 9))
        except ValueError:
            return ("s", s)
    if isinstance(v, (list, tuple)):
        return ("l", tuple(canon(x) for x in v))
    if isinstance(v, dict):
        return ("d", tuple(sorted((str(k), canon(x)) for k, x in v.items())))
    return ("o", str(v))


def auroc(y, s):
    y = np.asarray(y, bool); s = np.asarray(s, float)
    pos, neg = s[y], s[~y]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    return float(((pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()) / (len(pos) * len(neg)))


def tpr_at_fbr(wrong, score, fbr):
    """Largest detection with false-block rate <= fbr: block when score >= t (ties handled by the threshold set)."""
    w = np.asarray(wrong, bool); s = np.asarray(score, float)
    best = (0.0, 0.0)
    for t in sorted(set(s.tolist())):
        blocked = s >= t
        f = blocked[~w].mean() if (~w).any() else 0.0
        if f <= fbr:
            d = blocked[w].mean() if w.any() else 0.0
            if d > best[0]:
                best = (float(d), float(f))
    return best


def family(m):
    m = m.lower()
    for k in ("claude", "gpt", "o3", "o4", "gemini", "deepseek", "qwen", "kimi"):
        if m.startswith(k):
            return {"o3": "gpt", "o4": "gpt"}.get(k, k)
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "benchmarks/data/bfcl/consensus_cases.json"))
    ap.add_argument("--out", default=str(ROOT / "benchmarks/consensus_results.json"))
    ap.add_argument("--boot", type=int, default=1000)
    a = ap.parse_args()
    d = json.loads(Path(a.data).read_text(encoding="utf-8"))
    idx = d["consensus_index"]
    inst = []                                   # one row per (slot, model)
    for slot, per_model in idx.items():
        test = slot.split("|")[0]
        vals = {m: canon(x["value"]) for m, x in per_model.items()}
        wrong = {m: x["label"] != "correct" for m, x in per_model.items()}
        n = len(per_model)
        if n < 5:
            continue
        plurality = Counter(vals.values()).most_common(1)[0][0]
        for m in per_model:
            others = [o for o in per_model if o != m]
            agree = sum(vals[o] == vals[m] for o in others) / len(others)
            other_wrong = sum(wrong[o] for o in others) / len(others)
            inst.append({"slot": slot, "test": test, "model": m, "wrong": wrong[m], "dis": 1 - agree, "other_wrong": other_wrong,
                         "plur_block": vals[m] != plurality})
    wrong = np.array([r["wrong"] for r in inst]); dis = np.array([r["dis"] for r in inst])
    ow = np.array([r["other_wrong"] for r in inst]); tests = np.array([r["test"] for r in inst])
    lone = wrong & (ow < 0.5); syst = wrong & (ow >= 0.5)
    res = {"n_instances": int(len(inst)), "n_slots": len(idx), "n_wrong": int(wrong.sum()), "n_lone": int(lone.sum()), "n_systematic": int(syst.sum()),
           "wrong_rate": round(float(wrong.mean()), 4)}

    def sub_auroc(mask_wrong):
        keep = (~wrong) | mask_wrong
        return auroc(mask_wrong[keep], dis[keep])
    res["auroc_all_wrong"] = round(auroc(wrong, dis), 3)
    res["auroc_lone"] = round(sub_auroc(lone), 3)
    res["auroc_systematic"] = round(sub_auroc(syst), 3)
    rng = np.random.default_rng(0)
    ut = np.unique(tests)
    boots = {"all": [], "lone": []}
    for _ in range(a.boot):
        pick = rng.choice(ut, len(ut))
        m = np.concatenate([np.where(tests == t)[0] for t in pick])
        w, s, l = wrong[m], dis[m], lone[m]
        if w.any() and (~w).any():
            boots["all"].append(auroc(w, s))
        keep = (~w) | l
        if l.any() and (~w).any():
            boots["lone"].append(auroc(l[keep], s[keep]))
    for k, v in boots.items():
        res[f"auroc_{k}_ci95"] = [round(float(np.percentile(v, 2.5)), 3), round(float(np.percentile(v, 97.5)), 3)] if v else None
    res["tpr_at_fbr"] = {}
    for f in (0.01, 0.05, 0.10):
        keep = (~wrong) | lone
        d_lone, f_lone = tpr_at_fbr(lone[keep], dis[keep], f)
        d_all, f_all = tpr_at_fbr(wrong, dis, f)
        res["tpr_at_fbr"][str(f)] = {"lone_errors_only": [round(d_lone, 3), round(f_lone, 3)], "all_wrong": [round(d_all, 3), round(f_all, 3)]}
    pb = np.array([r["plur_block"] for r in inst])
    res["plurality_vote"] = {"fbr": round(float(pb[~wrong].mean()), 3), "tpr_all_wrong": round(float(pb[wrong].mean()), 3),
                             "tpr_lone": round(float(pb[lone].mean()), 3) if lone.any() else None,
                             "tpr_systematic": round(float(pb[syst].mean()), 3) if syst.any() else None}
    # error correlation between models over the slots both answered
    models = sorted({r["model"] for r in inst})
    mat = defaultdict(dict)
    for r in inst:
        mat[r["model"]][r["slot"]] = int(r["wrong"])
    phis_within, phis_cross = [], []
    for m1, m2 in itertools.combinations(models, 2):
        common = sorted(set(mat[m1]) & set(mat[m2]))
        x = np.array([mat[m1][s] for s in common], float); y = np.array([mat[m2][s] for s in common], float)
        if x.std() == 0 or y.std() == 0:
            continue
        phi = float(np.corrcoef(x, y)[0, 1])
        (phis_within if family(m1) == family(m2) else phis_cross).append(phi)
    res["error_phi_mean"] = {"within_family": round(float(np.mean(phis_within)), 3) if phis_within else None, "n_within": len(phis_within),
                             "cross_family": round(float(np.mean(phis_cross)), 3) if phis_cross else None, "n_cross": len(phis_cross)}
    per_model = {}
    for m in models:
        r = [x for x in inst if x["model"] == m]
        per_model[m] = {"wrong_rate": round(float(np.mean([x["wrong"] for x in r])), 4)}
    res["per_model_wrong_rate"] = per_model
    Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    skip = {"per_model_wrong_rate"}
    print(json.dumps({k: v for k, v in res.items() if k not in skip}, indent=1))


if __name__ == "__main__":
    main()
