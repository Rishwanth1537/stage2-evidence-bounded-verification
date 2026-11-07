"""
Cost and latency of the deterministic checker, measured on this machine, next to the judge figures recorded in the judge result files.

  PYTHONPATH=. python benchmarks/measure_cost.py [--repeats 5] [--out benchmarks/cost_latency_dev.json]

Checker: wall-clock time of scoring one call (all arguments against the full context), single thread, after a warm-up pass, over the same
seeded dev samples the judges saw (fcrb 200, cfb 100 with FULL contexts, injected 200).  Timings exclude Python start-up and module import.
Judges: mean/p95 latency and mean tokens per call as recorded by llm_judge_args.py (network round trip to a hosted API; free-tier queueing
and retries can inflate it).  Agent-mode judges have no latency or token record.  No prices are used: tokens are reported, not dollars.
"""
import argparse
import glob
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))
from agent_judge import sample_cases  # noqa: E402
from server.pipeline.arg_ground import call_score  # noqa: E402
from eval_deref import score_case  # noqa: E402


def time_calls(fn, cases, repeats):
    for c in cases[:10]:
        fn(c)                                     # warm-up (regex compilation, caches)
    per = []
    for c in cases:
        best = []
        for _ in range(repeats):
            t0 = time.perf_counter(); fn(c); best.append(time.perf_counter() - t0)
        per.append(min(best))                     # best of N per case removes scheduler noise
    ms = np.array(per) * 1000
    return {"n": len(ms), "mean_ms": round(float(ms.mean()), 3), "p50_ms": round(float(np.percentile(ms, 50)), 3),
            "p95_ms": round(float(np.percentile(ms, 95)), 3), "max_ms": round(float(ms.max()), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--out", default=str(ROOT / "benchmarks" / "cost_latency_dev.json"))
    a = ap.parse_args()
    sets = {
        "fcrb": (str(ROOT / "benchmarks/data/deref/cases_fcrb.json"), 200, lambda c: score_case(c)),
        "cfb": (str(ROOT / "benchmarks/data/deref/cases_cfb.json"), 100, lambda c: score_case(c)),
        "injected": (str(ROOT / "benchmarks/argground_bench.json"), 200, lambda c: call_score(c["call"]["arguments"], c["premise"])),
    }
    res = {"machine": {"platform": platform.platform(), "processor": platform.processor(), "python": platform.python_version()},
           "checker": {}, "judges": {}}
    for name, (bench, limit, fn) in sets.items():
        cases = sample_cases(bench, "dev", limit, 0)
        res["checker"][name] = time_calls(fn, cases, a.repeats)
        res["checker"][name]["mean_context_chars"] = round(float(np.mean([len(c["premise"]) for c in cases])), 0)
        print(name, res["checker"][name])
    for f in sorted(glob.glob(str(ROOT / "benchmarks" / "llm_judge_args_*_dev_v0.json"))):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        j = d["judge"]
        res["judges"][Path(f).name] = {"n": j["n"], "latency_s_mean": j.get("latency_s_mean"), "latency_s_p95": j.get("latency_s_p95"),
                                       "tokens_mean": j.get("tokens_mean") or None}
    Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    for k, v in res["judges"].items():
        print(k[16:-12], v)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
