"""
Evaluate the 'grounded' design on text-based tool-call cases, without the graph stage (fast, CPU):

  nli_raw             whole-claim NLI (no template), max over overlapping premise windows, entailment >= 0.40
  value_veto_only     deterministic check only: consistent iff every number-like token in the hypothesis occurs in the premise
  grounded            nli_raw AND NOT value_veto          <- the new design (server/tools/verify_grounded.py)

Protocol (stated up front): the value check was motivated by NLI errors seen on benchmarks/mcpevol_v2.json, so v2 is a
DESIGN set. benchmarks/mcpevol_v3.json (different seed, never inspected before design) is the clean held-out test.
Thresholds are fixed (entailment 0.40) and nothing is tuned.

Usage:  PYTHONPATH=. python benchmarks/eval_grounded.py --dataset benchmarks/mcpevol_v3.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmarks.ablation_local import TEXT_TYPES, boot_ci, mcnemar_exact, metrics, raw_entail  # noqa: E402
from server import config  # noqa: E402
from server.pipeline.value_check import unmatched_values  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--output", default=None)
    args = ap.parse_args()
    records = [r for r in json.loads(Path(args.dataset).read_text()) if r.get("type", "content") in TEXT_TYPES]
    thr = config.ENTAILMENT_THRESHOLD
    y = [bool(r["label"]) for r in records]
    ent = [raw_entail(r["premise"], r["hypothesis"]) for r in records]
    um = [unmatched_values(r["hypothesis"], r["premise"]) for r in records]
    preds = {
        "nli_raw": [e >= thr for e in ent],
        "value_veto_only": [not u for u in um],
        "grounded": [(e >= thr) and not u for e, u in zip(ent, um)],
    }
    out = {"dataset": Path(args.dataset).name, "entailment_threshold": thr, "n": len(records),
           "n_consistent": sum(y), "variants": {}, "by_mutation": {}, "mcnemar_exact": {}}
    for k, p in preds.items():
        m = metrics(y, p)
        m["balanced_accuracy_95ci"] = boot_ci(y, p)
        out["variants"][k] = m
    muts = sorted({r.get("mutation", r.get("type")) for r in records})
    for mu in muts:
        idx = [i for i, r in enumerate(records) if r.get("mutation", r.get("type")) == mu]
        out["by_mutation"][mu] = {"n": len(idx), **{k: round(sum(preds[k][i] == y[i] for i in idx) / len(idx), 3) for k in preds}}
    out["mcnemar_exact"]["grounded_vs_nli_raw"] = mcnemar_exact(y, preds["grounded"], preds["nli_raw"])
    out["errors_grounded"] = [{"id": r["id"], "label": y[i], "nli_raw_entail": round(float(ent[i]), 4), "unmatched_values": um[i],
                               "hypothesis": r["hypothesis"], "premise": r["premise"][:160]}
                              for i, r in enumerate(records) if preds["grounded"][i] != y[i]]
    path = Path(args.output) if args.output else ROOT / "benchmarks" / f"grounded_{Path(args.dataset).stem}_results.json"
    path.write_text(json.dumps(out, indent=2))
    print(f"{out['dataset']}: n={len(records)} ({sum(y)} consistent)")
    for k, m in out["variants"].items():
        print(f"  {k:<16} acc={m['accuracy']:.3f} bal_acc={m['balanced_accuracy']:.3f} {m['balanced_accuracy_95ci']} "
              f"P={m['precision']:.2f} R={m['recall']:.2f} spec={m['specificity']:.2f} (TP{m['tp']} FP{m['fp']} TN{m['tn']} FN{m['fn']})")
    print("  McNemar grounded vs nli_raw:", out["mcnemar_exact"]["grounded_vs_nli_raw"])
    print("  by mutation:", json.dumps(out["by_mutation"]))
    print(f"  grounded errors: {len(out['errors_grounded'])}")
    for e in out["errors_grounded"][:5]:
        print("   ", e["id"], "label", e["label"], "ent", e["nli_raw_entail"], e["unmatched_values"], "|", e["hypothesis"])
    print("wrote", path)


if __name__ == "__main__":
    main()
