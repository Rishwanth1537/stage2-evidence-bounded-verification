"""Tests for the negation detection module and its integration with GED."""
from __future__ import annotations
import networkx as nx
import pytest
from unittest.mock import patch, MagicMock

from server.pipeline.ged import compute_ged, _node_subst_cost


# ── Unit tests for _node_subst_cost negation logic ────────────────────────────

def test_negated_vs_nonnegated_same_lemma_costs_max():
    """transfer(negated=True) vs transfer(negated=False) must cost 1.0."""
    cost = _node_subst_cost(
        "transfer", {"kind": "predicate", "negated": True},
        "transfer", {"kind": "predicate", "negated": False},
    )
    assert cost == 1.0, (
        f"Negation mismatch on same lemma must cost 1.0, got {cost}"
    )


def test_negated_vs_negated_same_costs_zero():
    """transfer(negated=True) vs transfer(negated=True) is an exact match."""
    cost = _node_subst_cost(
        "transfer", {"kind": "predicate", "negated": True},
        "transfer", {"kind": "predicate", "negated": True},
    )
    assert cost == 0.0


def test_nonnegated_vs_nonnegated_same_costs_zero():
    """transfer(negated=False) vs transfer(negated=False) is exact."""
    cost = _node_subst_cost(
        "transfer", {"kind": "predicate", "negated": False},
        "transfer", {"kind": "predicate", "negated": False},
    )
    assert cost == 0.0


def test_different_lemma_same_kind_costs_half():
    """delete vs read (both predicates, no negation) costs 0.5."""
    cost = _node_subst_cost(
        "delete", {"kind": "predicate"},
        "read",   {"kind": "predicate"},
    )
    assert cost == 0.5


def test_different_lemma_different_kind_costs_one():
    """predicate vs argument always costs 1.0."""
    cost = _node_subst_cost(
        "transfer", {"kind": "predicate"},
        "Alice",    {"kind": "argument"},
    )
    assert cost == 1.0


# ── GED integration: negated graph should diverge from non-negated ────────────

def _make_transfer_graph(negated: bool) -> nx.DiGraph:
    G = nx.DiGraph()
    G.add_node("transfer", kind="predicate", negated=negated)
    G.add_node("Alice",    kind="argument")
    G.add_node("$50",      kind="argument")
    G.add_edge("transfer", "Alice", label="AGENT")
    G.add_edge("transfer", "$50",   label="MONEY")
    return G


def test_negated_graph_has_nonzero_ged_vs_nonnegated():
    """
    Graphs where only negation differs must have GED > 0.
    ("Alice did NOT transfer $50" vs "Alice transferred $50")
    """
    G_negated     = _make_transfer_graph(negated=True)
    G_nonnegated  = _make_transfer_graph(negated=False)
    raw, norm = compute_ged(G_negated, G_nonnegated)
    assert raw > 0.0, (
        f"GED between negated and non-negated graph must be > 0 (got {raw})"
    )
    assert 0.0 < norm <= 1.0


def test_identical_negation_state_has_zero_ged():
    """Two graphs with the same negation state should have zero GED."""
    G1 = _make_transfer_graph(negated=True)
    G2 = _make_transfer_graph(negated=True)
    raw, norm = compute_ged(G1, G2)
    assert raw == 0.0
    assert norm == 0.0


# ── Role-swap: dep edges differentiate AGENT vs PATIENT ──────────────────────

def test_role_swap_produces_different_graph_topology():
    """
    "Alice paid Bob" and "Bob paid Alice" must not be graph-identical.
    After dep_parser maps nsubj→AGENT and dobj→PATIENT, the edges connecting
    Alice and Bob to the predicate carry different labels depending on ordering.
    """
    from server.pipeline.dep_parser import _DEP_TO_ROLE
    # Verify the mapping exists
    assert _DEP_TO_ROLE.get("nsubj") == "AGENT"
    assert _DEP_TO_ROLE.get("dobj") == "PATIENT"

    # Build two role-swapped graphs manually
    def _make_pay_graph(agent, patient):
        G = nx.DiGraph()
        G.add_node("pay",    kind="predicate", negated=False)
        G.add_node(agent,    kind="argument")
        G.add_node(patient,  kind="argument")
        G.add_edge("pay", agent,   label="AGENT")
        G.add_edge("pay", patient, label="PATIENT")
        return G

    G_alice_pays = _make_pay_graph("Alice", "Bob")
    G_bob_pays   = _make_pay_graph("Bob",   "Alice")

    raw, norm = compute_ged(G_alice_pays, G_bob_pays)
    assert raw > 0.0, (
        f"Role-swapped graphs must have GED > 0 (got {raw}). "
        "Alice-pays-Bob and Bob-pays-Alice should be distinguishable."
    )


# ── find_negated_predicates unit test ─────────────────────────────────────────

def test_find_negated_predicates_detects_neg_children():
    """find_negated_predicates returns the head lemma of any neg child."""
    from server.pipeline.negation import find_negated_predicates

    class _Tok:
        def __init__(self, dep_, head_lemma, lemma_):
            self.dep_ = dep_
            self.lemma_ = lemma_
            self.head = type("H", (), {"lemma_": head_lemma})()

    class _FakeDoc:
        def __iter__(self):
            return iter([
                _Tok("nsubj", "transfer", "Alice"),
                _Tok("neg",   "transfer", "not"),
                _Tok("dobj",  "transfer", "money"),
            ])

    negated = find_negated_predicates(_FakeDoc())
    assert "transfer" in negated, f"Expected 'transfer' in negated set, got {negated}"


def test_find_negated_predicates_empty_when_no_negation():
    from server.pipeline.negation import find_negated_predicates

    class _Tok:
        def __init__(self, dep_, head_lemma, lemma_):
            self.dep_ = dep_
            self.lemma_ = lemma_
            self.head = type("H", (), {"lemma_": head_lemma})()

    class _FakeDoc:
        def __iter__(self):
            return iter([
                _Tok("nsubj", "transfer", "Alice"),
                _Tok("dobj",  "transfer", "money"),
            ])

    negated = find_negated_predicates(_FakeDoc())
    assert len(negated) == 0, f"Expected empty negated set, got {negated}"
