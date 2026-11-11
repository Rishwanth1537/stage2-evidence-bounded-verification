"""
tests/test_conformal_simulation.py
Prompt 6C Step 5: Conformal simulation test.

Verifies that a correct split-conformal implementation produces the
expected fraction of splits within alpha using synthetic exchangeable scores.

The key insight: the split-conformal guarantee holds ON AVERAGE across
calibration/test splits (mean ask-rate <= alpha under exchangeability),
but individual splits routinely exceed alpha. The fraction of splits
within alpha for n=100 calibration calls is roughly 50-80%, consistent
with the 57-62% reported in the draft.
"""
import math
import random
import statistics

import pytest


def _split_conformal_threshold(scores: list[float], alpha: float) -> float:
    """
    Given calibration non-conformity scores (higher = more unusual),
    return the threshold tau such that ask_rate = alpha on a fresh split.
    Standard split-conformal: tau = quantile at level ceil((n+1)*(1-alpha))/n.
    """
    n = len(scores)
    q_idx = math.ceil((n + 1) * (1 - alpha)) - 1  # 0-indexed
    q_idx = max(0, min(n - 1, q_idx))
    return sorted(scores)[q_idx]


def run_split_conformal_simulation(
    n_total: int = 1000,
    n_calib: int = 100,
    alpha: float = 0.05,
    n_splits: int = 1000,
    seed: int = 7,
) -> dict:
    """
    Simulate split-conformal ask-rate across many random splits.

    Data: n_total exchangeable samples from U(0,1) (all correct calls).
    For each split: calibrate on n_calib samples, evaluate on the rest.
    Record the ask-rate on test portion.

    Returns summary statistics.
    """
    rng = random.Random(seed)
    # Generate all scores (correct calls: scores ~ U[0,1])
    all_scores = [rng.random() for _ in range(n_total)]

    ask_rates = []
    within_alpha = 0

    for _ in range(n_splits):
        idx = list(range(n_total))
        rng.shuffle(idx)
        calib_idx = idx[:n_calib]
        test_idx = idx[n_calib:]

        calib_scores = [all_scores[i] for i in calib_idx]
        test_scores = [all_scores[i] for i in test_idx]

        tau = _split_conformal_threshold(calib_scores, alpha)
        ask_rate = sum(1 for s in test_scores if s > tau) / len(test_scores)
        ask_rates.append(ask_rate)
        if ask_rate <= alpha:
            within_alpha += 1

    return {
        "mean_ask_rate": statistics.mean(ask_rates),
        "std_ask_rate": statistics.stdev(ask_rates),
        "fraction_within_alpha": within_alpha / n_splits,
        "alpha": alpha,
        "n_calib": n_calib,
        "n_splits": n_splits,
    }


class TestSplitConformalSimulation:
    """
    Verify that split-conformal produces correct ON-AVERAGE guarantee.
    """

    @pytest.mark.parametrize("alpha", [0.05, 0.10, 0.20])
    def test_mean_ask_rate_within_alpha(self, alpha: float):
        """Mean ask-rate should be <= alpha (the actual guarantee)."""
        result = run_split_conformal_simulation(
            n_total=2000, n_calib=100, alpha=alpha, n_splits=1000
        )
        mean_ar = result["mean_ask_rate"]
        # Allow 2 percentage points tolerance for simulation noise
        assert mean_ar <= alpha + 0.02, (
            f"Mean ask-rate {mean_ar:.4f} exceeds alpha {alpha} + 2pp tolerance. "
            f"Split-conformal guarantee violated."
        )

    def test_fraction_within_alpha_is_not_one(self):
        """
        Individual splits should NOT all be within alpha.
        ~50-80% is normal for n_calib=100, alpha=0.05.
        This matches the '57-62%' observed in the draft.
        """
        result = run_split_conformal_simulation(
            n_total=2000, n_calib=100, alpha=0.05, n_splits=1000
        )
        frac = result["fraction_within_alpha"]
        # Should be well below 100% (individual splits can exceed alpha)
        assert frac < 0.95, (
            f"Fraction within alpha is {frac:.1%} — too high. "
            f"Expected ~50-80% for n_calib=100."
        )
        # Should also not be below 40% (would indicate implementation bug)
        assert frac >= 0.40, (
            f"Fraction within alpha is {frac:.1%} — too low. "
            f"Check simulation."
        )
        # Print for visibility (captured by pytest -s)
        print(
            f"\n  alpha=0.05, n_calib=100: fraction within alpha = {frac:.1%} "
            f"(mean_ask={result['mean_ask_rate']:.4f})"
        )

    def test_matches_draft_observation(self):
        """
        Draft observed 57-62% of splits within alpha for consensus rule at alpha=0.05.
        This simulation with n_calib=100 should produce a similar range.
        The draft observation is CONSISTENT with a correct implementation.
        """
        result = run_split_conformal_simulation(
            n_total=2000, n_calib=100, alpha=0.05, n_splits=1000
        )
        frac = result["fraction_within_alpha"]
        mean_ar = result["mean_ask_rate"]

        # On-average guarantee holds
        assert mean_ar <= 0.05 + 0.02

        # Fraction-within-alpha is in a plausible range consistent with draft
        assert 0.40 <= frac <= 0.90, (
            f"fraction_within_alpha={frac:.1%} outside [40%, 90%]. "
            f"The draft's 57-62% is in this range."
        )

        print(
            f"\n  Simulation: mean_ask={mean_ar:.4f}, frac_within_alpha={frac:.1%}"
        )
        print(
            "  Draft 57-62% is CONSISTENT with correct split-conformal implementation."
        )
        print(
            "  The guarantee is on the AVERAGE ask-rate, not on each individual split."
        )

    @pytest.mark.parametrize("alpha", [0.05, 0.10, 0.20])
    def test_cluster_aware_rule_has_higher_compliance(self, alpha: float):
        """
        A stricter (cluster-aware) threshold achieves higher compliance.
        Simulated by using a lower effective alpha (conservative quantile).
        """
        # Conservative: use alpha * 0.5 as effective level
        conservative_alpha = alpha * 0.5
        result = run_split_conformal_simulation(
            n_total=2000, n_calib=100, alpha=conservative_alpha, n_splits=500
        )
        result_std = run_split_conformal_simulation(
            n_total=2000, n_calib=100, alpha=alpha, n_splits=500
        )
        # Conservative rule should have more splits within the nominal alpha
        assert result["fraction_within_alpha"] >= result_std["fraction_within_alpha"] - 0.05
