"""
Confirmatory analysis of the AgentHallu BFCL slice (registered in review/PREREGISTRATION.md, Deviation 14).

Systems: the deterministic context checker (call_is_grounded on all arguments) and the judges listed in JUDGES (each run once with the frozen prompt).
For every system: false-block rate on the 93 clean calls and detection of the 31 human-attributed errors with Wilson 95% intervals, unparseable
replies (counted as misses), Youden's J.  H-J1 (primary): detection above the checker's at a false-block rate not above the checker's, exact McNemar on
per-case correctness against the checker, Holm correction over the judges present.  H-J2: detection below 70%.

  PYTHONPATH=. python benchmarks/analyze_agenthallu.py
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))
from analyze_study import blocked_from_row  # noqa: E402
from llm_judge_args import mcnemar_exact  # noqa: E402
from server.pipeline.arg_ground import call_is_grounded  # noqa: E402

B = ROOT / "benchmarks"
JUDGES = [
    ("Claude Opus (agent)", "llm_judge_args_ah_agent_opus_dev_v0.json"),
    ("Claude Sonnet (agent)", "llm_judge_args_ah_agent_sonnet_dev_v0.json"),
    ("Claude Haiku (agent)", "llm_judge_args_ah_agent_haiku_dev_v0.json"),
    ("Nemotron 550B (API t=0)", "llm_judge_args_ah_nvidia_nemotron_3_ultra_550b_a55b_dev_v0.json"),
    ("Nemotron 4B (API t=0)", "llm_judge_args_ah_nvidia_nemotron_3_5_bolt_e4b_dev_v0.json"),
]


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (c - h, c + h)


def main():
    cases = {c["id"]: c for c in json.loads((B / "data/agenthallu/cases_eval.json").read_text(encoding="utf-8"))["cases"]}
    ids = sorted(cases)
    ok = np.array([bool(cases[i]["label"]) for i in ids])
    chk = np.array([not call_is_grounded(cases[i]["call"]["arguments"], cases[i]["premise"]) for i in ids])
    systems = {"context checker": (chk, 0)}
    for name, f in JUDGES:
        p = B / f
        if not p.exists():
            print(f"{name}: no result file yet")
            continue
        rows = {r["id"]: r for r in json.loads(p.read_text(encoding="utf-8"))["rows"]}
        if any(i not in rows for i in ids):
            print(f"{name}: incomplete ({len(rows)} rows)")
            continue
        systems[name] = (np.array([blocked_from_row(rows[i]) for i in ids]), sum(not rows[i]["parsed"] for i in ids))
    n_pos, n_neg = int((~ok).sum()), int(ok.sum())
    out = {}
    print("%-26s %-22s %-22s %6s %6s | vs checker: only-judge/only-checker  p" % ("system", "false blocks (95% CI)", "detection (95% CI)", "J", "unpars"))
    pvals = {}
    for name, (b, unp) in systems.items():
        fb, dt = int(b[ok].sum()), int(b[~ok].sum())
        lf, hf = wilson(fb, n_neg); ld, hd = wilson(dt, n_pos)
        row = {"fbr": fb / n_neg, "det": dt / n_pos, "fbr_ci": [lf, hf], "det_ci": [ld, hd], "J": dt / n_pos - fb / n_neg, "unparseable": unp}
        if name != "context checker":
            mc = mcnemar_exact([(not x) == o for x, o in zip(b, ok)], [(not x) == o for x, o in zip(chk, ok)])
            row["mcnemar"] = mc
            pvals[name] = mc["p"]
        out[name] = row
    # Holm over judges
    order = sorted(pvals, key=pvals.get)
    m = len(order)
    prev = 0.0
    for rank, name in enumerate(order):
        adj = min(1.0, max(prev, (m - rank) * pvals[name]))
        out[name]["holm_p"] = adj
        prev = adj
    for name, row in out.items():
        mc = row.get("mcnemar")
        extra = "" if mc is None else "%d/%d  p=%.4f Holm=%.4f" % (mc["only_a_correct"], mc["only_b_correct"], mc["p"], row["holm_p"])
        print("%-26s %5.1f%% [%4.1f,%4.1f]    %5.1f%% [%4.1f,%4.1f]    %+5.1f %5d | %s" % (
            name, 100 * row["fbr"], 100 * row["fbr_ci"][0], 100 * row["fbr_ci"][1], 100 * row["det"], 100 * row["det_ci"][0], 100 * row["det_ci"][1],
            100 * row["J"], row["unparseable"], extra))
    base = out["context checker"]
    print()
    for name, row in out.items():
        if name == "context checker":
            continue
        hj1 = row["det"] > base["det"] and row["fbr"] <= base["fbr"] and row["holm_p"] < 0.05
        print("H-J1 %-26s %s (det %.1f vs %.1f, FBR %.1f vs %.1f, Holm p %.4f)   H-J2 det<70%%: %s" % (
            name, "SUPPORTED" if hj1 else "not supported", 100 * row["det"], 100 * base["det"], 100 * row["fbr"], 100 * base["fbr"], row["holm_p"],
            "yes" if row["det"] < 0.70 else "no"))
    (B / "agenthallu_confirmatory.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
