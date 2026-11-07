"""Dev-only experiment: can NLI rescue arguments that the deterministic matcher marks UNGROUNDED?
One fixed hypothesis template (no template search): "The {argument name} is {value}."
Outputs per-argument entailment scores for gold (should be rescued) vs injected (must stay blocked) arguments."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))

from eval_argground import split_cases  # noqa: E402
from server.pipeline.arg_ground import check_arguments  # noqa: E402
from server.pipeline.entailment import score_claim  # noqa: E402

cases = json.loads((ROOT / "benchmarks" / "argground_bench.json").read_text())["cases"]
dev, _ = split_cases(cases)
rows = []
for c in dev:
    for v in check_arguments(c["call"]["arguments"], c["premise"]):
        if v.verdict != "UNGROUNDED":
            continue
        hyp = f"The {v.argument.replace('_', ' ')} is {v.value}."
        rows.append({"id": c["id"], "gold": bool(c["label"]), "argument": v.argument, "value": v.value,
                     "changed": (not c["label"]) and c["change"]["argument"] == v.argument,
                     "ent": score_claim(c["premise"], hyp)})
print(len(rows), "ungrounded args on dev; gold:", sum(r["gold"] for r in rows))
y = np.array([r["gold"] for r in rows])   # positive = should be rescued (legit)
s = np.array([r["ent"] for r in rows])


def auroc(y, s):
    from scipy.stats import rankdata
    r = rankdata(s); n1, n0 = y.sum(), (~y).sum()
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


print("AUROC (gold-legit vs injected):", round(auroc(y, s), 3))
for t in (0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9):
    print(f"  thr {t}: rescues {np.mean(s[y] >= t):.2f} of legit, and also lets through {np.mean(s[~y] >= t):.3f} of injected")
Path(ROOT / "benchmarks" / "argground_rescue_dev.json").write_text(json.dumps(rows, indent=1))
