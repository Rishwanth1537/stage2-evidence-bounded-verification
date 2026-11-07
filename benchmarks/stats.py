"""
Rigorous statistical methods for hallucination checker evaluations.

Follows Stage 2 Prompt 3 specification:
- Confidence intervals: Wilson score interval, Clopper-Pearson exact interval.
- Resampling: Cluster bootstrap percentile interval (resampling clusters of items).
- Hypothesis testing: McNemar exact test via scipy.stats.binomtest.
- Comparative bootstrap: Paired cluster bootstrap difference with percentile intervals.
- Evaluation metrics: Detection rate, False-block rate, Interruption rate, Hard-block rate,
  Youden's J statistic, and AUROC with bootstrap intervals.
- Power simulation: required_positives_for_detection_gap for paired detector comparisons.

Dependencies: numpy and scipy only.
"""
from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import scipy.stats as st


def wilson_ci(k: int, n: int, confidence: float = 0.95) -> Tuple[float, float]:
    """
    Wilson score confidence interval for a binomial proportion without continuity correction.

    Matches the standard formulation:
        center = (p_hat + z^2 / (2n)) / (1 + z^2 / n)
        margin = (z / (1 + z^2 / n)) * sqrt(p_hat * (1 - p_hat) / n + z^2 / (4n^2))

    Args:
        k: Number of successes / positives.
        n: Total number of trials.
        confidence: Confidence level (default 0.95).

    Returns:
        (ci_lower, ci_upper) bounded in [0.0, 1.0].
    """
    if n <= 0:
        return 0.0, 1.0
    if k < 0 or k > n:
        raise ValueError(f"k must be in range [0, n], got k={k}, n={n}")

    alpha = 1.0 - confidence
    z = float(st.norm.ppf(1.0 - alpha / 2.0))
    z2 = z * z
    p = float(k) / float(n)

    denom = 1.0 + z2 / float(n)
    center = (p + z2 / (2.0 * float(n))) / denom
    radicand = (p * (1.0 - p) / float(n)) + (z2 / (4.0 * float(n) * float(n)))
    margin = (z / denom) * math.sqrt(max(0.0, radicand))

    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    if k == 0:
        lower = 0.0
    if k == n:
        upper = 1.0
    return lower, upper


def clopper_pearson_ci(k: int, n: int, confidence: float = 0.95) -> Tuple[float, float]:
    """
    Exact Clopper-Pearson confidence interval for a binomial proportion using Beta quantiles.

    Args:
        k: Number of successes / positives.
        n: Total number of trials.
        confidence: Confidence level (default 0.95).

    Returns:
        (ci_lower, ci_upper) bounded in [0.0, 1.0].
    """
    if n <= 0:
        return 0.0, 1.0
    if k < 0 or k > n:
        raise ValueError(f"k must be in range [0, n], got k={k}, n={n}")

    alpha = 1.0 - confidence

    if k == 0:
        lower = 0.0
        upper = float(st.beta.ppf(1.0 - alpha / 2.0, 1, n))
    elif k == n:
        lower = float(st.beta.ppf(alpha / 2.0, n, 1))
        upper = 1.0
    else:
        lower = float(st.beta.ppf(alpha / 2.0, k, n - k + 1))
        upper = float(st.beta.ppf(1.0 - alpha / 2.0, k + 1, n - k))

    return max(0.0, lower), min(1.0, upper)


def mcnemar_exact(b: int, c: int) -> float:
    """
    Exact two-sided McNemar test for paired binary outcomes.

    Evaluates the null hypothesis H0: p_b = p_c on discordant pairs (b, c)
    via an exact two-sided binomial test with p=0.5.

    Args:
        b: Number of items where System A was correct and System B was incorrect.
        c: Number of items where System B was correct and System A was incorrect.

    Returns:
        Exact two-sided p-value in [0.0, 1.0].
    """
    total = b + c
    if total == 0:
        return 1.0
    res = st.binomtest(b, n=total, p=0.5, alternative="two-sided")
    return float(res.pvalue)


def _get_field(row: Any, key: str, default: Any = None) -> Any:
    """Helper to extract field from either a Pydantic model or a dictionary."""
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def cluster_bootstrap_ci(
    rows: Sequence[Any],
    metric_fn: Callable[[List[Any]], float],
    cluster_key: str = "cluster_id",
    B: int = 10000,
    confidence: float = 0.95,
    seed: int = 0,
) -> Tuple[float, float, float]:
    """
    Cluster-bootstrap percentile confidence interval.

    Groups records by cluster_key (dialogue, trajectory, session ID) and resamples
    entire clusters with replacement B times. When each cluster has exactly one item,
    this reduces identically to standard i.i.d. bootstrap at the same random seed.

    Args:
        rows: Sequence of result rows (ResultRow instances or dicts).
        metric_fn: Function mapping a list of rows to a scalar float metric.
        cluster_key: Field used to define clusters (default: 'cluster_id').
        B: Number of bootstrap resamples (default: 10000).
        confidence: Confidence level (default: 0.95).
        seed: Random seed for reproducibility.

    Returns:
        (estimate, ci_lower, ci_upper)
    """
    if not rows:
        return 0.0, 0.0, 0.0

    point_est = float(metric_fn(list(rows)))

    # Group rows into clusters
    clusters_dict: Dict[str, List[Any]] = {}
    for r in rows:
        cid = str(_get_field(r, cluster_key, ""))
        clusters_dict.setdefault(cid, []).append(r)

    cluster_list = list(clusters_dict.values())
    K = len(cluster_list)

    if K <= 1:
        return point_est, point_est, point_est

    rng = np.random.default_rng(seed)
    boot_vals = np.empty(B, dtype=float)

    for b in range(B):
        sample_indices = rng.choice(K, size=K, replace=True)
        # Flatten sampled clusters
        boot_sample = [row for idx in sample_indices for row in cluster_list[idx]]
        boot_vals[b] = metric_fn(boot_sample)

    alpha = 1.0 - confidence
    lower_pct = 100.0 * (alpha / 2.0)
    upper_pct = 100.0 * (1.0 - alpha / 2.0)

    ci_lower = float(np.percentile(boot_vals, lower_pct))
    ci_upper = float(np.percentile(boot_vals, upper_pct))

    return point_est, ci_lower, ci_upper


def paired_cluster_bootstrap_diff(
    rows_a: Sequence[Any],
    rows_b: Sequence[Any],
    metric_fn: Callable[[List[Any]], float],
    cluster_key: str = "cluster_id",
    item_key: str = "item_id",
    B: int = 10000,
    confidence: float = 0.95,
    seed: int = 0,
) -> Tuple[float, float, float]:
    """
    Paired cluster bootstrap for comparing two systems on the same benchmark instances.

    Jointly resamples shared clusters with replacement and calculates the difference:
        Delta = metric_fn(sample_a) - metric_fn(sample_b)

    Args:
        rows_a: Rows from System A.
        rows_b: Rows from System B.
        metric_fn: Metric evaluation function.
        cluster_key: Cluster grouping field.
        item_key: Item identifier field.
        B: Number of bootstrap iterations.
        confidence: Confidence level.
        seed: Random seed.

    Returns:
        (diff_estimate, diff_ci_lower, diff_ci_upper)
    """
    est_a = metric_fn(list(rows_a))
    est_b = metric_fn(list(rows_b))
    point_diff = float(est_a - est_b)

    clusters_a: Dict[str, List[Any]] = {}
    for r in rows_a:
        clusters_a.setdefault(str(_get_field(r, cluster_key, "")), []).append(r)

    clusters_b: Dict[str, List[Any]] = {}
    for r in rows_b:
        clusters_b.setdefault(str(_get_field(r, cluster_key, "")), []).append(r)

    shared_clusters = sorted(set(clusters_a.keys()) & set(clusters_b.keys()))
    K = len(shared_clusters)
    if K <= 1:
        return point_diff, point_diff, point_diff

    rng = np.random.default_rng(seed)
    boot_diffs = np.empty(B, dtype=float)

    for b in range(B):
        idx = rng.choice(K, size=K, replace=True)
        boot_a = [r for i in idx for r in clusters_a[shared_clusters[i]]]
        boot_b = [r for i in idx for r in clusters_b[shared_clusters[i]]]
        boot_diffs[b] = metric_fn(boot_a) - metric_fn(boot_b)

    alpha = 1.0 - confidence
    ci_lower = float(np.percentile(boot_diffs, 100.0 * (alpha / 2.0)))
    ci_upper = float(np.percentile(boot_diffs, 100.0 * (1.0 - alpha / 2.0)))

    return point_diff, ci_lower, ci_upper


# ── Core Evaluation Metrics ───────────────────────────────────────────────────

def _is_error_flagged(decision: Optional[str], legacy_semantics: bool) -> bool:
    """
    Check if a gate decision counts as flagging an error:
    - legacy_semantics=True: Only BLOCK is considered an error detection.
    - legacy_semantics=False: Both ASK and BLOCK count as flagging an error.
    """
    if not decision:
        return False
    d = str(decision).upper()
    if legacy_semantics:
        return d == "BLOCK"
    return d in ("ASK", "BLOCK")


def detection_rate(
    rows: Sequence[Any],
    legacy_semantics: bool = False,
    ci_method: str = "cluster_bootstrap",
    cluster_key: str = "cluster_id",
    B: int = 10000,
    seed: int = 0,
) -> Tuple[float, float, float]:
    """
    Detection Rate (Sensitivity / Recall on erroneous calls where label == 1).

    Definitions:
        - Legacy semantics: Error is detected only if decision == "BLOCK".
        - New semantics: Error is detected if decision in ("ASK", "BLOCK").

    Args:
        rows: Result records.
        legacy_semantics: If True, only BLOCK counts as detection; otherwise ASK or BLOCK.
        ci_method: "cluster_bootstrap" (default) or "wilson".
        cluster_key: Field name for cluster ID.
        B: Bootstrap iterations.
        seed: Random seed.

    Returns:
        (rate, ci_lower, ci_upper)
    """
    positives = [r for r in rows if _get_field(r, "label") == 1]
    n_pos = len(positives)
    if n_pos == 0:
        return 0.0, 0.0, 0.0

    detected_count = sum(
        1 for r in positives if _is_error_flagged(_get_field(r, "decision"), legacy_semantics)
    )
    est = detected_count / n_pos

    if ci_method == "wilson":
        low, high = wilson_ci(detected_count, n_pos)
        return est, low, high

    def _metric(batch: List[Any]) -> float:
        b_pos = [r for r in batch if _get_field(r, "label") == 1]
        if not b_pos:
            return 0.0
        k = sum(1 for r in b_pos if _is_error_flagged(_get_field(r, "decision"), legacy_semantics))
        return k / len(b_pos)

    return cluster_bootstrap_ci(rows, _metric, cluster_key=cluster_key, B=B, seed=seed)


def false_block_rate(
    rows: Sequence[Any],
    legacy_semantics: bool = True,
    ci_method: str = "cluster_bootstrap",
    cluster_key: str = "cluster_id",
    B: int = 10000,
    seed: int = 0,
) -> Tuple[float, float, float]:
    """
    False-Block Rate (Fall-out on clean calls where label == 0).

    Definitions:
        - Legacy semantics: Clean call wrongly blocked (decision == "BLOCK").
        - New semantics: Clean call interrupted (decision in ("ASK", "BLOCK")).

    Args:
        rows: Result records.
        legacy_semantics: If True, only BLOCK counts as false block; if False, ASK or BLOCK.
        ci_method: "cluster_bootstrap" (default) or "wilson".
        cluster_key: Field name for cluster ID.
        B: Bootstrap iterations.
        seed: Random seed.

    Returns:
        (rate, ci_lower, ci_upper)
    """
    negatives = [r for r in rows if _get_field(r, "label") == 0]
    n_neg = len(negatives)
    if n_neg == 0:
        return 0.0, 0.0, 0.0

    flagged_count = sum(
        1 for r in negatives if _is_error_flagged(_get_field(r, "decision"), legacy_semantics)
    )
    est = flagged_count / n_neg

    if ci_method == "wilson":
        low, high = wilson_ci(flagged_count, n_neg)
        return est, low, high

    def _metric(batch: List[Any]) -> float:
        b_neg = [r for r in batch if _get_field(r, "label") == 0]
        if not b_neg:
            return 0.0
        k = sum(1 for r in b_neg if _is_error_flagged(_get_field(r, "decision"), legacy_semantics))
        return k / len(b_neg)

    return cluster_bootstrap_ci(rows, _metric, cluster_key=cluster_key, B=B, seed=seed)


def interruption_rate(
    rows: Sequence[Any],
    ci_method: str = "cluster_bootstrap",
    cluster_key: str = "cluster_id",
    B: int = 10000,
    seed: int = 0,
) -> Tuple[float, float, float]:
    """
    Interruption Rate on clean calls: Fraction of clean calls (label == 0) receiving ASK or BLOCK.

    Returns:
        (rate, ci_lower, ci_upper)
    """
    return false_block_rate(
        rows,
        legacy_semantics=False,
        ci_method=ci_method,
        cluster_key=cluster_key,
        B=B,
        seed=seed,
    )


def hard_block_rate(
    rows: Sequence[Any],
    ci_method: str = "cluster_bootstrap",
    cluster_key: str = "cluster_id",
    B: int = 10000,
    seed: int = 0,
) -> Tuple[float, float, float]:
    """
    Hard-Block Rate on clean calls: Fraction of clean calls (label == 0) receiving strictly BLOCK.

    Returns:
        (rate, ci_lower, ci_upper)
    """
    return false_block_rate(
        rows,
        legacy_semantics=True,
        ci_method=ci_method,
        cluster_key=cluster_key,
        B=B,
        seed=seed,
    )


def youden_j(
    rows: Sequence[Any],
    legacy_semantics: bool = False,
    cluster_key: str = "cluster_id",
    B: int = 10000,
    seed: int = 0,
) -> Tuple[float, float, float]:
    """
    Youden's J statistic (Informedness):
        J = Detection Rate (Sensitivity) - False Block Rate (1 - Specificity)
        Range: [-1.0, 1.0]. A value of 1.0 represents perfect discrimination; 0.0 is chance.

    Returns:
        (j_estimate, ci_lower, ci_upper) via cluster bootstrap.
    """
    def _metric(batch: List[Any]) -> float:
        pos = [r for r in batch if _get_field(r, "label") == 1]
        neg = [r for r in batch if _get_field(r, "label") == 0]
        if not pos or not neg:
            return 0.0
        det = sum(1 for r in pos if _is_error_flagged(_get_field(r, "decision"), legacy_semantics)) / len(pos)
        fbr = sum(1 for r in neg if _is_error_flagged(_get_field(r, "decision"), legacy_semantics)) / len(neg)
        return det - fbr

    return cluster_bootstrap_ci(rows, _metric, cluster_key=cluster_key, B=B, seed=seed)


def auroc_with_ci(
    rows: Sequence[Any],
    score_key: str = "score",
    label_key: str = "label",
    higher_is_error: bool = True,
    cluster_key: str = "cluster_id",
    B: int = 2000,
    seed: int = 0,
) -> Tuple[float, float, float]:
    """
    Area Under the ROC Curve (AUROC) with cluster-bootstrap confidence interval.

    Uses the Mann-Whitney U rank statistic for exact O(N log N) computation.

    Args:
        rows: Result records with continuous score and binary label.
        score_key: Name of the continuous score field.
        label_key: Binary label field (1 = error, 0 = clean).
        higher_is_error: If True, higher score means higher suspicion of error.
        cluster_key: Cluster grouping field.
        B: Number of bootstrap iterations.
        seed: Random seed.

    Returns:
        (auroc, ci_lower, ci_upper)
    """
    def _compute_auroc(items: List[Any]) -> float:
        scores_pos = []
        scores_neg = []
        for r in items:
            s = _get_field(r, score_key)
            lbl = _get_field(r, label_key)
            if s is None or lbl is None:
                continue
            val = float(s) if higher_is_error else -float(s)
            if lbl == 1:
                scores_pos.append(val)
            elif lbl == 0:
                scores_neg.append(val)

        if not scores_pos or not scores_neg:
            return 0.5

        # Wilcoxon-Mann-Whitney U statistic
        # U = sum of ranks of positive items - n_pos*(n_pos+1)/2
        all_scores = np.concatenate([scores_pos, scores_neg])
        ranks = st.rankdata(all_scores)
        n_pos = len(scores_pos)
        n_neg = len(scores_neg)
        sum_ranks_pos = np.sum(ranks[:n_pos])
        u = sum_ranks_pos - (n_pos * (n_pos + 1.0)) / 2.0
        return float(u / (n_pos * n_neg))

    return cluster_bootstrap_ci(rows, _compute_auroc, cluster_key=cluster_key, B=B, seed=seed)


def required_positives_for_detection_gap(
    p_a: float,
    p_b: float,
    correlation: float,
    power: float = 0.80,
    alpha: float = 0.05,
    seed: int = 0,
    n_sim: int = 400,
    max_n: int = 5000,
) -> int:
    """
    Estimate the required number of positive cases N to detect a difference between
    two paired binary detectors with marginal detection rates p_a and p_b and Pearson correlation r.

    Documented as APPROXIMATE: Uses Monte Carlo simulation of bivariate Bernoulli pairs
    evaluated under McNemar's exact test (binomtest).

    Args:
        p_a: Detection rate of System A (in [0.0, 1.0]).
        p_b: Detection rate of System B (in [0.0, 1.0]).
        correlation: Pearson correlation r between System A and B detection indicators.
        power: Desired statistical power 1 - beta (default: 0.80).
        alpha: Two-sided significance level (default: 0.05).
        seed: Random seed for simulation.
        n_sim: Number of simulated benchmark replicates per candidate N.
        max_n: Maximum search horizon.

    Returns:
        Estimated integer sample size N of positive test cases required.
    """
    if p_a == p_b:
        return max_n

    # Compute bivariate Bernoulli cell probabilities
    cov = correlation * math.sqrt(max(0.0, p_a * (1.0 - p_a) * p_b * (1.0 - p_b)))
    p11 = np.clip(p_a * p_b + cov, max(0.0, p_a + p_b - 1.0), min(p_a, p_b))
    p10 = max(0.0, p_a - p11)
    p01 = max(0.0, p_b - p11)
    p00 = max(0.0, 1.0 - (p11 + p10 + p01))
    probs = np.array([p11, p10, p01, p00], dtype=float)
    total_p = probs.sum()
    if total_p <= 0:
        return max_n
    probs /= total_p

    def _eval_power(n_test: int) -> float:
        rng = np.random.default_rng(seed + n_test)
        mult_draws = rng.multinomial(n_test, probs, size=n_sim)
        n10 = mult_draws[:, 1]
        n01 = mult_draws[:, 2]
        disc = n10 + n01

        rejections = 0
        for i in range(n_sim):
            d = disc[i]
            if d > 0:
                p_val = st.binomtest(n10[i], n=d, p=0.5, alternative="two-sided").pvalue
                if p_val < alpha:
                    rejections += 1
        return float(rejections / n_sim)

    # Bisection search over [10, max_n]
    low = 10
    high = max_n
    ans = max_n

    while low <= high:
        mid = (low + high) // 2
        emp_power = _eval_power(mid)
        if emp_power >= power:
            ans = mid
            high = mid - 1
        else:
            low = mid + 1

    return ans
