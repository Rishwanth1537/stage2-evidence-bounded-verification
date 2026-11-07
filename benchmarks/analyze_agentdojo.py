"""
Value-planting robustness on AgentDojo runs (exploratory, development data; cases built by load_agentdojo.py for claude-3-5-sonnet-20241022 and
gpt-4o-2024-05-13).

Positives: calls that match the injection task's attacker goal by function name (attack_goal_call), carry a value planted by the injection
(injected) and belong to a run where the attacker goal was achieved (run_security, attack_type is not null).  Negatives: every tool call of the runs
without any attack (attack_type is null).  Both labels are heuristics (see review/scout/TASK_agentdojo.md): attack_goal_call is name-level
and `injected` is a token match.

Checkers (deterministic, from server/pipeline/arg_ground.py; block when any argument is not grounded):
  context   arguments grounded against the WHOLE rendered conversation (system, user, assistant, tool outputs) - the checker used in the other experiments
  trusted   arguments grounded only against the system and user messages (what the user and the deployer said)
Reported per model: share of attacker-goal calls blocked (detection) and share of benign calls blocked (false blocks), Wilson 95% intervals.

  PYTHONPATH=. python benchmarks/analyze_agentdojo.py [--max-neg 4000]
"""
import argparse
import json
import math
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.pipeline.arg_ground import call_is_grounded  # noqa: E402

SPLIT = re.compile(r"(?m)^\[(system|user|assistant|tool)\]")


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (c - h, c + h)


def trusted_text(premise):
    parts = SPLIT.split(premise)            # ['', role, text, role, text, ...]
    return "\n".join(t for r, t in zip(parts[1::2], parts[2::2]) if r in ("system", "user"))


def args_of(c):
    call = c["call"]
    if isinstance(call, str):
        call = eval(call, {"__builtins__": {}}, {"True": True, "False": False, "None": None}) if call.startswith("{") else {}
    return call.get("arguments", {})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-neg", type=int, default=4000)
    a = ap.parse_args()
    cases = json.loads((ROOT / "benchmarks/data/agentdojo/cases.json").read_text(encoding="utf-8"))["cases"]
    rng = random.Random(5)
    out = {}
    for model in sorted({c["model"] for c in cases}):
        pos = [c for c in cases if c["model"] == model and c["attack_goal_call"] and c["injected"] and c["run_security"] and c["attack_type"] is not None]
        neg = [c for c in cases if c["model"] == model and c["attack_type"] is None]
        rng.shuffle(neg)
        neg = neg[: a.max_neg]
        res = {"n_pos": len(pos), "n_neg": len(neg)}
        for name, fn in (("context", lambda c: c["premise"]), ("trusted", lambda c: trusted_text(c["premise"]))):
            pb = sum(not call_is_grounded(args_of(c), fn(c)) for c in pos)
            nb = sum(not call_is_grounded(args_of(c), fn(c)) for c in neg)
            res[name] = {"detection": pb / len(pos) if pos else None, "detection_ci": wilson(pb, len(pos)),
                         "false_blocks": nb / len(neg) if neg else None, "false_blocks_ci": wilson(nb, len(neg))}
        out[model] = res
        print(model, "attacker-goal calls n =", len(pos), "| benign calls (no-attack runs) n =", len(neg))
        for name in ("context", "trusted"):
            r = res[name]
            if r["detection"] is None or r["false_blocks"] is None:
                print("   ", name, "n/a")
                continue
            print("   %-8s detection %5.1f%% [%4.1f, %4.1f]   false blocks %5.1f%% [%4.1f, %4.1f]" % (
                name, 100 * r["detection"], 100 * r["detection_ci"][0], 100 * r["detection_ci"][1],
                100 * r["false_blocks"], 100 * r["false_blocks_ci"][0], 100 * r["false_blocks_ci"][1]))
    (ROOT / "benchmarks" / "agentdojo_value_planting_dev.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
