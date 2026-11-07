"""
Information-versus-size table (dev): for every judge that has results WITH and WITHOUT the tool definition on the seeded 200-case fcrb dev
sample, restricted to the calls that carry a definition, report false blocks and detection in both conditions, the gain, and the exact
McNemar test (with vs without).  Also prints the spread of detection across model sizes inside each condition, per family.

  PYTHONPATH=. python benchmarks/analyze_ladder.py
Files are found by name; judges missing a condition are listed as incomplete.  Temperature-0 API judges (Groq, NVIDIA) and batched agent-mode
Claude judges are labelled separately.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))
from analyze_study import blocked_from_row  # noqa: E402
from contract_complement import contract_flag  # noqa: E402
from contract_tier import load_schemas  # noqa: E402
from llm_judge_args import mcnemar_exact  # noqa: E402

B = ROOT / "benchmarks"
JUDGES = [
    # family, label, size (billions, active or total as published), mode, plain file, schema file
    ("Claude", "Haiku", None, "agent", "llm_judge_args_fcrb_agent_haiku_dev_v0.json", "llm_judge_args_fcrb_schema_agent_haiku_schema_dev_v0.json"),
    ("Claude", "Sonnet", None, "agent", "llm_judge_args_fcrb_agent_sonnet_dev_v0.json", "llm_judge_args_fcrb_schema_agent_sonnet_schema_dev_v0.json"),
    ("Claude", "Opus", None, "agent", "llm_judge_args_fcrb_agent_opus_dev_v0.json", "llm_judge_args_fcrb_schema_agent_opus_schema_dev_v0.json"),
    ("Nemotron", "bolt-e4b (4B)", 4, "api t=0", "llm_judge_args_fcrb_nvidia_nvidia_nemotron_3_5_bolt_e4b_dev_v0.json", "llm_judge_args_fcrbschema_nvidia_nvidia_nemotron_3_5_bolt_e4b_dev_v0.json"),
    ("Nemotron", "lightning (30B-A3B)", 30, "api t=0", "llm_judge_args_fcrb_nvidia_nvidia_nemotron_3_5_lightning_30b_a3b_dev_v0.json", "llm_judge_args_fcrbschema_nvidia_nvidia_nemotron_3_5_lightning_30b_a3b_dev_v0.json"),
    ("Nemotron", "super-vl (120B-A12B)", 120, "api t=0", "llm_judge_args_fcrb_nvidia_nvidia_nemotron_3_5_super_vl_120b_a12b_dev_v0.json", "llm_judge_args_fcrbschema_nvidia_nvidia_nemotron_3_5_super_vl_120b_a12b_dev_v0.json"),
    ("Nemotron", "ultra (550B-A55B)", 550, "api t=0", "llm_judge_args_fcrb_nvidia_nvidia_nemotron_3_ultra_550b_a55b_dev_v0.json", "llm_judge_args_fcrbschema_nvidia_nvidia_nemotron_3_ultra_550b_a55b_dev_v0.json"),
]


def rows(name):
    p = B / name
    if not p.exists():
        return None
    return {r["id"]: r for r in json.loads(p.read_text(encoding="utf-8"))["rows"]}


def main():
    schemas = load_schemas()
    cases = {c["id"]: c for c in json.loads((B / "data/deref/cases_fcrb.json").read_text(encoding="utf-8"))["cases"]}
    out, by_family = [], {}
    print("%-9s %-22s %-8s %5s | %-17s | %-17s | %6s | %s" % ("family", "judge", "mode", "n", "without FBR/det", "with FBR/det", "gain", "J without -> with (det - FBR)   McNemar p (with vs without)"))
    for fam, lab, size, mode, pf, sf in JUDGES:
        wo, wi = rows(pf), rows(sf)
        if wo is None or wi is None:
            print("%-9s %-22s %-8s incomplete (%s)" % (fam, lab, mode, "no plain file" if wo is None else "no schema file"))
            continue
        ids = [i for i in wo if i in wi and contract_flag(cases[i], schemas) is not None]
        ok = np.array([bool(wo[i]["label"]) for i in ids])
        b0 = np.array([blocked_from_row(wo[i]) for i in ids]); b1 = np.array([blocked_from_row(wi[i]) for i in ids])
        u0 = sum(not wo[i]["parsed"] for i in ids); u1 = sum(not wi[i]["parsed"] for i in ids)
        f0, d0, f1, d1 = b0[ok].mean(), b0[~ok].mean(), b1[ok].mean(), b1[~ok].mean()
        mc = mcnemar_exact([(not b) == o for b, o in zip(b1, ok)], [(not b) == o for b, o in zip(b0, ok)])
        print("%-9s %-22s %-8s %5d | %5.1f%% / %5.1f%%   | %5.1f%% / %5.1f%%   | %+5.1f  | J %5.1f -> %5.1f (%+5.1f) | p=%.4f (%d vs %d); unparseable %d/%d" % (
            fam, lab, mode, len(ids), 100 * f0, 100 * d0, 100 * f1, 100 * d1, 100 * (d1 - d0), 100 * (d0 - f0), 100 * (d1 - f1),
            100 * ((d1 - f1) - (d0 - f0)), mc["p"], mc["only_a_correct"], mc["only_b_correct"], u0, u1))
        out.append({"family": fam, "judge": lab, "size_b": size, "mode": mode, "n": len(ids), "without": [round(float(f0), 3), round(float(d0), 3)],
                    "with": [round(float(f1), 3), round(float(d1), 3)], "gain_det": round(float(d1 - d0), 3), "J_without": round(float(d0 - f0), 3), "J_with": round(float(d1 - f1), 3), "mcnemar_p": mc["p"], "unparseable": [u0, u1]})
        by_family.setdefault(fam, []).append((lab, d0, d1))
    print()
    for fam, v in by_family.items():
        if len(v) > 1:
            d0s = [x[1] for x in v]; d1s = [x[2] for x in v]
            print("%-9s spread of detection across sizes: without = %.1f points, with = %.1f points; mean gain from information = %.1f points" % (
                fam, 100 * (max(d0s) - min(d0s)), 100 * (max(d1s) - min(d1s)), 100 * np.mean([b - a for a, b in zip(d0s, d1s)])))
    (B / "ladder_dev.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
