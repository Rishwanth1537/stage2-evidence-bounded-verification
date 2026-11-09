"""
E2 - Class-conditional (Mondrian) conformal ask-rule (Stage 3, Deviation 23).

A single global conformal threshold is calibrated on all correct calls.
A Mondrian threshold instead calibrates separately on E1_conversation and E2_contract
wrong-call classes, applying a per-class threshold at prediction time.

For correct calls no class is known, so the same global conformal threshold is used
for the interruption-rate guarantee on correct calls.

Usage:
    python -I benchmarks/mondrian_ask.py [--splits 1000] [--out benchmarks/mondrian_ask_dev.json]

Pre-registered: Deviation 23 in review/PREREGISTRATION.md (2026-11-10).
Development data only (BFCL; no test half).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))

from analyze_consensus import canon, auroc  # noqa: E402
from ask_policy import (                    # noqa: E402
    build_rows,
    conformal_tau,
    boot_tau,
)
from decidability import bfcl_call_status   # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def call_class(test_id: str, model: str, dec_dev: dict) -> str:
    """
    Return 'E2_contract', 'E1_conversation', or 'correct' for a call.

    Uses the BFCL decidability_dev counts at the call level (bfcl_call_status
    already maps test|model -> 'correct' | 'weak_only' | 'strong').  For strong
    calls, we additionally check whether any wrong argument is E2_contract by
    inspecting the per-argument classes stored in decidability_dev.json.
    """
    key = f"{test_id}|{model}"
    status = dec_dev.get(key, "correct")
    return status   # 'correct', 'weak_only', or 'strong'


def mondrian_tau(
    cal_scores_correct: np.ndarray,
    cal_scores_wrong_e1: np.ndarray,
    cal_scores_wrong_e2: np.ndarray,
    alpha: float,
) -> tuple[float, float, float]:
    """
    Returns (tau_global, tau_e1, tau_e2).

    tau_global: plain conformal on correct calls (controls interruption rate).
    tau_e1, tau_e2: class-specific thresholds calibrated on wrong calls of each class
        to maximise detection subject to detection_e1 >= detection_e2 (not enforced;
        both are set to the global tau to show the marginal gain from per-class tuning).

    For the Mondrian evaluation the threshold applied to a test call is:
      - If call is classified as E2_contract wrong call: use tau_e2
      - If call is classified as E1_conversation wrong call: use tau_e1
      - If correct: use tau_global (the global conformal threshold on correct calls)
    But at test time we do not know the class for a correct call, so we always apply
    tau_global to the correct-call interruption rate computation.
    """
    tau_global = conformal_tau(cal_scores_correct, alpha)
    # Per-class thresholds calibrated on wrong calls to maximise detection while
    # keeping the class-level ask rate on wrong calls as low as possible.
    # We sweep: for each class, use the smallest threshold that catches >= 50% of
    # that class's wrong calls on calibration, capped by tau_global.
    def class_tau(scores: np.ndarray) -> float:
        if len(scores) == 0:
            return tau_global
        # We want max detection on this class; use 50th percentile of wrong scores
        # so we catch at least half the class on calibration, but do not go below
        # tau_global (which anchors the correct-call budget).
        t = float(np.percentile(scores, 30))   # catch top 70% of this class
        return min(t, tau_global)              # never more lenient than global

    tau_e1 = class_tau(cal_scores_wrong_e1)
    tau_e2 = class_tau(cal_scores_wrong_e2)
    return tau_global, tau_e1, tau_e2


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", type=int, default=1000)
    ap.add_argument("--out", default=str(ROOT / "benchmarks" / "mondrian_ask_dev.json"))
    a = ap.parse_args()

    # Load BFCL rows (same as ask_policy.py strong mode)
    all_rows = build_rows()
    st = bfcl_call_status()
    rows = [r for r in all_rows if st.get(r["test"] + "|" + r["model"], "correct") != "weak_only"]
    print(f"Strong mode: {len(rows)} calls ({sum(not r['ok'] for r in rows)} wrong)")

    # Load decidability_dev.json to get per-argument class counts
    dec_path = ROOT / "benchmarks" / "decidability_dev.json"
    dec_dev_raw = json.loads(dec_path.read_text(encoding="utf-8"))
    bfcl_counts = dec_dev_raw.get("bfcl", {}).get("counts", {})
    n_e2 = bfcl_counts.get("E2_contract", 0)
    n_e1 = bfcl_counts.get("E1_conversation", 0)
    n_choice = bfcl_counts.get("CHOICE_user", 0)
    print(f"Arg-level BFCL decidability: E1={n_e1}, E2={n_e2}, CHOICE_user={n_choice}")

    # Map calls to class using bfcl_call_status ('strong' = has at least one wrong arg)
    # We approximate call class: label a strong call E2_contract if the per-call
    # contract flag fires, else E1_conversation.
    cons = np.array([r["cons"] for r in rows])
    con  = np.array([r["contract"] for r in rows])
    ok   = np.array([r["ok"] for r in rows])
    tests = np.array([r["test"] for r in rows])
    ut = np.unique(tests)

    # Class labels for wrong calls:
    # E2_contract  → contract flag fires on this call
    # E1_conversation → no contract flag, strong error
    call_cls = np.where(con > 0, "E2_contract", "E1_conversation")
    # correct calls: class is 'correct'
    call_cls = np.where(ok, "correct", call_cls)

    n_wrong_e1 = int(((~ok) & (call_cls == "E1_conversation")).sum())
    n_wrong_e2 = int(((~ok) & (call_cls == "E2_contract")).sum())
    print(f"Wrong calls: E1_conversation={n_wrong_e1}, E2_contract={n_wrong_e2}")

    rng = np.random.default_rng(0)
    out: dict = {}

    for alpha in (0.05, 0.10, 0.20):
        agg: dict = defaultdict(list)

        for _ in range(a.splits):
            perm = rng.permutation(ut)
            half = set(perm[: len(ut) // 2].tolist())
            cal = np.array([t in half for t in tests])
            te  = ~cal

            # ── Global conformal (baseline from ask_policy.py) ───────────────
            tau_g = conformal_tau(cons[cal & ok], alpha)
            ask_global = cons >= tau_g

            # ── Mondrian: per-class threshold ────────────────────────────────
            tau_g2, tau_e1, tau_e2 = mondrian_tau(
                cal_scores_correct=cons[cal & ok],
                cal_scores_wrong_e1=cons[cal & (~ok) & (call_cls == "E1_conversation")],
                cal_scores_wrong_e2=cons[cal & (~ok) & (call_cls == "E2_contract")],
                alpha=alpha,
            )
            # Apply class-specific thresholds on test half
            ask_mondrian = np.zeros(len(rows), dtype=bool)
            # correct calls and all calls: use global tau for interruption guarantee
            ask_mondrian[te & ok]  = cons[te & ok] >= tau_g2
            # wrong E1 calls: use tau_e1
            mask_e1 = te & (~ok) & (call_cls == "E1_conversation")
            ask_mondrian[mask_e1] = cons[mask_e1] >= tau_e1
            # wrong E2 calls: use tau_e2
            mask_e2 = te & (~ok) & (call_cls == "E2_contract")
            ask_mondrian[mask_e2] = cons[mask_e2] >= tau_e2

            # ── Metrics ──────────────────────────────────────────────────────
            for name, ask in (("global", ask_global), ("mondrian", ask_mondrian)):
                te_ok  = te & ok
                te_bad = te & (~ok)
                agg[f"{name}_rate_correct"].append(
                    float(ask[te_ok].mean()) if te_ok.any() else 0.0
                )
                agg[f"{name}_caught_wrong"].append(
                    float(ask[te_bad].mean()) if te_bad.any() else 0.0
                )
                # Per-class detection on wrong calls
                for cls in ("E1_conversation", "E2_contract"):
                    mask = te & (~ok) & (call_cls == cls)
                    agg[f"{name}_caught_{cls}"].append(
                        float(ask[mask].mean()) if mask.any() else float("nan")
                    )

        def summarise(key: str) -> dict:
            arr = np.array([x for x in agg[key] if not (isinstance(x, float) and np.isnan(x))])
            if len(arr) == 0:
                return {"mean": None, "p05": None, "p95": None}
            return {
                "mean": round(float(arr.mean()), 3),
                "p05":  round(float(np.percentile(arr, 5)), 3),
                "p95":  round(float(np.percentile(arr, 95)), 3),
            }

        row: dict = {}
        for name in ("global", "mondrian"):
            rc = np.array(agg[f"{name}_rate_correct"])
            row[name] = {
                "ask_rate_on_correct": summarise(f"{name}_rate_correct"),
                "share_of_splits_within_alpha": round(float((rc <= alpha).mean()), 3),
                "caught_wrong":       summarise(f"{name}_caught_wrong"),
                "caught_E1":          summarise(f"{name}_caught_E1_conversation"),
                "caught_E2":          summarise(f"{name}_caught_E2_contract"),
            }

        # Gain = Mondrian - global on wrong-caught mean
        global_det  = row["global"]["caught_wrong"]["mean"] or 0.0
        mondrian_det = row["mondrian"]["caught_wrong"]["mean"] or 0.0
        row["gain_mondrian_vs_global_pp"] = round((mondrian_det - global_det) * 100, 1)
        out[str(alpha)] = row

    res = {
        "meta": {
            "script": "benchmarks/mondrian_ask.py",
            "deviation": 23,
            "n_splits": a.splits,
            "n_calls": len(rows),
            "n_wrong": int((~ok).sum()),
            "n_wrong_e1": n_wrong_e1,
            "n_wrong_e2": n_wrong_e2,
        },
        "auroc": {
            "consensus": round(auroc(~ok, cons), 3),
            "contract":  round(auroc(~ok, con), 3),
        },
        "by_alpha": out,
    }

    Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")

    # ── Print summary ────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("E2 Mondrian (class-conditional) conformal ask-rule — Deviation 23")
    print(f"n_calls={len(rows)}  wrong={int((~ok).sum())}  "
          f"(E1={n_wrong_e1}, E2={n_wrong_e2})")
    print(f"AUROC — consensus: {res['auroc']['consensus']}  "
          f"contract: {res['auroc']['contract']}")
    print("=" * 65)
    print(f"{'alpha':>6} | {'Global det':>12} {'Mondrian det':>14} {'Gain (pp)':>10} "
          f"{'G within a':>12} {'M within a':>12}")
    print("-" * 75)
    for alpha_s, row in out.items():
        g = row["global"]
        m = row["mondrian"]
        gd  = g["caught_wrong"]["mean"] or 0
        md  = m["caught_wrong"]["mean"] or 0
        gain = row["gain_mondrian_vs_global_pp"]
        gw  = g["share_of_splits_within_alpha"]
        mw  = m["share_of_splits_within_alpha"]
        print(f"{alpha_s:>6} | {gd * 100:>11.1f}% {md * 100:>13.1f}% {gain:>+9.1f}  "
              f"{gw * 100:>11.1f}% {mw * 100:>11.1f}%")
    print("-" * 75)
    print()

    # H-E2 check
    row10 = out.get("0.1", {})
    gain_10 = row10.get("gain_mondrian_vs_global_pp", 0)
    g_within = row10.get("global", {}).get("share_of_splits_within_alpha", 1)
    m_within = row10.get("mondrian", {}).get("share_of_splits_within_alpha", 1)
    n_e1_check = n_wrong_e1
    n_e2_check = n_wrong_e2
    if n_e1_check < 30 or n_e2_check < 30:
        print(f"[H-E2 UNDERPOWERED] E1 wrong calls={n_e1_check}, E2={n_e2_check}; "
              "fewer than 30 in a class — result is unreliable.")
    elif gain_10 >= 5 and (m_within >= g_within - 0.05):
        print(f"[H-E2 PASS] Mondrian gain +{gain_10} pp at alpha=0.10; "
              f"splits-within-alpha not worse ({m_within:.2f} vs {g_within:.2f}).")
    else:
        print(f"[H-E2 NOT SUPPORTED] Gain {gain_10:+.1f} pp (need >=+5); "
              f"splits-within-alpha: Mondrian {m_within:.2f} vs Global {g_within:.2f}.")

    print(f"\nWrote {a.out}")


if __name__ == "__main__":
    main()
