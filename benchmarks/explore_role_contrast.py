"""
Exploratory (DEV half only): contrastive role check for arguments whose value is visible in the context.

For an argument (name, value) in a call that has other arguments, verbalise "<name words>: <value>" with every argument name of the
same call and ask a local NLI model (cross-encoder/nli-deberta-v3-base, the project's existing model) how strongly the request
entails each.  Contrast score = entail(this role) - max(entail(other roles)); a value that fits another role of the same call better
than its own (an actor's name in directed_by while a cast argument exists) gets a negative contrast.

Reports AUROC at argument level (visible-wrong vs visible-correct) for plain entailment and for the contrast, per dataset path.
Reads only split == "dev".  Run with the .venv python:  U:\txt\.venv\Scripts\python.exe benchmarks\explore_role_contrast.py
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.pipeline.entailment import score_claim  # noqa: E402


def words(name):
    return re.sub(r"[_\-]+", " ", re.sub(r"([a-z])([A-Z])", r"\1 \2", name)).strip().lower()


def verbalise(name, value):
    return f"The {words(name)} is {value}."


def auroc(y, s):
    y = np.asarray(y, bool); s = np.asarray(s, float)
    pos, neg = s[y], s[~y]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    gt = (pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()
    return float(gt / (len(pos) * len(neg)))


def main():
    cases = [c for c in json.loads((ROOT / "benchmarks/data/deref/cases_fcrb.json").read_text(encoding="utf-8"))["cases"] if c["split"] == "dev"]
    rows = []
    cache = {}

    def ent(premise, hyp):
        k = (premise, hyp)
        if k not in cache:
            cache[k] = float(score_claim(premise, hyp))
        return cache[k]

    for ci, c in enumerate(cases):
        call = c["call"]
        args = call["arguments"]
        for a in c["args_meta"]:
            if not a["in_analysis"] or a["path"] != "visible" or a["name"] not in args:
                continue
            v = a["value"]
            if isinstance(v, bool) or v is None or str(v).lower() in ("dontcare", "true", "false", ""):
                continue
            own = ent(c["premise"], verbalise(a["name"], v))
            others = [n for n in args if n != a["name"] and args[n] not in (None, "", "dontcare", True, False)]
            oth = [ent(c["premise"], verbalise(n, v)) for n in others]
            rows.append({"wrong": a["label"] == "wrong", "own": own, "contrast": own - max(oth) if oth else own,
                         "has_other": bool(oth), "name": a["name"], "value": str(v)})
        if (ci + 1) % 100 == 0:
            print(f"  {ci + 1}/{len(cases)} cases, {len(cache)} NLI calls", flush=True)
    y = [r["wrong"] for r in rows]
    # lower entailment / lower contrast = more suspicious, so use the negative as the "wrongness" score
    print("visible args scored:", len(rows), "wrong:", sum(y))
    print("AUROC wrong-vs-correct, plain entailment:", round(auroc(y, [-r["own"] for r in rows]), 3))
    print("AUROC wrong-vs-correct, role contrast  :", round(auroc(y, [-r["contrast"] for r in rows]), 3))
    sub = [r for r in rows if r["has_other"]]
    ys = [r["wrong"] for r in sub]
    print("subset with another filled argument:", len(sub), "wrong:", sum(ys))
    print("  plain:", round(auroc(ys, [-r["own"] for r in sub]), 3), " contrast:", round(auroc(ys, [-r["contrast"] for r in sub]), 3))
    out = ROOT / "benchmarks" / "role_contrast_dev.json"
    out.write_text(json.dumps(rows, indent=0), encoding="utf-8")
    print("wrote", out.name)


if __name__ == "__main__":
    main()
