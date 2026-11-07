"""
Unit tests for benchmarks/stats.py and benchmarks/report_table.py.

Verifies:
- Wilson score interval for 18/31 against both statsmodels and hand formula.
- Wilson boundary cases (0/10 and 10/10).
- Clopper-Pearson against exact scipy beta quantiles.
- McNemar exact against scipy.stats.binomtest.
- One-item-per-cluster bootstrap matches standard i.i.d. bootstrap at fixed seed.
- Metrics (detection_rate, false_block_rate, interruption_rate, hard_block_rate, youden_j, auroc_with_ci).
- Power simulation (required_positives_for_detection_gap).
"""
from __future__ import annotations

import math
import numpy as np
import pytest
import scipy.stats as st

from benchmarks.report_table import build_report_table
from benchmarks.results_io import ResultRow
from benchmarks.stats import (
    auroc_with_ci,
    clopper_pearson_ci,
    cluster_bootstrap_ci,
    detection_rate,
    false_block_rate,
    hard_block_rate,
    interruption_rate,
    mcnemar_exact,
    paired_cluster_bootstrap_diff,
    required_positives_for_detection_gap,
    wilson_ci,
    youden_j,
)


def _wilson_hand_formula(k: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Independent manual hand-formula implementation of the Wilson score interval."""
    alpha = 1.0 - confidence
    z = st.norm.ppf(1.0 - alpha / 2.0)
    p = k / n
    denom = 1.0 + (z**2) / n
    center = (p + (z**2) / (2.0 * n)) / denom
    margin = (z / denom) * math.sqrt(p * (1.0 - p) / n + (z**2) / (4.0 * (n**2)))
    return max(0.0, center - margin), min(1.0, center + margin)


def test_wilson_ci_18_31_matches_hand_and_statsmodels():
    """
    Wilson 18/31 at 95% is approximately [0.41, 0.74].
    Confirm against an independent computation (both statsmodels and hand formula).
    """
    k, n = 18, 31
    low, high = wilson_ci(k, n, confidence=0.95)

    # 1. Check approximate range [0.41, 0.74]
    assert 0.40 < low < 0.42, f"Expected low ~ 0.41, got {low}"
    assert 0.73 < high < 0.75, f"Expected high ~ 0.74, got {high}"

    # 2. Compare against hand formula
    hand_low, hand_high = _wilson_hand_formula(k, n, confidence=0.95)
    assert math.isclose(low, hand_low, rel_tol=1e-12)
    assert math.isclose(high, hand_high, rel_tol=1e-12)

    # 3. Compare against statsmodels
    try:
        from statsmodels.stats.proportion import proportion_confint
        sm_low, sm_high = proportion_confint(k, n, alpha=0.05, method="wilson")
        assert math.isclose(low, sm_low, rel_tol=1e-7)
        assert math.isclose(high, sm_high, rel_tol=1e-7)
    except ImportError:
        pass


def test_wilson_ci_boundaries():
    """Wilson boundary cases: 0/10 and 10/10."""
    # 0/10
    low_0, high_0 = wilson_ci(0, 10, confidence=0.95)
    assert low_0 == 0.0
    assert 0.27 < high_0 < 0.29

    # 10/10
    low_10, high_10 = wilson_ci(10, 10, confidence=0.95)
    assert 0.71 < low_10 < 0.73
    assert high_10 == 1.0


def test_clopper_pearson_against_scipy_beta_quantiles():
    """Clopper-Pearson matches exact scipy beta quantiles."""
    test_cases = [(0, 10), (10, 10), (18, 31), (5, 20)]
    alpha = 0.05

    for k, n in test_cases:
        low, high = clopper_pearson_ci(k, n, confidence=1.0 - alpha)
        if k == 0:
            exp_low = 0.0
            exp_high = float(st.beta.ppf(1.0 - alpha / 2.0, 1, n))
        elif k == n:
            exp_low = float(st.beta.ppf(alpha / 2.0, n, 1))
            exp_high = 1.0
        else:
            exp_low = float(st.beta.ppf(alpha / 2.0, k, n - k + 1))
            exp_high = float(st.beta.ppf(1.0 - alpha / 2.0, k + 1, n - k))

        assert math.isclose(low, exp_low, rel_tol=1e-9)
        assert math.isclose(high, exp_high, rel_tol=1e-9)


def test_mcnemar_exact_against_scipy_binomtest():
    """McNemar exact p-value matches scipy.stats.binomtest on discordant pairs."""
    discordant_pairs = [(13, 27), (0, 5), (10, 10), (1, 15), (0, 0)]
    for b, c in discordant_pairs:
        p_val = mcnemar_exact(b, c)
        if b + c == 0:
            assert p_val == 1.0
        else:
            exp_p = float(st.binomtest(b, n=b + c, p=0.5, alternative="two-sided").pvalue)
            assert math.isclose(p_val, exp_p, rel_tol=1e-9)


def test_one_item_per_cluster_matches_iid_bootstrap():
    """
    When every item belongs to its own unique cluster (1 item per cluster),
    cluster bootstrap must match the iid bootstrap at a fixed random seed.
    """
    n_items = 25
    # Create rows where each row has a unique cluster_id
    rows = [
        {"cluster_id": f"c_{i}", "val": (1 if i % 3 == 0 else 0)}
        for i in range(n_items)
    ]

    def _mean_metric(batch: list[dict]) -> float:
        return sum(x["val"] for x in batch) / len(batch)

    seed = 123
    B = 2000

    # Cluster bootstrap
    _, cl_low, cl_high = cluster_bootstrap_ci(
        rows, _mean_metric, cluster_key="cluster_id", B=B, seed=seed
    )

    # Direct i.i.d. bootstrap using identical RNG stream
    rng = np.random.default_rng(seed)
    n = len(rows)
    iid_boots = np.empty(B, dtype=float)
    for b in range(B):
        idx = rng.choice(n, size=n, replace=True)
        sample = [rows[i] for i in idx]
        iid_boots[b] = _mean_metric(sample)

    iid_low = float(np.percentile(iid_boots, 2.5))
    iid_high = float(np.percentile(iid_boots, 97.5))

    assert math.isclose(cl_low, iid_low, abs_tol=1e-9)
    assert math.isclose(cl_high, iid_high, abs_tol=1e-9)


def test_metrics_legacy_vs_new_semantics():
    """
    Test detection_rate, false_block_rate, interruption_rate, hard_block_rate, and youden_j
    under legacy (BLOCK only) vs new (ASK or BLOCK) semantics.
    """
    sample_rows = [
        # Erroneous calls (label=1)
        ResultRow(run_id="r", dataset="d", split="dev", item_id="p1", cluster_id="c1", label=1, system="s", decision="BLOCK", latency_ms=1.0),
        ResultRow(run_id="r", dataset="d", split="dev", item_id="p2", cluster_id="c1", label=1, system="s", decision="ASK", latency_ms=1.0),
        ResultRow(run_id="r", dataset="d", split="dev", item_id="p3", cluster_id="c2", label=1, system="s", decision="ALLOW", latency_ms=1.0),
        ResultRow(run_id="r", dataset="d", split="dev", item_id="p4", cluster_id="c2", label=1, system="s", decision="WARN", latency_ms=1.0),
        # Clean calls (label=0)
        ResultRow(run_id="r", dataset="d", split="dev", item_id="n1", cluster_id="c3", label=0, system="s", decision="ALLOW", latency_ms=1.0),
        ResultRow(run_id="r", dataset="d", split="dev", item_id="n2", cluster_id="c3", label=0, system="s", decision="ASK", latency_ms=1.0),
        ResultRow(run_id="r", dataset="d", split="dev", item_id="n3", cluster_id="c4", label=0, system="s", decision="BLOCK", latency_ms=1.0),
        ResultRow(run_id="r", dataset="d", split="dev", item_id="n4", cluster_id="c4", label=0, system="s", decision="ALLOW", latency_ms=1.0),
    ]

    # Legacy detection: only BLOCK detects -> 1 / 4 = 0.25
    det_leg, _, _ = detection_rate(sample_rows, legacy_semantics=True, ci_method="wilson")
    assert math.isclose(det_leg, 0.25)

    # New detection: ASK or BLOCK detects -> 2 / 4 = 0.50
    det_new, _, _ = detection_rate(sample_rows, legacy_semantics=False, ci_method="wilson")
    assert math.isclose(det_new, 0.50)

    # Hard-block rate on clean calls: BLOCK only -> 1 / 4 = 0.25
    hb, _, _ = hard_block_rate(sample_rows, ci_method="wilson")
    assert math.isclose(hb, 0.25)

    # Interruption rate on clean calls: ASK or BLOCK -> 2 / 4 = 0.50
    ir, _, _ = interruption_rate(sample_rows, ci_method="wilson")
    assert math.isclose(ir, 0.50)

    # Youden J legacy: 0.25 - 0.25 = 0.0
    j_leg, _, _ = youden_j(sample_rows, legacy_semantics=True, B=200, seed=42)
    assert math.isclose(j_leg, 0.0)

    # Youden J new: 0.50 - 0.50 = 0.0
    j_new, _, _ = youden_j(sample_rows, legacy_semantics=False, B=200, seed=42)
    assert math.isclose(j_new, 0.0)


def test_auroc_with_ci():
    """Verify AUROC on clean separable scores."""
    rows = [
        ResultRow(run_id="r", dataset="d", split="dev", item_id="1", cluster_id="c1", label=1, system="s", score=0.9),
        ResultRow(run_id="r", dataset="d", split="dev", item_id="2", cluster_id="c1", label=1, system="s", score=0.8),
        ResultRow(run_id="r", dataset="d", split="dev", item_id="3", cluster_id="c2", label=0, system="s", score=0.2),
        ResultRow(run_id="r", dataset="d", split="dev", item_id="4", cluster_id="c2", label=0, system="s", score=0.1),
    ]
    auc, low, high = auroc_with_ci(rows, B=500, seed=42)
    assert math.isclose(auc, 1.0)
    assert low > 0.0


def test_required_positives_power_simulation():
    """Verify power simulation returns reasonable sample size."""
    n_req = required_positives_for_detection_gap(
        p_a=0.70, p_b=0.40, correlation=0.20, power=0.80, alpha=0.05, seed=42
    )
    # A gap of 0.30 is large; sample size should be moderate (typically < 150)
    assert 20 <= n_req <= 200, f"Expected reasonable sample size, got {n_req}"


def test_build_report_table():
    """Verify markdown report table generation."""
    rows = [
        ResultRow(run_id="r", dataset="d", split="dev", item_id="p1", cluster_id="c1", label=1, system="ModelA", decision="BLOCK", latency_ms=10.0, tokens_in=50, tokens_out=10),
        ResultRow(run_id="r", dataset="d", split="dev", item_id="n1", cluster_id="c2", label=0, system="ModelA", decision="ALLOW", latency_ms=12.0, tokens_in=50, tokens_out=10),
    ]
    md = build_report_table(rows)
    assert "| System | n_pos | n_neg |" in md
    assert "ModelA" in md
