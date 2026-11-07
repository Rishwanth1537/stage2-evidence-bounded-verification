"""
Information ablation (dev only): does showing the judge the tool definition raise detection, and by how much compared with a deterministic
contract check?  For each Claude judge, on the seeded 200-case fcrb dev sample restricted to cases that carry a tool definition:

  without   the earlier judge run (conversation only)
  with      the same judge, same cases, tool definition appended and the one-sentence rule added (agent mode)
  w/o OR contract   judge without the definition, OR the deterministic contract tier
  with OR contract  judge with the definition, OR the contract tier

Reports false-block rate and detection, the exact McNemar test of correctness (with vs without), and the share of the judge's misses
that each route catches.  Judge sizes are compared inside each condition to test whether detection depends on model size or on information.
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
from contract_complement import contract_flag  # noqa: E402
from contract_tier import load_schemas  # noqa: E402
from llm_judge_args import mcnemar_exact  # noqa: E402


def load(name):
    return {r["id"]: r for r in json.loads((ROOT / "benchmarks" / name).read_text(encoding="utf-8"))["rows"]}


def main():
    schemas = load_schemas()
    cases = {c["id"]: c for c in json.loads((ROOT / "benchmarks/data/deref/cases_fcrb.json").read_text(encoding="utf-8"))["cases"]}
    res = {}
    for m in ("haiku", "sonnet", "opus"):
        try:
            wo = load(f"llm_judge_args_fcrb_agent_{m}_dev_v0.json")
            wi = load(f"llm_judge_args_fcrb_schema_custom_agent_{m}_schema_dev_v0.json") if False else None
        except FileNotFoundError:
            continue
        # file name written by llm_judge_args.py: llm_judge_args_<bench tag>_<provider>_<model>_dev_v0.json
        cand = list((ROOT / "benchmarks").glob(f"llm_judge_args_*fcrb_schema*agent_{m}_schema*_dev_v0.json"))
        cand += list((ROOT / "benchmarks").glob(f"llm_judge_args_fcrb_schema_agent_{m}_schema_dev_v0.json"))
        if not cand:
            print(f"{m}: no with-schema result file yet")
            continue
        wi = load(cand[0].name)
        ids = [i for i in wo if i in wi and contract_flag(cases[i], schemas) is not None]
        ok = np.array([bool(wo[i]["label"]) for i in ids])
        b0 = np.array([blocked_from_row(wo[i]) for i in ids]); b1 = np.array([blocked_from_row(wi[i]) for i in ids])
        cf = np.array([bool(contract_flag(cases[i], schemas)) for i in ids])
        row = {"n": len(ids), "n_correct": int(ok.sum()), "n_wrong": int((~ok).sum())}
        for name, b in (("without", b0), ("with", b1), ("without_or_contract", b0 | cf), ("with_or_contract", b1 | cf), ("contract_only", cf)):
            row[name] = {"fbr": round(float(b[ok].mean()), 3), "det": round(float(b[~ok].mean()), 3)}
        row["mcnemar_with_vs_without"] = mcnemar_exact([(not b) == o for b, o in zip(b1, ok)], [(not b) == o for b, o in zip(b0, ok)])
        miss0 = (~ok) & (~b0)
        row["judge_misses_without"] = int(miss0.sum())
        row["of_those_caught_by_with_schema"] = int((miss0 & b1).sum())
        row["of_those_caught_by_contract"] = int((miss0 & cf).sum())
        res[m] = row
        print(m, json.dumps(row))
    (ROOT / "benchmarks" / "schema_ablation_dev.json").write_text(json.dumps(res, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
