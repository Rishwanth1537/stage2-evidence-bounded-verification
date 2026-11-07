"""
Approximate Graph Edit Distance — pure-Python implementation, no numpy required.

Uses a greedy bipartite node matching (Hungarian-style cost matrix solved with
a simple min-cost greedy pass) to estimate GED in O(n^2) time.

Cost model
──────────
  node insertion / deletion            = 1.0
  edge insertion / deletion            = 1.0
  node substitution (same ID)          = 0.0  exact match
                                       = 0.3  same ID, attr drift
  node substitution (diff ID, value)   = 1.0  VALUE kinds always exact-match
  node substitution (diff ID, other)   = 0.5  same non-value kind
                                       = 1.0  different kind
  negated vs non-negated predicate     = 1.0  even with same lemma
  edge label substitution              = 0.5

VALUE kinds are spans that carry concrete measured quantities: MONEY, CARDINAL,
ORDINAL, PERCENT, QUANTITY, DATE, TIME, VERSION.  Any substitution between two
distinct value spans (e.g. "$50" vs "$500", "v2.4.0" vs "v2.4.1",
"Monday" vs "Tuesday") is treated as maximally inconsistent (cost 1.0) rather
than a cheap same-kind match (old cost 0.5).  This is the primary fix for
numeric/temporal hallucination detection.

Normalisation:
  normalised = raw / (|V_hyp| + |V_prem| + |E_hyp| + |E_prem|)
  Always clamped to [0, 1].

Symmetry:
  Canonical (smaller-first) ordering is applied before matching so that
  compute_ged(A, B) == compute_ged(B, A).

Fast-mode: when total nodes > 80 the full O(n²) matcher is skipped in favour
of a degree-sequence structural approximation.
"""
from __future__ import annotations
import re
import networkx as nx
from typing import Tuple, List, Optional
from ..config import GED_FAST_MODE_NODE_LIMIT

_FAST_MODE_LIMIT = GED_FAST_MODE_NODE_LIMIT

_VALUE_KINDS = frozenset({
    "MONEY", "CARDINAL", "ORDINAL", "PERCENT",
    "QUANTITY", "DATE", "TIME", "VERSION",
})

_VERSION_RE = re.compile(r"^v?\d+\.\d+(?:\.\d+)?(?:-[a-zA-Z0-9]+)?$")

_GED_DEGRADED: bool = False
_GED_DEGRADED_REASONS: List[str] = []


class GedResult(tuple):
    """
    Subclass of tuple (raw, normalised) for backward compatibility,
    with attached degraded flags.
    """
    raw: float
    normalised: float
    degraded: bool
    degraded_reasons: List[str]

    def __new__(cls, raw: float, normalised: float, degraded: bool = False, degraded_reasons: Optional[List[str]] = None):
        instance = super().__new__(cls, (raw, normalised))
        instance.raw = raw
        instance.normalised = normalised
        instance.degraded = degraded
        instance.degraded_reasons = list(degraded_reasons or [])
        return instance


def get_ged_degraded_status() -> Tuple[bool, List[str]]:
    """Returns (degraded, reasons) for the GED module."""
    return (_GED_DEGRADED, list(_GED_DEGRADED_REASONS))


def _is_value_node(node_id: str, attrs: dict) -> bool:
    """Return True if this node represents a concrete measured value."""
    if attrs.get("kind") in _VALUE_KINDS:
        return True
    if _VERSION_RE.match(str(node_id).strip()):
        return True
    return False


def _node_subst_cost(n1: str, a1: dict, n2: str, a2: dict) -> float:
    """
    Substitution cost between two nodes:
      0.0 → identical ID and attributes
      0.3 → identical ID (lemma), minor attribute drift (not negated)
      0.5 → different ID, same syntactic kind (e.g. both ARG, both VERB)
            UNLESS either node is a value node — value nodes require exact match!
      1.0 → different kind, or value-node mutation ($50 vs $500), or negation mismatch

    The negation penalty ensures that a negated predicate node is
    treated as maximally distant from its non-negated counterpart even
    when they share the same lemma string.

    The value-kind penalty ensures that "$50" and "$500" (both MONEY) are
    treated as maximally different, not cheaply interchangeable at cost 0.5.
    """
    if n1 == n2 and a1 == a2:
        return 0.0
    if n1 == n2:
        # Same lemma — check for negation flip (not X vs X → max cost)
        neg1 = a1.get("negated", False)
        neg2 = a2.get("negated", False)
        if neg1 != neg2:
            return 1.0  # negation mismatch: semantically opposite
        return 0.3  # same label, minor attribute drift
    # Different node IDs — value nodes require exact match
    if _is_value_node(n1, a1) or _is_value_node(n2, a2):
        return 1.0  # numeric/temporal/version mutation: max cost
    same_kind = a1.get("kind") == a2.get("kind")
    return 0.5 if same_kind else 1.0


def _edge_subst_cost(a: dict, b: dict) -> float:
    return 0.0 if a.get("label") == b.get("label") else 0.5


def _greedy_ged(G1: nx.DiGraph, G2: nx.DiGraph) -> Tuple[float, bool, List[str]]:
    """
    O(n³) optimal bipartite node matching via scipy's linear_sum_assignment
    (true Hungarian algorithm), with fallback to greedy O(n²) if scipy is
    unavailable.

    1. Build cost matrix for all (v1, v2) node pairs.
    2. Solve the minimum-cost assignment problem optimally.
    3. Add deletion cost for unmatched G1 nodes, insertion for unmatched G2.
    4. Add edge edit costs based on matched node pairs.
    """
    nodes1 = list(G1.nodes(data=True))
    nodes2 = list(G2.nodes(data=True))
    n, m = len(nodes1), len(nodes2)

    if n == 0 and m == 0:
        return 0.0, False, []

    # Build cost matrix (pad the smaller dimension with insertion/deletion costs)
    size = max(n, m)
    # Unmatched slots cost 1.0 each (insertion or deletion)
    cost_matrix = [[1.0] * size for _ in range(size)]
    for i, (n1, a1) in enumerate(nodes1):
        for j, (n2, a2) in enumerate(nodes2):
            cost_matrix[i][j] = _node_subst_cost(n1, a1, n2, a2)

    degraded = False
    degraded_reasons: List[str] = []

    # Solve assignment problem
    try:
        import numpy as np
        from scipy.optimize import linear_sum_assignment
        row_ind, col_ind = linear_sum_assignment(np.array(cost_matrix))
        assignment = list(zip(row_ind.tolist(), col_ind.tolist()))
    except (ImportError, Exception):
        # Fallback: greedy sort-based matching (original behaviour)
        degraded = True
        degraded_reasons.append("scipy.optimize.linear_sum_assignment unavailable; fell back to greedy matching")
        costs = []
        for i in range(size):
            for j in range(size):
                costs.append((cost_matrix[i][j], i, j))
        costs.sort()
        matched_r, matched_c = set(), set()
        assignment = []
        for cost, i, j in costs:
            if i not in matched_r and j not in matched_c:
                matched_r.add(i)
                matched_c.add(j)
                assignment.append((i, j))

    total_cost = 0.0
    node_map: dict = {}  # G1 node → G2 node (only for real node pairs)

    for i, j in assignment:
        total_cost += cost_matrix[i][j]
        if i < n and j < m:
            node_map[nodes1[i][0]] = nodes2[j][0]

    # Edge costs: for each matched real-node pair, compare outgoing edges
    edges2_index: dict = {}
    for u, v, data in G2.edges(data=True):
        edges2_index.setdefault(u, {})[v] = data

    for n1, n2 in node_map.items():
        e1_targets = {node_map.get(v): d for v, d in G1[n1].items() if node_map.get(v) is not None}
        e2_targets = edges2_index.get(n2, {})

        all_targets = set(e1_targets) | set(e2_targets)
        for t in all_targets:
            if t in e1_targets and t in e2_targets:
                total_cost += _edge_subst_cost(e1_targets[t], e2_targets[t])
            else:
                total_cost += 1.0  # insertion or deletion

    return total_cost, degraded, degraded_reasons


def _fast_approx_ged(G1: nx.DiGraph, G2: nx.DiGraph) -> float:
    """
    Very fast structural approximation for large graphs.
    Based on degree sequence difference + edge count difference +
    a value-node mismatch penalty.

    Value nodes in G1 that have no exact counterpart in G2 (and vice versa)
    each contribute a full cost-1.0 penalty so that numeric/temporal
    hallucinations are not silently absorbed by structural similarity.
    """
    deg1 = sorted(d for _, d in G1.degree())
    deg2 = sorted(d for _, d in G2.degree())

    # Pad shorter list
    while len(deg1) < len(deg2):
        deg1.append(0)
    while len(deg2) < len(deg1):
        deg2.append(0)

    node_diff = sum(abs(a - b) for a, b in zip(deg1, deg2))
    edge_diff = abs(G1.number_of_edges() - G2.number_of_edges())

    # Value-node mismatch penalty: each unmatched value node costs 1.0
    vals1 = {n for n, a in G1.nodes(data=True) if _is_value_node(n, a)}
    vals2 = {n for n, a in G2.nodes(data=True) if _is_value_node(n, a)}
    value_penalty = float(len(vals1.symmetric_difference(vals2)))

    return float(node_diff + edge_diff) + value_penalty


def compute_ged(G_hyp: nx.DiGraph, G_prem: nx.DiGraph) -> Tuple[float, float]:
    """
    Returns (raw_ged, normalised_ged) as a GedResult tuple.
    normalised_ged is always in [0, 1].

    Canonical ordering (smaller graph first) is applied so that
    compute_ged(A, B) == compute_ged(B, A) — satisfying metric symmetry.

    Value-node amplification:
        When value nodes (MONEY, DATE, VERSION, etc.) differ between the two
        graphs, a per-unmatched-value penalty of ``VALUE_MISMATCH_WEIGHT`` is
        added *after* normalisation so that numeric/temporal hallucinations
        cannot be diluted by a large number of structural non-value nodes.
        The final score is clamped to [0, 1].
    """
    global _GED_DEGRADED, _GED_DEGRADED_REASONS
    # Weight applied per unmatched value node AFTER normalisation.
    # Each unmatched value node adds this fraction to the normalised score,
    # making numeric mutations impossible to hide in a large graph.
    _VALUE_MISMATCH_WEIGHT = 0.20

    total_nodes = G_hyp.number_of_nodes() + G_prem.number_of_nodes()
    denom = total_nodes + G_hyp.number_of_edges() + G_prem.number_of_edges()

    # --- Enforce symmetry via canonical (smaller-first) ordering -----------
    if G_hyp.number_of_nodes() > G_prem.number_of_nodes():
        G_hyp, G_prem = G_prem, G_hyp
    # -----------------------------------------------------------------------

    if total_nodes > _FAST_MODE_LIMIT:
        raw = _fast_approx_ged(G_hyp, G_prem)
        ged_degraded = False
        ged_reasons: List[str] = []
    else:
        raw, ged_degraded, ged_reasons = _greedy_ged(G_hyp, G_prem)

    _GED_DEGRADED = ged_degraded
    _GED_DEGRADED_REASONS = ged_reasons

    normalised = raw / denom if denom > 0 else 0.0
    normalised = max(0.0, min(1.0, normalised))

    # --- Value-node amplification: count unmatched value nodes -------------
    vals_hyp = {n for n, a in G_hyp.nodes(data=True) if _is_value_node(n, a)}
    vals_prem = {n for n, a in G_prem.nodes(data=True) if _is_value_node(n, a)}
    unmatched_values = len(vals_hyp.symmetric_difference(vals_prem))
    value_bonus = unmatched_values * _VALUE_MISMATCH_WEIGHT

    normalised = min(1.0, normalised + value_bonus)
    return GedResult(raw, normalised, degraded=ged_degraded, degraded_reasons=ged_reasons)
