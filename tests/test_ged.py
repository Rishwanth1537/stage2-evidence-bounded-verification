"""Unit tests for GED computation."""
import networkx as nx
import pytest
from server.pipeline.ged import compute_ged, _node_subst_cost, _is_value_node


def _simple_graph(edges):
    G = nx.DiGraph()
    for u, v, label in edges:
        G.add_edge(u, v, label=label)
    return G


def test_identical_graphs_have_zero_ged():
    G = _simple_graph([("Alice", "Bob", "ARG1"), ("transfer", "Alice", "ARG0")])
    raw, norm = compute_ged(G, G)
    assert raw == 0.0
    assert norm == 0.0


def test_completely_different_graphs_have_high_ged():
    G1 = _simple_graph([("A", "B", "rel1")])
    G2 = _simple_graph([("X", "Y", "rel2"), ("Y", "Z", "rel3")])
    raw, norm = compute_ged(G1, G2)
    assert raw > 0
    assert 0.0 <= norm <= 1.0


def test_normalised_ged_in_unit_interval():
    G1 = _simple_graph([("a", "b", "l1"), ("b", "c", "l2")])
    G2 = _simple_graph([("a", "b", "l1"), ("b", "d", "l3")])
    _, norm = compute_ged(G1, G2)
    assert 0.0 <= norm <= 1.0


# ── Value-kind cost model ─────────────────────────────────────────────────────

def test_value_node_different_id_costs_one():
    """$50 vs $500 (both MONEY kind) must cost 1.0, not 0.5."""
    cost = _node_subst_cost(
        "$50",  {"kind": "MONEY"},
        "$500", {"kind": "MONEY"},
    )
    assert cost == 1.0, f"Numeric mutation must cost 1.0, got {cost}"


def test_value_node_same_id_costs_zero():
    """$50 vs $50 (exact match) costs 0."""
    cost = _node_subst_cost(
        "$50", {"kind": "MONEY"},
        "$50", {"kind": "MONEY"},
    )
    assert cost == 0.0


def test_version_node_different_id_costs_one():
    """v2.4.0 vs v2.4.1 must cost 1.0."""
    cost = _node_subst_cost(
        "v2.4.0", {"kind": "argument"},
        "v2.4.1", {"kind": "argument"},
    )
    assert cost == 1.0, f"Version mutation must cost 1.0, got {cost}"


def test_date_node_different_id_costs_one():
    """Monday vs Tuesday (both DATE) must cost 1.0."""
    cost = _node_subst_cost(
        "Monday",  {"kind": "DATE"},
        "Tuesday", {"kind": "DATE"},
    )
    assert cost == 1.0


def test_non_value_same_kind_costs_half():
    """Non-value nodes of the same kind still cost 0.5."""
    cost = _node_subst_cost(
        "delete", {"kind": "predicate"},
        "read",   {"kind": "predicate"},
    )
    assert cost == 0.5


def test_is_value_node_recognises_money():
    assert _is_value_node("$50", {"kind": "MONEY"}) is True


def test_is_value_node_recognises_version_string():
    assert _is_value_node("v2.4.0", {"kind": "argument"}) is True
    assert _is_value_node("2.4.1",  {"kind": "argument"}) is True


def test_is_value_node_rejects_non_value():
    assert _is_value_node("Alice", {"kind": "argument"}) is False
    assert _is_value_node("delete", {"kind": "predicate"}) is False


# ── End-to-end: numeric mutation produces meaningful GED ─────────────────────

def _make_transfer_graph(amount: str) -> nx.DiGraph:
    """Build a minimal graph representing 'Alice transferred <amount> to Bob'."""
    G = nx.DiGraph()
    G.add_node("transfer", kind="predicate", negated=False)
    G.add_node("Alice",    kind="argument")
    G.add_node(amount,     kind="MONEY")
    G.add_node("Bob",      kind="argument")
    G.add_edge("transfer", "Alice",  label="AGENT")
    G.add_edge("transfer", amount,   label="MONEY")
    G.add_edge("transfer", "Bob",    label="PATIENT")
    return G


def test_numeric_mutation_produces_nonzero_ged():
    """The $50 vs $500 hallucination must produce GED > 0."""
    G_50  = _make_transfer_graph("$50")
    G_500 = _make_transfer_graph("$500")
    raw, norm = compute_ged(G_50, G_500)
    assert raw > 0.0, f"$50 vs $500 must differ (got raw GED={raw})"
    assert norm > 0.0


def test_numeric_mutation_exceeds_default_threshold():
    """The $50 vs $500 GED must exceed the default threshold of 0.35."""
    from server.config import GED_THRESHOLD
    G_50  = _make_transfer_graph("$50")
    G_500 = _make_transfer_graph("$500")
    _, norm = compute_ged(G_50, G_500)
    assert norm > GED_THRESHOLD, (
        f"Numeric mutation GED {norm:.4f} should exceed threshold {GED_THRESHOLD}"
    )


def test_version_mutation_produces_nonzero_ged():
    """v2.4.0 vs v2.4.1 must produce GED > 0."""
    G1 = nx.DiGraph()
    G1.add_node("deploy",  kind="predicate", negated=False)
    G1.add_node("v2.4.0",  kind="argument")
    G1.add_edge("deploy", "v2.4.0", label="VERSION")

    G2 = nx.DiGraph()
    G2.add_node("deploy",  kind="predicate", negated=False)
    G2.add_node("v2.4.1",  kind="argument")
    G2.add_edge("deploy", "v2.4.1", label="VERSION")

    raw, norm = compute_ged(G1, G2)
    assert raw > 0.0, f"Version mutation must differ (got raw GED={raw})"
