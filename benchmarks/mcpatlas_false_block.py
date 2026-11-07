"""
False-block rate of the deterministic argument checker on MCP-Atlas reference tool calls (playbook Stage 2.4).

MCP-Atlas (CC BY 4.0) reference calls are all clean (label correct).  The premise is the user's task text only: later calls of a multi-step
trajectory take values from earlier tool OUTPUTS that the premise does not contain, so a high block rate on later calls measures missing
evidence, not a faulty checker.  This script reports the strict block rate overall, for the first call of each task (where the premise is the
only possible evidence) and for later calls, per-argument verdicts, and the argument names that block most.

  python -I benchmarks/mcpatlas_false_block.py            (writes benchmarks/mcpatlas_fbr_dev.json)
"""
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.pipeline.arg_ground import check_arguments  # noqa: E402


def wilson(k, n, z=1.96):
    if n == 0:
        return [None, None]
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(c - h, 3), round(c + h, 3)]


def literal(s):
    import ast
    if not isinstance(s, str):
        return s
    try:
        return json.loads(s)
    except Exception:
        return ast.literal_eval(s)


def main():
    d = json.loads((ROOT / "benchmarks/data/mcpatlas/cases.json").read_text(encoding="utf-8"))
    cases = d["cases"] if isinstance(d, dict) else d
    rows = []
    for c in cases:
        call = literal(c["call"])
        m = re.match(r"(.*)-(\d+)$", c["id"])
        task, idx = (m.group(1), int(m.group(2))) if m else (c["id"], 0)
        ver = check_arguments(call.get("arguments", {}), c["premise"])
        rows.append({"task": task, "idx": idx, "tool": call.get("name"), "n_args": len(ver),
                     "blocked": any(v.verdict == "UNGROUNDED" for v in ver),
                     "verdicts": [(v.argument, v.verdict) for v in ver]})
    res = {"n_calls": len(rows), "n_tasks": len({r["task"] for r in rows})}

    def block(rs):
        n = len(rs); k = sum(r["blocked"] for r in rs)
        return {"n": n, "blocked": k, "rate": round(k / n, 3) if n else None, "wilson95": wilson(k, n)}

    res["all"] = block(rows)
    res["with_arguments"] = block([r for r in rows if r["n_args"] > 0])
    res["first_call_of_task"] = block([r for r in rows if r["idx"] == 0 and r["n_args"] > 0])
    res["later_calls"] = block([r for r in rows if r["idx"] > 0 and r["n_args"] > 0])
    vc = Counter(v for r in rows for _, v in r["verdicts"])
    res["argument_verdicts"] = dict(vc)
    by_arg = defaultdict(Counter)
    for r in rows:
        for a, v in r["verdicts"]:
            by_arg[a][v] += 1
    res["top_blocking_argument_names"] = sorted(({"arg": a, "ungrounded": c["UNGROUNDED"], "total": sum(c.values())} for a, c in by_arg.items()), key=lambda x: -x["ungrounded"])[:15]
    by_tool = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["n_args"] > 0:
            by_tool[r["tool"]][0] += 1; by_tool[r["tool"]][1] += r["blocked"]
    res["tools_with_most_blocks"] = sorted(({"tool": t, "calls": n, "blocked": k} for t, (n, k) in by_tool.items()), key=lambda x: -x["blocked"])[:10]
    Path(ROOT / "benchmarks" / "mcpatlas_fbr_dev.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("n_calls", "n_tasks", "all", "with_arguments", "first_call_of_task", "later_calls", "argument_verdicts")}, indent=1))
    print(res["top_blocking_argument_names"][:8])


if __name__ == "__main__":
    main()
