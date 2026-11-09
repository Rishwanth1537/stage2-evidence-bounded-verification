"""
E1 Residual Analysis — Characterise the 34.4% FBR that persists after trajectory evidence.

Fast-path heuristic (avoids re-running spaCy on 2,423 cases which takes ~23 min):

    An arg is considered UNGROUNDED if str(value) does NOT appear as a
    case-insensitive substring in the evidence string.  This matches the
    dominant signal used by check_arguments (substring/token presence);
    spaCy entity matching adds precision at the margins but the primary
    block signal is literal absence.

    A call is classified as residual-blocked if ANY arg is ungrounded by
    the heuristic AFTER adding earlier_tool_outputs.

For every residual UNGROUNDED argument, classify into failure mode:

    DATE_RANGE      — arg name or value looks like a date / date-range.
                      These need contract-default evidence (E2 territory).

    NUMERIC_DEFAULT — arg is a plain number (limit, max_results, count …).
                      Implicit defaults not stated in conversation.

    MULTI_HOP_ARITH — arg value contains arithmetic / code-to-evaluate.
                      Fundamentally undecidable from text alone.

    PARAPHRASE      — multi-word natural-language string absent literally
                      but plausibly paraphrased.  Fuzzy tolerance could help.

    URL_DERIVED     — URL that can be templated from evidence but not
                      stated verbatim.

    OTHER           — none of the above.

Outputs:  benchmarks/residual_analysis_dev.json
Analysis of Deviation 22 outcome; no new deviation required.
"""
from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmarks.provenance_grounding import build_provenance_context  # noqa: E402


# ---------------------------------------------------------------------------
# Fast substring grounding heuristic
# ---------------------------------------------------------------------------

def is_grounded_fast(value: str, evidence: str) -> bool:
    """Return True if value appears as a substring (case-insensitive) in evidence."""
    v = str(value).strip()
    if not v:
        return True  # empty / null arg is not a grounding failure
    # For numbers, also try without leading zeros etc.
    return v.lower() in evidence.lower()


# ---------------------------------------------------------------------------
# Failure mode classifier
# ---------------------------------------------------------------------------

_DATE_ARG_NAMES = re.compile(
    r"\b(date|from|to|start|end|since|until|before|after|created|modified|"
    r"published|at|time|year|month|day|deadline|due|timestamp)\b",
    re.I,
)
_DATE_VALUE = re.compile(
    r"\b\d{4}[-/]\d{2}[-/]\d{2}\b"
    r"|\b\d{2}[-/]\d{2}[-/]\d{4}\b"
    r"|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2},?\s+\d{4}\b"
    r"|\b\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
    re.I,
)
_NUMERIC_ARG_NAMES = re.compile(
    r"\b(limit|count|max|min|top|num|n_|number_of|results|size|per_page|"
    r"page_size|offset|skip|take|rows|records|items|k|n)\b",
    re.I,
)
_ARITHMETIC_VALUE = re.compile(
    r"[\d\s]*(?:[\+\-\*\/\^][\s\d\.]+){2,}"
    r"|print\s*\("
    r"|def\s+\w+"
    r"|import\s+\w+"
    r"|=\s*\w+\s*[\+\-\*\/]",
)
_URL_VALUE = re.compile(r"^https?://", re.I)


def classify_arg(arg_name: str, arg_value: str) -> str:
    name = arg_name.lower()
    val = str(arg_value)

    if _DATE_ARG_NAMES.search(name) or _DATE_VALUE.search(val):
        return "DATE_RANGE"

    if _ARITHMETIC_VALUE.search(val):
        return "MULTI_HOP_ARITH"

    if _URL_VALUE.match(val.strip()):
        return "URL_DERIVED"

    # Numeric default: value is purely numeric
    try:
        float(val.strip())
        return "NUMERIC_DEFAULT"
    except (ValueError, TypeError):
        pass
    if re.match(r"^\d+$", val.strip()):
        return "NUMERIC_DEFAULT"
    if _NUMERIC_ARG_NAMES.search(name) and re.search(r"\d", val):
        return "NUMERIC_DEFAULT"

    # Paraphrase: multi-word natural language string
    if len(val.split()) >= 3:
        return "PARAPHRASE"

    return "OTHER"


# ---------------------------------------------------------------------------
# Wilson CI
# ---------------------------------------------------------------------------

def wilson(k: int, n: int, z: float = 1.96) -> list:
    if n == 0:
        return [None, None]
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(c - h, 3), round(c + h, 3)]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

ORDERED_CATS = ["DATE_RANGE", "NUMERIC_DEFAULT", "MULTI_HOP_ARITH",
                "PARAPHRASE", "URL_DERIVED", "OTHER"]


def main() -> None:
    data_path = ROOT / "benchmarks" / "data" / "mcpatlas" / "cases_v2.json"
    if not data_path.exists():
        sys.exit(f"cases_v2.json not found at {data_path}")

    raw = json.loads(data_path.read_text(encoding="utf-8"))
    cases = raw["cases"] if isinstance(raw, dict) else raw

    arg_cats: Counter = Counter()
    call_dominant_cat: Counter = Counter()
    first_call_cats: Counter = Counter()
    later_call_cats: Counter = Counter()
    still_ungrounded_names: Counter = Counter()

    residual_calls = 0
    total_calls_with_args = 0

    for c in cases:
        call = c.get("call", {})
        args = call.get("arguments", {}) if isinstance(call, dict) else {}
        if not args:
            continue

        total_calls_with_args += 1
        premise = c.get("premise", "") or ""
        step_index = c.get("step_index", 1)
        earlier = c.get("earlier_tool_outputs", []) or []

        evidence = build_provenance_context(premise, earlier)

        # Fast heuristic: check each arg
        ungrounded_args = {
            k: str(v)
            for k, v in args.items()
            if not is_grounded_fast(str(v), evidence)
        }

        if not ungrounded_args:
            continue

        residual_calls += 1
        cats_this_call: list[str] = []

        for arg_name, arg_val in ungrounded_args.items():
            cat = classify_arg(arg_name, arg_val)
            arg_cats[cat] += 1
            cats_this_call.append(cat)
            still_ungrounded_names[arg_name] += 1

        dominant = Counter(cats_this_call).most_common(1)[0][0]
        call_dominant_cat[dominant] += 1
        if step_index == 1:
            first_call_cats[dominant] += 1
        else:
            later_call_cats[dominant] += 1

    total_ungrounded_args = sum(arg_cats.values())

    # --- Print ---
    print("=" * 65)
    print("E1 Residual Analysis — Failure-Mode Breakdown")
    print(f"(Fast heuristic: substring match; no spaCy NLP)")
    print(f"Residual blocked calls: {residual_calls} / {total_calls_with_args} "
          f"({residual_calls/total_calls_with_args*100:.1f}%)")
    print(f"Total UNGROUNDED args (heuristic, after provenance): "
          f"{total_ungrounded_args}")
    print("=" * 65)

    n = total_ungrounded_args
    print("\n--- By ARGUMENT (all residual UNGROUNDED args) ---")
    print(f"{'Category':<20} {'Count':>7} {'Share':>8}  {'95% CI'}")
    print("-" * 55)
    for cat in ORDERED_CATS:
        k = arg_cats[cat]
        pct = k / n * 100 if n else 0
        ci = wilson(k, n)
        print(f"{cat:<20} {k:>7} {pct:>7.1f}%  [{ci[0]*100:.1f}, {ci[1]*100:.1f}]")

    print("\n--- By CALL (dominant failure mode per call) ---")
    print(f"{'Category':<20} {'All':>6} {'First':>7} {'Later':>7}")
    print("-" * 48)
    for cat in ORDERED_CATS:
        print(f"{cat:<20} {call_dominant_cat[cat]:>6} "
              f"{first_call_cats[cat]:>7} "
              f"{later_call_cats[cat]:>7}")

    print("\n--- Top still-UNGROUNDED argument names ---")
    for name, cnt in still_ungrounded_names.most_common(15):
        print(f"  {name:<28} {cnt}")

    # Interpretive buckets
    if n:
        e2_fixable = arg_cats["DATE_RANGE"] + arg_cats["NUMERIC_DEFAULT"]
        undecidable = arg_cats["MULTI_HOP_ARITH"]
        fuzzy_fixable = arg_cats["PARAPHRASE"] + arg_cats["URL_DERIVED"]
        other = arg_cats["OTHER"]
        print("\n--- Interpretive buckets ---")
        print(f"  E2-fixable (contract defaults):  {e2_fixable:>5}  ({e2_fixable/n*100:.1f}%)")
        print(f"  Fuzzy-tolerance fixable:         {fuzzy_fixable:>5}  ({fuzzy_fixable/n*100:.1f}%)")
        print(f"  Fundamentally undecidable:       {undecidable:>5}  ({undecidable/n*100:.1f}%)")
        print(f"  Other:                           {other:>5}  ({other/n*100:.1f}%)")

    # --- Save ---
    result = {
        "meta": {
            "script": "benchmarks/residual_analysis.py",
            "data": "benchmarks/data/mcpatlas/cases_v2.json",
            "method": "Fast substring heuristic (no spaCy). "
                      "Outcome analysis of E1 (Deviation 22); no new deviation.",
        },
        "residual_blocked_calls": residual_calls,
        "total_calls_with_args": total_calls_with_args,
        "residual_rate": round(residual_calls / total_calls_with_args, 3)
        if total_calls_with_args else None,
        "total_ungrounded_args_after_provenance": total_ungrounded_args,
        "arg_level_categories": dict(arg_cats),
        "arg_level_shares": {
            cat: round(arg_cats[cat] / n, 3) for cat in ORDERED_CATS
        } if n else {},
        "call_level_dominant_category": dict(call_dominant_cat),
        "first_call_dominant_category": dict(first_call_cats),
        "later_call_dominant_category": dict(later_call_cats),
        "top_still_ungrounded_arg_names": still_ungrounded_names.most_common(15),
        "interpretive_buckets": {
            "e2_fixable": arg_cats["DATE_RANGE"] + arg_cats["NUMERIC_DEFAULT"],
            "fuzzy_fixable": arg_cats["PARAPHRASE"] + arg_cats["URL_DERIVED"],
            "undecidable": arg_cats["MULTI_HOP_ARITH"],
            "other": arg_cats["OTHER"],
        } if n else {},
    }

    out_path = ROOT / "benchmarks" / "residual_analysis_dev.json"
    out_path.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
