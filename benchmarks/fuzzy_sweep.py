"""
E3-soft — Fuzzy tolerance threshold sweep on MCP-Atlas (Deviation 24).

The residual analysis (section 25) shows 32.5% of remaining UNGROUNDED args
after provenance are PARAPHRASE — multi-word strings present in the conversation
in a paraphrased form.  The checker already uses difflib fuzzy matching at
threshold FUZZY=0.88.  This experiment asks:

    Does lowering the matching threshold rescue a meaningful share of PARAPHRASE
    residual without inflating false blocks on correct calls beyond tolerance?

Matching metric: unigram token recall — fraction of value tokens present in the
evidence token set.  O(n+m) per arg; identical to token-set containment at
recall=1.0.  SequenceMatcher is not used here because a small number of
pathological `code` args (embedded JSON blobs, >80 tokens) make it hang.
Token recall is a looser but stable proxy: it measures whether the words of
the value appear anywhere in evidence, without requiring order.

Pre-registered: Deviation 24 in review/PREREGISTRATION.md (2026-11-10).
Outputs: benchmarks/fuzzy_sweep_dev.json
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmarks.provenance_grounding import build_provenance_context  # noqa: E402
from server.pipeline.arg_ground import _norm_text, _check_iso, _check_currency  # noqa: E402


THRESHOLDS = [0.88, 0.82, 0.76, 0.70, 0.65]


def token_recall(value_norm: str, context_norm: str) -> float:
    """
    Fraction of value tokens that appear in the context token set.
    Returns 1.0 for substring match (fast path) and for empty value.
    O(len(value_tokens) + len(context_tokens)).
    """
    if not value_norm:
        return 1.0
    if value_norm in context_norm:
        return 1.0
    vt = value_norm.split()
    if not vt:
        return 1.0
    ct_set = set(context_norm.split())
    hits = sum(1 for t in vt if t in ct_set)
    return hits / len(vt)


def score_arg(arg: str, value: str, context: str) -> float:
    """
    Returns token-recall score for a string arg (0–1).
    1.0 = grounded; < threshold = blocked.
    Special typed handlers (ISO date, currency) used before string path.
    """
    if not value.strip():
        return 1.0  # UNCHECKABLE
    iso = _check_iso(arg, value, context)
    if iso is not None:
        return 1.0 if iso.verdict == "GROUNDED" else 0.0
    curr = _check_currency(arg, value, context)
    if curr is not None:
        return 1.0 if curr.verdict == "GROUNDED" else 0.0
    # Purely numeric string
    if re.fullmatch(r"\s*[\d,]+(?:\.\d+)?\s*", value):
        return 1.0  # let the numeric path handle it; not counted here
    vn, cn = _norm_text(value), _norm_text(context)
    return token_recall(vn, cn)


def wilson(k: int, n: int, z: float = 1.96) -> list:
    if n == 0:
        return [None, None]
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(c - h, 3), round(c + h, 3)]


def main() -> None:
    data_path = ROOT / "benchmarks" / "data" / "mcpatlas" / "cases_v2.json"
    if not data_path.exists():
        sys.exit(f"cases_v2.json not found at {data_path}")

    raw = json.loads(data_path.read_text(encoding="utf-8"))
    cases = raw["cases"] if isinstance(raw, dict) else raw

    # Per-call: minimum token-recall score across all string args
    call_scores: list[float] = []
    n_calls = 0

    for c in cases:
        call = c.get("call", {})
        args = call.get("arguments", {}) if isinstance(call, dict) else {}
        if not args:
            continue
        premise = c.get("premise", "") or ""
        earlier = c.get("earlier_tool_outputs", []) or []
        evidence = build_provenance_context(premise, earlier)

        str_args = {
            k: str(v) for k, v in args.items()
            if isinstance(v, str) and str(v).strip() and not isinstance(v, bool)
        }
        if not str_args:
            continue

        n_calls += 1
        min_score = min(score_arg(k, v, evidence) for k, v in str_args.items())
        call_scores.append(min_score)

    baseline_blocked = sum(1 for s in call_scores if s < 0.88)

    print("=" * 72)
    print("E3-soft: Token-recall threshold sweep on MCP-Atlas (Deviation 24)")
    print(f"Metric: unigram token recall (O(n+m), no SequenceMatcher)")
    print(f"Calls with string args: {n_calls}")
    print(f"Baseline blocked at thr=0.88: {baseline_blocked} ({baseline_blocked/n_calls*100:.1f}%)")
    print("=" * 72)
    print(f"{'Threshold':<12} {'Blocked':>8} {'FBR':>8}  {'95% CI'}  {'Rescued vs 0.88'}")
    print("-" * 72)

    rows = []
    for thr in THRESHOLDS:
        k = sum(1 for s in call_scores if s < thr)
        n = n_calls
        rate = k / n if n else 0
        ci = wilson(k, n)
        rescued = baseline_blocked - k
        pct = rescued / baseline_blocked * 100 if baseline_blocked else 0
        print(f"  {thr:<10} {k:>8} {rate*100:>7.1f}%  "
              f"[{ci[0]*100:.1f}, {ci[1]*100:.1f}]  "
              f"rescued {rescued:+d} ({pct:.1f}% of blocked@0.88)")
        rows.append({
            "threshold": thr,
            "blocked": k,
            "fbr": round(rate, 3),
            "wilson95": ci,
            "rescued_vs_0_88": rescued,
            "pct_rescued_of_baseline_blocked": round(pct, 1),
        })

    result = {
        "meta": {
            "script": "benchmarks/fuzzy_sweep.py",
            "data": "benchmarks/data/mcpatlas/cases_v2.json",
            "method": "Unigram token recall (fraction of value tokens in evidence token set). "
                      "String args only; numeric/bool excluded. "
                      "Provenance evidence (premise + earlier tool outputs). "
                      "ISO date and currency special handlers applied first.",
            "deviation": 24,
            "caveat": "Token recall is a looser proxy than difflib fuzzy ratio — it ignores "
                      "token order. It correctly captures the PARAPHRASE bucket (words present "
                      "but reordered/rephrased) but may over-credit cases where a few unrelated "
                      "tokens coincidentally match. FBR on confirmed-correct calls only cannot "
                      "be measured without labels on this split.",
        },
        "n_calls_with_string_args": n_calls,
        "baseline_blocked_at_0_88": baseline_blocked,
        "baseline_fbr": round(baseline_blocked / n_calls, 3) if n_calls else None,
        "thresholds": rows,
    }

    out_path = ROOT / "benchmarks" / "fuzzy_sweep_dev.json"
    out_path.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(f"\nWrote {out_path}")

    # Hypothesis check
    print("\n--- H-E3soft outcome ---")
    for thr in [0.76, 0.70]:
        k = sum(1 for s in call_scores if s < thr)
        rescue_pp = (baseline_blocked - k) / n_calls * 100
        base_pp = baseline_blocked / n_calls * 100
        kill = rescue_pp < 2.0
        print(f"  thr={thr}: rescue {rescue_pp:.1f}pp below baseline {base_pp:.1f}% — "
              f"kill rule (< 2pp): {'KILL' if kill else 'PASS'}")
    print(f"\n  H-E3soft: at thr=0.76 rescue={rows[2]['rescued_vs_0_88']} calls "
          f"({rows[2]['pct_rescued_of_baseline_blocked']}% of baseline blocked) — "
          f"{'PASS (>= 5pp)' if rows[2]['rescued_vs_0_88']/n_calls*100 >= 5 else 'PARTIAL (< 5pp)'}")


if __name__ == "__main__":
    main()
