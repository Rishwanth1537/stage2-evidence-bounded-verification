"""
Does the contract tier add to a judge?  On the dev judge sample (fcrb, calls with a schema) compute, for each judge result file,
judge alone, judge OR contract, and the contract violations on the wrong calls the judge MISSED.  Dev only.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))
from analyze_study import blocked_from_row  # noqa: E402
from contract_tier import load_schemas, pick, violations  # noqa: E402


def contract_flag(c, schemas):
    calls = c.get("calls") or [c["call"]]
    seen = False
    for a in c["args_meta"]:
        if not a["in_analysis"]:
            continue
        ci = a.get("call_index", 0)
        call = calls[ci] if ci < len(calls) else calls[0]
        fn = pick(schemas, call)
        if fn is None:
            return None
        props = fn.get("parameters", {}).get("properties", {})
        v = ["unknown_arg"] if a["name"] not in props else violations(props[a["name"]], a["value"])
        seen = seen or any(k in v for k in ("type", "enum", "fmt_city_state", "fmt_date", "fmt_time", "unknown_arg"))
    return seen


def main():
    schemas = load_schemas()
    cases = {c["id"]: c for c in json.loads((ROOT / "benchmarks/data/deref/cases_fcrb.json").read_text(encoding="utf-8"))["cases"]}
    files = {"Groq gpt-oss-120b": "llm_judge_args_fcrb_groq_openai_gpt_oss_120b_dev_v0.json",
             "Haiku": "llm_judge_args_fcrb_agent_haiku_dev_v0.json", "Sonnet": "llm_judge_args_fcrb_agent_sonnet_dev_v0.json",
             "Opus": "llm_judge_args_fcrb_agent_opus_dev_v0.json"}
    out = {}
    for name, f in files.items():
        rows = json.loads((ROOT / "benchmarks" / f).read_text(encoding="utf-8"))["rows"]
        keep = []
        for r in rows:
            cf = contract_flag(cases[r["id"]], schemas)
            if cf is not None:
                keep.append((r, cf))
        ok = np.array([bool(r["label"]) for r, _ in keep])           # True = correct call
        jb = np.array([blocked_from_row(r) for r, _ in keep]); cb = np.array([cf for _, cf in keep])
        u = jb | cb
        missed = (~ok) & (~jb)
        out[name] = {"n": len(keep), "judge_fbr": round(float(jb[ok].mean()), 3), "judge_det": round(float(jb[~ok].mean()), 3),
                     "union_fbr": round(float(u[ok].mean()), 3), "union_det": round(float(u[~ok].mean()), 3),
                     "contract_catches_of_judge_missed": f"{int((missed & cb).sum())}/{int(missed.sum())}",
                     "extra_false_blocks": int((ok & cb & ~jb).sum()), "n_correct": int(ok.sum())}
        print(name, out[name])
    (ROOT / "benchmarks" / "contract_complement_dev.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
