"""
E1 — AgentHallu sanity check for provenance-aware grounding (Deviation 22).

Verifies that the checker's detection on the AgentHallu confirmatory slice
(cases_eval.json) stays at or above 53% at a false-block rate of at most 15%
when no additional trajectory evidence is added (the slice has no tool outputs).

This is NOT a new run of the confirmatory analysis.  It re-reads the existing
agenthallu_confirmatory.json (checker row) and states whether H-E1-agenthallu holds.

Usage:
    python -I benchmarks/provenance_agenthallu_check.py

Writes nothing; prints only.  Development data only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    conf_path = ROOT / "benchmarks" / "agenthallu_confirmatory.json"
    if not conf_path.exists():
        sys.exit("agenthallu_confirmatory.json not found. Run analyze_agenthallu.py first.")

    data = json.loads(conf_path.read_text(encoding="utf-8"))
    # file is a dict keyed by system name; look for the context-checker entry
    checker_row = None
    for key in ("context checker", "checker", "deterministic"):
        if key in data:
            checker_row = data[key]
            break
    if checker_row is None:
        sys.exit(f"No checker row found in agenthallu_confirmatory.json. Keys: {list(data.keys())}")

    detection = checker_row.get("det") or checker_row.get("detection_rate") or checker_row.get("detection", 0)
    fbr = checker_row.get("fbr") or checker_row.get("false_block_rate") or checker_row.get("false_block", 0)

    # Convert from 0-1 or 0-100 scale
    if detection > 1.0:
        detection /= 100
    if fbr > 1.0:
        fbr /= 100

    print("=" * 55)
    print("E1 AgentHallu sanity check (Deviation 22, H-E1-agenthallu)")
    print("=" * 55)
    print(f"Checker detection   : {detection * 100:.1f}%  (threshold: >= 53%)")
    print(f"Checker false-block : {fbr * 100:.1f}%  (threshold: <= 15%)")

    detection_ok = detection >= 0.53
    fbr_ok = fbr <= 0.15

    if detection_ok and fbr_ok:
        print("H-E1-agenthallu: PASS — provenance extension does not degrade AgentHallu.")
    elif not detection_ok:
        print(f"H-E1-agenthallu: FAIL — detection {detection * 100:.1f}% < 53% threshold.")
    else:
        print(f"H-E1-agenthallu: FAIL — false-block rate {fbr * 100:.1f}% > 15% threshold.")

    print(f"\nFull checker row: {json.dumps(checker_row, indent=2)}")


if __name__ == "__main__":
    main()
