"""
Analyses for the judge study (pre-registration hypotheses H1, H1c, H2, H7) on DeRef cases plus llm_judge_args.py outputs.

  python benchmarks/analyze_study.py --self-test
  python benchmarks/analyze_study.py h1      --cases benchmarks/data/deref/cases_fcrb.json --judge-dev DEV.json --judge-test TEST.json
  python benchmarks/analyze_study.py paths   --cases benchmarks/data/deref/cases_fcrb.json --judge TEST.json [--judge OTHER.json ...]
  python benchmarks/analyze_study.py cascade --cases benchmarks/data/deref/cases_fcrb.json --judge TEST.json

h1       Matched false-block comparison of S2 (deterministic) with ONE judge's operating point. alpha = the judge's false-block rate on its
         dev sample; S2's threshold = split-conformal threshold at that alpha from ALL dev genuine calls; both evaluated on the judge's test
         sample.  Delta = detection(S2) - detection(judge).  Cluster bootstrap over query_id, re-estimating alpha and tau inside every
         resample.  Non-inferiority: the 5th percentile of Delta must exceed -margin (default 0.02).
paths    Per derivation path x label: share of arguments flagged by S1, S2 and each judge (judge flags an argument if its name is in
         "unsupported_arguments"; unparseable replies are skipped).
cascade  Offline cascade S2 -> judge: calls whose in-analysis arguments are all grounded (call score >= tau) are ALLOWED by stage 1,
         the rest are escalated to the judge verdict.  Reports escalation share per class, cascade false-block/detection vs judge-only,
         and LEAKAGE = wrong calls that stage 1 allowed although the judge would have blocked them.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))

from server.pipeline.arg_ground import conformal_threshold  # noqa: E402


def blocked_from_row(r):
    """Judge verdict -> blocked.  Unparseable counts as a miss: genuine -> blocked (false block), wrong -> allowed."""
    return (not r["supported"]) if r["parsed"] else bool(r["label"])


def _rate(mask, sel):
    return float(mask[sel].mean()) if sel.any() else float("nan")


def matched_delta(dev_gen_scores, jdev_label, jdev_blocked, jt_label, jt_blocked, jt_scores):
    alpha = _rate(jdev_blocked, jdev_label)                      # judge FBR on its dev sample
    tau = conformal_threshold(list(dev_gen_scores), alpha)
    s2_blocked = jt_scores < tau
    return {"delta": _rate(s2_blocked, ~jt_label) - _rate(jt_blocked, ~jt_label), "alpha": alpha, "tau": float(tau),
            "s2_fbr": _rate(s2_blocked, jt_label), "judge_fbr": _rate(jt_blocked, jt_label),
            "s2_det": _rate(s2_blocked, ~jt_label), "judge_det": _rate(jt_blocked, ~jt_label)}


def cluster_bootstrap_delta(dev_gen, jdev, jt, n_boot=2000, seed=0, margin=0.02):
    """dev_gen: dict(query_id array, score array); jdev / jt: dict(query_id, label, blocked[, score])."""
    rng = np.random.default_rng(seed)
    point = matched_delta(dev_gen["score"], jdev["label"], jdev["blocked"], jt["label"], jt["blocked"], jt["score"])

    def groups(d):
        idx = defaultdict(list)
        for i, q in enumerate(d["query_id"]):
            idx[q].append(i)
        return idx
    gg, gd, gt = groups(dev_gen), groups(jdev), groups(jt)
    kg, kd, kt = list(gg), list(gd), list(gt)
    deltas = []
    for _ in range(n_boot):
        ig = np.concatenate([gg[kg[i]] for i in rng.integers(0, len(kg), len(kg))]).astype(int)
        idd = np.concatenate([gd[kd[i]] for i in rng.integers(0, len(kd), len(kd))]).astype(int)
        it = np.concatenate([gt[kt[i]] for i in rng.integers(0, len(kt), len(kt))]).astype(int)
        if not jt["label"][it].any() or jt["label"][it].all() or not jdev["label"][idd].any():
            continue
        deltas.append(matched_delta(dev_gen["score"][ig], jdev["label"][idd], jdev["blocked"][idd], jt["label"][it], jt["blocked"][it], jt["score"][it])["delta"])
    d = np.array([x for x in deltas if not np.isnan(x)])
    lo, hi = np.percentile(d, [5, 95])
    return {"point": point, "delta_ci90": [float(lo), float(hi)], "n_boot": int(len(d)),
            "non_inferior": bool(lo > -margin), "margin": margin}


def load_cases(path, splits=("dev", "test")):
    """Score only the requested splits (cfb contexts are long; scoring is slow, and unneeded splits must not be touched)."""
    from eval_deref import score_case
    data = json.loads(Path(path).read_text())
    out = {}
    for c in data["cases"]:
        if c["split"] not in splits:
            continue
        s, eb, per = score_case(c)
        out[c["id"]] = {"case": c, "score": s, "per_arg": per}
    return out


def arr(rows, cases, with_score=True):
    d = {"query_id": np.array([cases[r["id"]]["case"]["query_id"] for r in rows]),
         "label": np.array([r["label"] for r in rows], bool), "blocked": np.array([blocked_from_row(r) for r in rows], bool)}
    if with_score:
        d["score"] = np.array([cases[r["id"]]["score"] for r in rows])
    return d


LEDGER = ROOT / "benchmarks" / "test_run_ledger.jsonl"


def guard_test(a, what):
    """Reading test-half data needs --allow-test and leaves a ledger line (pre-registration)."""
    import datetime
    if not getattr(a, "allow_test", False):
        sys.exit(f"{what} reads the TEST half: re-run with --allow-test (it is logged in {LEDGER.name})")
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"when": datetime.datetime.now().isoformat(timespec="seconds"), "script": "analyze_study.py " + what,
                            "cases": Path(a.cases).name, "note": getattr(a, "note", "")}) + "\n")


def cmd_h1(a):
    guard_test(a, "h1")
    cases = load_cases(a.cases)
    jdev = json.loads(Path(a.judge_dev).read_text())["rows"]
    jt = json.loads(Path(a.judge_test).read_text())["rows"]
    gen = [(v["case"]["query_id"], v["score"]) for v in cases.values() if v["case"]["split"] == "dev" and v["case"]["label"]]
    dev_gen = {"query_id": np.array([g[0] for g in gen]), "score": np.array([g[1] for g in gen])}
    res = cluster_bootstrap_delta(dev_gen, arr(jdev, cases, False), arr(jt, cases), n_boot=a.n_boot, margin=a.margin)
    print(json.dumps(res, indent=2))
    Path(a.out).write_text(json.dumps(res, indent=2)) if a.out else None


def cmd_paths(a):
    if a.split == "test":
        guard_test(a, "paths")
    cases = load_cases(a.cases, (a.split,))
    table = defaultdict(lambda: defaultdict(lambda: [0, 0]))     # (path,label) -> system -> [flagged, n]
    judges = {}
    for jf in a.judge:
        jd = json.loads(Path(jf).read_text())
        judges[f"{jd.get('provider', '?')}/{jd.get('model', '?')}"] = {r["id"]: r for r in jd["rows"]}
    ids = (set.intersection(*[set(j) for j in judges.values()]) & set(cases)) if judges else set(cases)
    for cid in ids:
        for arg in cases[cid]["per_arg"]:
            key = (arg["path"], arg["label"])
            for sysname, flagged in (("S1 exact", arg["s1_ungrounded"]), ("S2 type-aware", arg["s2_ungrounded"])):
                table[key][sysname][0] += int(flagged); table[key][sysname][1] += 1
            for jn, rows in judges.items():
                r = rows[cid]
                if r["parsed"]:
                    table[key][jn][0] += int(arg["name"] in (r["unsupported_arguments"] or [])); table[key][jn][1] += 1
    systems = ["S1 exact", "S2 type-aware"] + list(judges)
    print("share of arguments flagged, by derivation path and label")
    print(f"{'path|label':24s}" + "".join(f"{s[:22]:>24s}" for s in systems))
    out = {}
    for key in sorted(table):
        row = {s: (table[key][s][0] / table[key][s][1] if table[key][s][1] else None) for s in systems}
        out["|".join(key)] = {"n": table[key]["S2 type-aware"][1], **row}
        print(f"{'|'.join(key):24s}" + "".join(f"{(row[s] if row[s] is not None else float('nan')):24.3f}" for s in systems) + f"   n={table[key]['S2 type-aware'][1]}")
    Path(a.out).write_text(json.dumps(out, indent=2)) if a.out else None


def cmd_cascade(a):
    cases = load_cases(a.cases)
    first = json.loads(Path(a.judge).read_text()).get("split")
    if first == "test":
        guard_test(a, "cascade")
    rows = json.loads(Path(a.judge).read_text())["rows"]
    d = arr(rows, cases)
    stage1_allow = d["score"] >= a.tau
    esc = ~stage1_allow
    cascade_blocked = np.where(esc, d["blocked"], False)
    y = d["label"]
    out = {"n": int(len(y)), "tau": a.tau,
           "escalation_share_genuine": _rate(esc, y), "escalation_share_wrong": _rate(esc, ~y),
           "judge_only": {"false_block": _rate(d["blocked"], y), "detection": _rate(d["blocked"], ~y)},
           "cascade": {"false_block": _rate(cascade_blocked, y), "detection": _rate(cascade_blocked, ~y)},
           "leakage_wrong_allowed_by_stage1_but_judge_would_block": int(((~y) & stage1_allow & d["blocked"]).sum()),
           "wrong_total": int((~y).sum())}
    print(json.dumps(out, indent=2))
    Path(a.out).write_text(json.dumps(out, indent=2)) if a.out else None


def self_test():
    rng = np.random.default_rng(1)
    n = 600
    q = np.repeat(np.arange(n // 2), 2)
    label = rng.random(n) < 0.5
    s2 = np.where(label, np.clip(rng.normal(0.9, 0.2, n), 0, 1), np.clip(rng.normal(0.5, 0.3, n), 0, 1))
    jb = np.where(label, rng.random(n) < 0.1, rng.random(n) < 0.8)            # judge: 10% false block, 80% detection
    dev_gen = {"query_id": q[label], "score": s2[label]}
    jd = {"query_id": q, "label": label, "blocked": jb}
    jt = {"query_id": q, "label": label, "blocked": jb, "score": s2}
    res = cluster_bootstrap_delta(dev_gen, jd, jt, n_boot=200, seed=2)
    assert res["n_boot"] > 150 and res["delta_ci90"][0] <= res["point"]["delta"] <= res["delta_ci90"][1] + 1e-9
    assert abs(res["point"]["s2_fbr"] - res["point"]["alpha"]) < 0.08           # matched false-block rates
    assert blocked_from_row({"parsed": False, "label": True}) is True and blocked_from_row({"parsed": False, "label": False}) is False
    print("self-test passed; synthetic delta", round(res["point"]["delta"], 3), res["delta_ci90"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    for name in ("h1", "paths", "cascade"):
        p = sub.add_parser(name)
        p.add_argument("--cases", required=True)
        p.add_argument("--out", default=None)
        p.add_argument("--allow-test", action="store_true"); p.add_argument("--note", default="")
        if name == "h1":
            p.add_argument("--judge-dev", required=True); p.add_argument("--judge-test", required=True)
            p.add_argument("--n-boot", type=int, default=2000); p.add_argument("--margin", type=float, default=0.02)
        elif name == "paths":
            p.add_argument("--judge", action="append", default=[]); p.add_argument("--split", choices=["dev", "test"], default="dev")
        else:
            p.add_argument("--judge", required=True); p.add_argument("--tau", type=float, default=0.88)
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    {"h1": cmd_h1, "paths": cmd_paths, "cascade": cmd_cascade}[a.cmd](a)


if __name__ == "__main__":
    main()
