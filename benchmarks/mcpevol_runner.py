"""
MCPEvol-Bench evaluation harness.

Usage:
    python benchmarks/mcpevol_runner.py --dataset path/to/mcpevol.json --output results.json
    python benchmarks/mcpevol_runner.py --dataset path/to/mcpevol.json --verbose

Dataset record schema:
    {
        "id":         str,
        "hypothesis": str,
        "premise":    str,
        "label":      bool,          # True = consistent, False = hallucinated
        "type":       str            # "schema" | "format" | "content" | "negation" | "role_swap"

        # Required when type == "schema" or "format"
        "agent_args":  dict          # agent's planned arguments
        "tool_schema": dict          # JSON Schema {"properties":…, "required":[…]}
    }

Routing:
    type == "schema" | "format"         → run_schema_alignment  (typed field validation)
    type == "content" | "negation"      → run_verification      (text-based semantic pipeline)
         | "role_swap"
    type missing                        → run_verification      (safe default)
"""
from __future__ import annotations
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from server.tools.verify_logic import run_verification
from server.tools.schema import run_schema_alignment
from server.models.schemas import MismatchedSpan


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
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
    }


def _synthetic_schema(hypothesis: str, premise: str) -> Dict[str, Any]:
    """
    When a schema-type record has no explicit agent_args/tool_schema,
    synthesise a minimal schema from key=value pairs in the premise.
    Fallback: treat the full premise as a single 'content' field.
    """
    pairs = re.findall(r"(\w+)\s*[:=]\s*(\S+)", premise)
    if pairs:
        fields = [k for k, _ in pairs]
        return {
            "required": fields,
            "properties": {f: {"type": "string"} for f in fields},
        }
    return {
        "required": ["content"],
        "properties": {"content": {"type": "string"}},
    }


def _run_record(
    rec: Dict, threshold: float
) -> Tuple[bool, float, float, List[MismatchedSpan], str]:
    """
    Dispatch a single benchmark record to the correct verification tool.
    Returns (pred_label, score, ged_norm, mismatched_spans, feedback).
    """
    rec_type = rec.get("type", "content")

    if rec_type in ("schema", "format"):
        agent_args: Dict[str, Any] = rec.get("agent_args", {})
        tool_schema: Dict[str, Any] = rec.get("tool_schema") or _synthetic_schema(
            rec["hypothesis"], rec["premise"]
        )
        result = run_schema_alignment(agent_args, tool_schema, threshold=threshold)
        feedback = (
            "; ".join(m.issue for m in result.mismatches)
            if result.mismatches
            else "Schema aligned."
        )
        return result.is_aligned, result.schema_drift_score, 0.0, result.mismatches, feedback

    # content / negation / role_swap — text-based semantic pipeline
    result = run_verification(rec["hypothesis"], rec["premise"], threshold)
    return (
        result.is_consistent,
        result.factual_consistency_score,
        result.ged_normalised,
        result.mismatched_spans,
        result.feedback,
    )


def evaluate(records: List[Dict], threshold: float = 0.35, verbose: bool = False) -> Dict:
    tp = fp = tn = fn = 0
    type_buckets: Dict[str, Dict] = defaultdict(lambda: {"tp": 0, "fp": 0, "tn": 0, "fn": 0})
    predictions = []

    for rec in records:
        pred_label, score, ged_norm, mismatches, feedback = _run_record(rec, threshold)
        true_label = rec["label"]
        rec_type = rec.get("type", "unknown")

        if pred_label and true_label:
            tp += 1; type_buckets[rec_type]["tp"] += 1; outcome = "TP  "
        elif pred_label and not true_label:
            fp += 1; type_buckets[rec_type]["fp"] += 1; outcome = "FP! "
        elif not pred_label and not true_label:
            tn += 1; type_buckets[rec_type]["tn"] += 1; outcome = "TN  "
        else:
            fn += 1; type_buckets[rec_type]["fn"] += 1; outcome = "FN! "

        if verbose:
            print(
                f"  [{rec['id']:>4}] {outcome:<5}  pred={str(pred_label):<5}  "
                f"truth={str(true_label):<5}  score={score:.4f}  "
                f"ged={ged_norm:.4f}  type={rec_type}"
            )

        predictions.append({
            "id": rec["id"],
            "prediction": pred_label,
            "ground_truth": true_label,
            "type": rec_type,
            "score": score,
            "ged_norm": ged_norm,
            "mismatched_spans": [
                {"span": m.span, "type": m.hallucination_type, "issue": m.issue}
                for m in mismatches
            ],
            "feedback": feedback,
        })

    overall = _metrics(tp, fp, tn, fn)
    per_type = {
        htype: _metrics(**buckets)
        for htype, buckets in type_buckets.items()
    }

    return {
        **overall,
        "per_type_metrics": per_type,
        "predictions": predictions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="MCPEvol-Bench evaluation harness")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", default="benchmarks/results.json", type=Path)
    parser.add_argument("--threshold", default=0.35, type=float)
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print per-case id, prediction, GED score, and outcome.",
    )
    args = parser.parse_args()

    records = json.loads(args.dataset.read_text())

    if args.verbose:
        print(f"Evaluating {len(records)} records at threshold={args.threshold} …")

    metrics = evaluate(records, threshold=args.threshold, verbose=args.verbose)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metrics, indent=2))
    print(f"\nAccuracy: {metrics['accuracy']}  F1: {metrics['f1']}")
    if metrics.get("per_type_metrics"):
        for htype, m in metrics["per_type_metrics"].items():
            print(f"  [{htype}] acc={m['accuracy']} f1={m['f1']}")
    print(f"Results written to {args.output}")


if __name__ == "__main__":
    main()
