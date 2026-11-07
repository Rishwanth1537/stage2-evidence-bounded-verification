"""
Threshold sweep for GED normalised score.

Evaluates the benchmark dataset at threshold values from 0.05 to 0.95
(step 0.05) and prints a table of accuracy/precision/recall/F1.
Reports the threshold that maximises F1.

Usage:
    python benchmarks/threshold_sweep.py --dataset benchmarks/mcpevol.json
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List


def _metrics(tp: int, fp: int, tn: int, fn: int) -> Dict:
    total = tp + fp + tn + fn
    accuracy = (tp + tn) / total if total else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def sweep(records: List[Dict], steps: int = 19) -> None:
    from server.tools.verify_logic import run_verification

    thresholds = [round(0.05 + i * 0.05, 2) for i in range(steps)]

    # Pre-run pipeline once per record (no threshold dependence)
    print("Running pipeline on all records …", flush=True)
    raw_results = []
    for rec in records:
        result = run_verification(rec["hypothesis"], rec["premise"], threshold=1.0)
        raw_results.append({
            "ged_norm": result.ged_normalised,
            "label": rec["label"],
            "type": rec.get("type", "unknown"),
        })
    print(f"Done. Evaluating {len(thresholds)} thresholds …\n", flush=True)

    header = f"{'Threshold':>10} {'Accuracy':>10} {'Precision':>10} {'Recall':>10} {'F1':>10}"
    print(header)
    print("-" * len(header))

    best_f1 = -1.0
    best_threshold = 0.35

    for t in thresholds:
        tp = fp = tn = fn = 0
        for r in raw_results:
            pred = r["ged_norm"] <= t   # consistent if GED ≤ threshold
            true = r["label"]
            if pred and true:
                tp += 1
            elif pred and not true:
                fp += 1
            elif not pred and not true:
                tn += 1
            else:
                fn += 1
        m = _metrics(tp, fp, tn, fn)
        marker = " <-- best" if m["f1"] > best_f1 else ""
        if m["f1"] > best_f1:
            best_f1 = m["f1"]
            best_threshold = t
        print(
            f"{t:>10.2f} {m['accuracy']:>10.4f} {m['precision']:>10.4f}"
            f" {m['recall']:>10.4f} {m['f1']:>10.4f}{marker}"
        )

    print(f"\nBest threshold: {best_threshold:.2f}  (F1={best_f1:.4f})")
    print(f"Update configs/thresholds.yaml -> ged_threshold: {best_threshold}")


def main() -> None:
    parser = argparse.ArgumentParser(description="GED threshold sweep")
    parser.add_argument("--dataset", required=True, type=Path)
    args = parser.parse_args()

    records = json.loads(args.dataset.read_text())
    sweep(records)


if __name__ == "__main__":
    main()
