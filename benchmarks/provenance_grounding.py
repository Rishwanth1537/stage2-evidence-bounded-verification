"""
E1 - Provenance-aware grounding on MCP-Atlas (Stage 3, Deviation 22).

Extends the deterministic argument checker to use:
    evidence = premise  +  all earlier tool outputs in the same trajectory

Reads cases_v2.json (built by load_mcpatlas.py), which carries the
earlier_tool_outputs list per call.  For the first call of a task the list
is empty, so the evidence is identical to the premise-only baseline.

Usage:
    python -I benchmarks/provenance_grounding.py

Writes:
    benchmarks/provenance_fbr_dev.json

Pre-registered: Deviation 22 in review/PREREGISTRATION.md (2026-11-10).
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.pipeline.arg_ground import check_arguments  # noqa: E402


MAX_OUTPUT_CHARS = 2000  # cap per earlier tool output to keep context tractable


def wilson(k: int, n: int, z: float = 1.96) -> list:
    if n == 0:
        return [None, None]
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(c - h, 3), round(c + h, 3)]


def build_provenance_context(premise: str, earlier_tool_outputs: list) -> str:
    """
    Concatenate the premise with earlier tool outputs (truncated per output).
    Earlier outputs are separated by a clear boundary so the checker can
    scan them like any other text evidence.
    """
    parts = [premise.strip()]
    for i, out in enumerate(earlier_tool_outputs):
        text = out.strip()
        if len(text) > MAX_OUTPUT_CHARS:
            text = text[:MAX_OUTPUT_CHARS]
        if text:
            parts.append(f"[Tool output {i + 1}]\n{text}")
    return "\n\n".join(parts)


def block_stats(rows: list) -> dict:
    n = len(rows)
    k = sum(r["blocked"] for r in rows)
    return {"n": n, "blocked": k,
            "rate": round(k / n, 3) if n else None,
            "wilson95": wilson(k, n)}


def main() -> None:
    data_path = ROOT / "benchmarks" / "data" / "mcpatlas" / "cases_v2.json"
    if not data_path.exists():
        sys.exit(f"cases_v2.json not found at {data_path}. Run load_mcpatlas.py first.")

    raw = json.loads(data_path.read_text(encoding="utf-8"))
    cases = raw["cases"] if isinstance(raw, dict) else raw

    rows = []
    blocked_by_new_evidence = 0  # calls unblocked by provenance that were blocked by premise-only

    for c in cases:
        call = c.get("call", {})
        args = call.get("arguments", {}) if isinstance(call, dict) else {}
        premise = c.get("premise", "") or ""
        step_index = c.get("step_index", 1)
        earlier = c.get("earlier_tool_outputs", []) or []

        # --- Premise-only verdict (baseline) ---
        verdicts_base = check_arguments(args, premise)
        blocked_base = any(v.verdict == "UNGROUNDED" for v in verdicts_base)

        # --- Provenance-aware verdict (E1 extension) ---
        evidence = build_provenance_context(premise, earlier)
        verdicts_prov = check_arguments(args, evidence)
        blocked_prov = any(v.verdict == "UNGROUNDED" for v in verdicts_prov)

        # Track arguments rescued by adding earlier tool outputs
        if blocked_base and not blocked_prov:
            blocked_by_new_evidence += 1

        rows.append({
            "id": c.get("id", ""),
            "step_index": step_index,
            "n_earlier_outputs": len(earlier),
            "n_args": len(args),
            "blocked_base": blocked_base,
            "blocked_prov": blocked_prov,
            "verdicts_base": [(v.argument, v.verdict) for v in verdicts_base],
            "verdicts_prov": [(v.argument, v.verdict) for v in verdicts_prov],
        })

    # --- Aggregate stats ---
    rows_with_args = [r for r in rows if r["n_args"] > 0]
    rows_first = [r for r in rows_with_args if r["step_index"] == 1]
    rows_later = [r for r in rows_with_args if r["step_index"] > 1]

    def stats_pair(subset: list) -> dict:
        return {
            "baseline": block_stats([{"blocked": r["blocked_base"]} for r in subset]),
            "provenance": block_stats([{"blocked": r["blocked_prov"]} for r in subset]),
        }

    # Argument-level rescue: how many UNGROUNDED args became GROUNDED
    args_rescued = 0
    args_ungrounded_base = 0
    for r in rows_with_args:
        base_map = dict(r["verdicts_base"])
        prov_map = dict(r["verdicts_prov"])
        for arg, verdict in base_map.items():
            if verdict == "UNGROUNDED":
                args_ungrounded_base += 1
                if prov_map.get(arg) == "GROUNDED":
                    args_rescued += 1

    # Top argument names rescued
    rescue_by_name: Counter = Counter()
    for r in rows_with_args:
        base_map = dict(r["verdicts_base"])
        prov_map = dict(r["verdicts_prov"])
        for arg, verdict in base_map.items():
            if verdict == "UNGROUNDED" and prov_map.get(arg) == "GROUNDED":
                rescue_by_name[arg] += 1

    # Argument-level verdicts (provenance)
    all_verdict_counts: Counter = Counter()
    for r in rows_with_args:
        for _, v in r["verdicts_prov"]:
            all_verdict_counts[v] += 1

    result = {
        "meta": {
            "script": "benchmarks/provenance_grounding.py",
            "data": "benchmarks/data/mcpatlas/cases_v2.json",
            "max_output_chars_per_turn": MAX_OUTPUT_CHARS,
            "deviation": 22,
        },
        "n_calls_total": len(rows),
        "n_calls_with_args": len(rows_with_args),
        "calls_rescued_at_call_level": blocked_by_new_evidence,
        "args_ungrounded_baseline": args_ungrounded_base,
        "args_rescued": args_rescued,
        "rescue_pct": round(args_rescued / args_ungrounded_base * 100, 1) if args_ungrounded_base else None,
        "top_rescued_argument_names": rescue_by_name.most_common(15),
        "argument_verdicts_provenance": dict(all_verdict_counts),
        "all_calls_with_args": stats_pair(rows_with_args),
        "first_call_of_task": stats_pair(rows_first),
        "later_calls": stats_pair(rows_later),
    }

    out_path = ROOT / "benchmarks" / "provenance_fbr_dev.json"
    out_path.write_text(json.dumps(result, indent=1), encoding="utf-8")

    # --- Print summary ---
    def pct(d):
        r = d.get("rate")
        return f"{r * 100:.1f}%" if r is not None else "N/A"

    def ci(d):
        w = d.get("wilson95", [None, None])
        if w[0] is None:
            return ""
        return f" [{w[0] * 100:.1f}, {w[1] * 100:.1f}]"

    print("=" * 60)
    print("E1 Provenance-aware grounding — MCP-Atlas (Deviation 22)")
    print(f"Cases (with args): {len(rows_with_args)}  |  "
          f"First-call: {len(rows_first)}  |  Later: {len(rows_later)}")
    print("=" * 60)
    print(f"{'Slice':<22} {'Baseline':>10} {'Provenance':>12} {'Delta':>8}")
    print("-" * 60)
    for label, subset in [("All (with args)", rows_with_args),
                           ("First call of task", rows_first),
                           ("Later calls", rows_later)]:
        b = block_stats([{"blocked": r["blocked_base"]} for r in subset])
        p = block_stats([{"blocked": r["blocked_prov"]} for r in subset])
        rb = b["rate"] or 0
        rp = p["rate"] or 0
        delta = rp - rb
        print(f"{label:<22} {pct(b):>10}{ci(b)}  {pct(p):>10}{ci(p)}  {delta * 100:>+7.1f}pp")
    print("-" * 60)
    print(f"Calls rescued at call level: {blocked_by_new_evidence} / "
          f"{sum(r['blocked_base'] for r in rows_with_args)}")
    print(f"Args rescued: {args_rescued} / {args_ungrounded_base} "
          f"({result['rescue_pct']}%)")
    print(f"Top rescued args: {rescue_by_name.most_common(8)}")
    print(f"Wrote {out_path}")
    print()

    # Kill rule check
    prov_rate = result["all_calls_with_args"]["provenance"]["rate"] or 1.0
    if prov_rate > 0.50:
        print(f"[KILL RULE] Block rate {prov_rate * 100:.1f}% > 50% after provenance — "
              "E1 is a negative result; do not pursue further without protocol change.")
    elif prov_rate <= 0.30:
        print(f"[H-E1-block PASS] Block rate {prov_rate * 100:.1f}% <= 30% target.")
    else:
        print(f"[H-E1-block PARTIAL] Block rate {prov_rate * 100:.1f}% — "
              "between 30% and 50%; improvement but hypothesis not fully met.")


if __name__ == "__main__":
    main()
