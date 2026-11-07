"""
Component ablation on MCPEvol-Bench (text-based cases), fully replicable on CPU.

Variants (all use FIXED thresholds from configs/thresholds.yaml; nothing is tuned on the benchmark):
  nli_only    whole hypothesis vs premise, entailment >= entailment_threshold
  ged_only    symmetric value-aware GED, norm_ged <= ged_threshold
  hybrid      the shipped pipeline (run_verification): GED gate AND span-level NLI
  hybrid_asym same pipeline with an experimental asymmetric hypothesis-in-premise GED
              (no symmetry swap, hypothesis-side cost only, no premise-extra penalty, no value bonus)

Schema/format cases are handled by the deterministic validator in the shipped pipeline and are reported
separately: those cases are constructed schema violations, so they say nothing about text grounding.

Usage:  PYTHONPATH=. python benchmarks/ablation_local.py
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scipy.optimize import linear_sum_assignment  # noqa: E402

from server import config  # noqa: E402
from server.pipeline import ged as ged_mod  # noqa: E402
from server.pipeline.entailment import _load_pipeline, _premise_windows, score_spans  # noqa: E402
from server.pipeline.graph_builder import build_semantic_graph  # noqa: E402
from server.tools import verify_logic  # noqa: E402
from server.tools.schema import run_schema_alignment  # noqa: E402

SEED = 42
N_BOOT = 2000
TEXT_TYPES = ("content", "negation", "role_swap")


def asym_ged(G_hyp, G_prem):
    """Experimental: cost of embedding the hypothesis graph into the premise graph."""
    hn, pn = list(G_hyp.nodes(data=True)), list(G_prem.nodes(data=True))
    n, m = len(hn), len(pn)
    if n == 0:
        return 0.0, 0.0
    if m == 0:
        return float(n), 1.0
    cost = np.array([[ged_mod._node_subst_cost(a, aa, b, bb) for b, bb in pn] for a, aa in hn])
    rows, cols = linear_sum_assignment(cost)
    total = float(cost[rows, cols].sum()) + max(0, n - m)  # unmatched hypothesis nodes cost 1
    mapping = {hn[i][0]: pn[j][0] for i, j in zip(rows, cols)}
    for u, v, d in G_hyp.edges(data=True):
        mu, mv = mapping.get(u), mapping.get(v)
        if mu is not None and mv is not None and G_prem.has_edge(mu, mv):
            total += ged_mod._edge_subst_cost(d, G_prem[mu][mv])
        else:
            total += 1.0
    denom = n + G_hyp.number_of_edges()
    return total, max(0.0, min(1.0, total / denom if denom else 0.0))


def raw_entail(premise: str, hypothesis: str) -> float:
    """Whole-claim entailment WITHOUT the repo's hypothesis template; max over overlapping premise windows."""
    clf = _load_pipeline()
    inputs = [{"text": w, "text_pair": hypothesis} for w in _premise_windows(premise)]
    best = 0.0
    for scores in clf(inputs):
        if isinstance(scores, list) and scores and isinstance(scores[0], list):
            scores = scores[0]
        best = max(best, next((x["score"] for x in scores if x["label"].lower() == "entailment"), 0.0))
    return best


def select_veto_threshold(y, ent_raw, asym, ent_thr):
    """Pick the asymmetric-GED veto threshold that maximises balanced accuracy of NLI-raw AND asym<=thr on this data."""
    best, best_t = -1.0, None
    for t in [x / 100 for x in range(5, 81, 5)]:
        pred = [(e >= ent_thr) and (a <= t) for e, a in zip(ent_raw, asym)]
        ba = metrics(y, pred)["balanced_accuracy"]
        if ba > best + 1e-12:
            best, best_t = ba, t
    return best_t, best


def metrics(y, p):
    y, p = np.asarray(y, bool), np.asarray(p, bool)
    tp, fp, tn, fn = int((p & y).sum()), int((p & ~y).sum()), int((~p & ~y).sum()), int((~p & y).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    spec = tn / (tn + fp) if tn + fp else 0.0
    return dict(n=len(y), accuracy=(tp + tn) / len(y), balanced_accuracy=(rec + spec) / 2, precision=prec,
                recall=rec, specificity=spec, f1=2 * prec * rec / (prec + rec) if prec + rec else 0.0,
                tp=tp, fp=fp, tn=tn, fn=fn)


def boot_ci(y, p, key="balanced_accuracy"):
    rng = np.random.default_rng(SEED)
    y, p = np.asarray(y, bool), np.asarray(p, bool)
    vals = []
    for _ in range(N_BOOT):
        i = rng.integers(0, len(y), len(y))
        if y[i].all() or (~y[i]).all():
            continue
        vals.append(metrics(y[i], p[i])[key])
    return [round(float(np.percentile(vals, 2.5)), 3), round(float(np.percentile(vals, 97.5)), 3)]


def mcnemar_exact(y, pa, pb):
    ca, cb = np.asarray(pa) == np.asarray(y), np.asarray(pb) == np.asarray(y)
    b, c = int((ca & ~cb).sum()), int((~ca & cb).sum())
    n = b + c
    if n == 0:
        return dict(only_a_correct=b, only_b_correct=c, p=1.0)
    k = min(b, c)
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)
    return dict(only_a_correct=b, only_b_correct=c, p=round(p, 4))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=str(ROOT / "benchmarks" / "mcpevol.json"))
    ap.add_argument("--output", default=str(ROOT / "benchmarks" / "ablation_results.json"))
    ap.add_argument("--veto-threshold", type=float, default=None,
                    help="asymmetric-GED veto threshold; if omitted it is selected on THIS dataset (optimistic)")
    args = ap.parse_args()
    records = json.loads(Path(args.dataset).read_text())
    ged_thr, ent_thr = config.GED_THRESHOLD, config.ENTAILMENT_THRESHOLD
    print(f"fixed thresholds: ged={ged_thr} entailment={ent_thr}; {len(records)} records")

    text = [r for r in records if r.get("type", "content") in TEXT_TYPES]
    y = [bool(r["label"]) for r in text]
    preds = {k: [] for k in ("nli_only", "nli_raw", "ged_only", "hybrid", "hybrid_asym")}
    scores = {"nli_only": [], "nli_raw": [], "ged_only": [], "asym_norm": []}

    orig_ged = verify_logic.compute_ged
    for i, r in enumerate(text):
        h, p = r["hypothesis"], r["premise"]
        Gh, Gp = build_semantic_graph(h), build_semantic_graph(p)
        _, norm = ged_mod.compute_ged(Gh, Gp)
        _, norm_a = asym_ged(Gh, Gp)
        ent = score_spans(p, [h])[0][1]
        ent_r = raw_entail(p, h)
        scores["nli_only"].append(ent); scores["nli_raw"].append(ent_r); scores["ged_only"].append(1 - norm); scores["asym_norm"].append(norm_a)
        preds["nli_only"].append(ent >= ent_thr)
        preds["nli_raw"].append(ent_r >= ent_thr)
        preds["ged_only"].append(norm <= ged_thr)
        preds["hybrid"].append(bool(verify_logic.run_verification(h, p, ged_thr).is_consistent))
        verify_logic.compute_ged = lambda a, b: asym_ged(a, b)
        try:
            preds["hybrid_asym"].append(bool(verify_logic.run_verification(h, p, ged_thr).is_consistent))
        finally:
            verify_logic.compute_ged = orig_ged
        print(f"  {i + 1}/{len(text)}", end="\r")
    print()

    if args.veto_threshold is None:
        veto_thr, veto_ba = select_veto_threshold(y, scores["nli_raw"], scores["asym_norm"], ent_thr)
        veto_note = f"selected on this dataset (balanced accuracy {veto_ba:.3f}; optimistic)"
    else:
        veto_thr, veto_note = args.veto_threshold, "fixed in advance (selected elsewhere)"
    preds["nli_raw_asym_veto"] = [(e >= ent_thr) and (a <= veto_thr) for e, a in zip(scores["nli_raw"], scores["asym_norm"])]
    print(f"asymmetric-GED veto threshold = {veto_thr} ({veto_note})")

    # schema / format cases, shipped validator
    sch = [r for r in records if r.get("type") in ("schema", "format")]
    ys = [bool(r["label"]) for r in sch]
    ps = []
    for r in sch:
        ts = r.get("tool_schema")
        ps.append(bool(run_schema_alignment(r.get("agent_args", {}), ts, threshold=ged_thr).is_aligned))

    out = {"dataset": Path(args.dataset).name,
           "thresholds": {"ged": ged_thr, "entailment": ent_thr, "veto": veto_thr, "veto_selection": veto_note,
                          "tuned_on_benchmark": args.veto_threshold is None},
           "n_text": len(text), "n_schema_format": len(sch), "text_variants": {}, "schema_format_validator": metrics(ys, ps) if ys else None,
           "by_type": {}, "mcnemar_exact": {}}
    for k, p in preds.items():
        m = metrics(y, p)
        m["balanced_accuracy_95ci"] = boot_ci(y, p)
        out["text_variants"][k] = m
    for t in TEXT_TYPES:
        idx = [i for i, r in enumerate(text) if r.get("type", "content") == t]
        out["by_type"][t] = {k: round(metrics([y[i] for i in idx], [preds[k][i] for i in idx])["accuracy"], 3) for k in preds}
        out["by_type"][t]["n"] = len(idx)
    for a, b in (("hybrid", "nli_only"), ("hybrid", "ged_only"), ("hybrid_asym", "hybrid"),
                 ("nli_raw", "nli_only"), ("nli_raw_asym_veto", "nli_raw"), ("nli_raw_asym_veto", "hybrid")):
        out["mcnemar_exact"][f"{a}_vs_{b}"] = mcnemar_exact(y, preds[a], preds[b])
    out["predictions"] = [{"id": r["id"], "type": r.get("type"), "label": y[i], **{k: bool(preds[k][i]) for k in preds},
                           "nli_entail": round(float(scores["nli_only"][i]), 4),
                           "nli_raw_entail": round(float(scores["nli_raw"][i]), 4),
                           "ged_norm_sym": round(float(1 - scores["ged_only"][i]), 4),
                           "ged_norm_asym": round(float(scores["asym_norm"][i]), 4)} for i, r in enumerate(text)]
    path = Path(args.output)
    path.write_text(json.dumps(out, indent=2))

    print(f"\nText-based cases (n={len(text)}; {sum(y)} consistent / {len(y) - sum(y)} hallucinated)")
    for k, m in out["text_variants"].items():
        print(f"  {k:<12} acc={m['accuracy']:.3f} bal_acc={m['balanced_accuracy']:.3f} {m['balanced_accuracy_95ci']} "
              f"P={m['precision']:.2f} R={m['recall']:.2f} spec={m['specificity']:.2f} (TP{m['tp']} FP{m['fp']} TN{m['tn']} FN{m['fn']})")
    print("  by type (accuracy):", json.dumps(out["by_type"]))
    print("  McNemar exact:", json.dumps(out["mcnemar_exact"]))
    m = out["schema_format_validator"]
    if m:
        print(f"Schema/format validator (n={len(sch)}): acc={m['accuracy']:.3f}")
    print("wrote", path)


if __name__ == "__main__":
    main()
