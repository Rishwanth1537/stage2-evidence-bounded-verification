"""Dev-only diagnostic: why does S2 flag DeRef 'visible' correct arguments that a plain substring check finds?"""
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.pipeline.arg_ground import check_value  # noqa: E402

data = json.loads((ROOT / "benchmarks" / "data" / "deref" / "cases_cfb.json").read_text())
cases = [c for c in data["cases"] if c["split"] == "dev"][:int(sys.argv[1]) if len(sys.argv) > 1 else 120]
kinds, examples, t0 = Counter(), [], time.time()
for c in cases:
    ctx = c["premise"]
    ctx_l = " ".join(ctx.lower().split())
    for a in c["args_meta"]:
        if not (a["in_analysis"] and a["path"] == "visible" and a["label"] == "correct"):
            continue
        v = check_value(a["name"], a["value"], ctx)
        if v.verdict == "UNGROUNDED":
            val = a["value"]
            kind = type(val).__name__
            if isinstance(val, (int, float)) and val < 0:
                kind += "-negative"
            elif isinstance(val, float) and val == int(val):
                kind += "-integer-valued"
            elif isinstance(val, float):
                kind += "-fractional"
            elif isinstance(val, str) and len(val) > 40:
                kind += "-long(>40)"
            elif isinstance(val, str) and val.replace("-", "").replace("_", "").isalnum() and any(ch.isdigit() for ch in val):
                kind += "-alnum-id"
            elif isinstance(val, list):
                kind += "-list"
            kinds[kind] += 1
            if len(examples) < 14:
                examples.append((a["name"], repr(val)[:70], str(val).lower() in ctx_l, v.score))
print(f"{len(cases)} cases, {time.time() - t0:.1f}s; flagged visible-correct args by kind:", dict(kinds))
for e in examples:
    print("  ", e)
