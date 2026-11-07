"""
Property-based tests for the MCP Hallucination Checker.
All 12 correctness properties from the design document.
ML model calls are mocked at pipeline boundaries.
"""
from __future__ import annotations
import statistics
from unittest.mock import patch, MagicMock
from typing import List

import networkx as nx
import pytest
from hypothesis import given, settings, assume, HealthCheck
import hypothesis.strategies as st

from server.pipeline.ged import compute_ged
from server.pipeline.taxonomy import classify_all, classify_span
from server.pipeline.constraints import compute_constraint_score
from server.models.schemas import HallucinationType
from server.session import tracker as session_tracker
from server.config import ENTAILMENT_THRESHOLD


# ─── Graph strategies ──────────────────────────────────────────────────────────

def _random_digraph(draw, min_nodes=0, max_nodes=15):
    n = draw(st.integers(min_value=min_nodes, max_value=max_nodes))
    nodes = list(range(n))
    G = nx.DiGraph()
    G.add_nodes_from(nodes)
    if n > 1:
        edge_labels = draw(st.lists(
            st.tuples(
                st.integers(0, n - 1),
                st.integers(0, n - 1),
                st.text(min_size=1, max_size=8),
            ),
            max_size=n * 2,
        ))
        for u, v, label in edge_labels:
            if u != v:
                G.add_edge(u, v, label=label)
    return G


@st.composite
def digraph_strategy(draw, min_nodes=0, max_nodes=15):
    return _random_digraph(draw, min_nodes, max_nodes)


@st.composite
def digraph_pair_strategy(draw):
    G1 = draw(digraph_strategy())
    G2 = draw(digraph_strategy())
    return G1, G2


@st.composite
def large_digraph_strategy(draw):
    """Graph with >40 nodes to trigger fast-mode (pair sum > 80)."""
    return _random_digraph(draw, min_nodes=42, max_nodes=55)


# ─── Property 1 ────────────────────────────────────────────────────────────────

# Feature: mcp-hallucination-checker, Property 1: Normalised GED is always in the unit interval
@given(digraph_pair_strategy())
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_property_1_normalised_ged_in_unit_interval(graph_pair):
    G1, G2 = graph_pair
    _, norm = compute_ged(G1, G2)
    assert 0.0 <= norm <= 1.0


# ─── Property 2 ────────────────────────────────────────────────────────────────

# Feature: mcp-hallucination-checker, Property 2: Identical graphs produce zero GED
@given(digraph_strategy(min_nodes=0, max_nodes=12))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_2_identical_graph_zero_ged(G):
    raw, norm = compute_ged(G, G)
    assert raw == 0.0
    assert norm == 0.0


# ─── Property 3 ────────────────────────────────────────────────────────────────

# Feature: mcp-hallucination-checker, Property 3: Factual consistency score equals one minus normalised GED
@given(st.floats(min_value=0.0, max_value=1.0))
@settings(max_examples=100, deadline=None)
def test_property_3_factual_score_equals_one_minus_ged(norm_ged):
    from server.tools.verify_logic import run_verification

    with patch("server.tools.verify_logic.build_semantic_graph") as mock_graph, \
         patch("server.tools.verify_logic.compute_ged", return_value=(norm_ged * 10, norm_ged)), \
         patch("server.tools.verify_logic.extract_frames", return_value=[]), \
         patch("server.tools.verify_logic.score_spans", return_value=[]):
        mock_graph.return_value = nx.DiGraph()
        result = run_verification("hyp", "prem", threshold=0.5)

    expected = round(max(0.0, 1.0 - norm_ged), 4)
    assert result.factual_consistency_score == expected


# ─── Property 4 ────────────────────────────────────────────────────────────────

# Feature: mcp-hallucination-checker, Property 4: is_consistent is the threshold comparison
@given(
    st.floats(min_value=0.0, max_value=1.0),
    st.floats(min_value=0.0, max_value=1.0),
)
@settings(max_examples=100)
def test_property_4_is_consistent_is_threshold_comparison(norm_ged, threshold):
    from server.tools.verify_logic import run_verification

    with patch("server.tools.verify_logic.build_semantic_graph") as mock_graph, \
         patch("server.tools.verify_logic.compute_ged", return_value=(norm_ged * 10, norm_ged)), \
         patch("server.tools.verify_logic.extract_frames", return_value=[]), \
         patch("server.tools.verify_logic.score_spans", return_value=[]):
        mock_graph.return_value = nx.DiGraph()
        result = run_verification("hyp", "prem", threshold=threshold)

    assert result.is_consistent == (norm_ged <= threshold)


# ─── Property 5 ────────────────────────────────────────────────────────────────

# Feature: mcp-hallucination-checker, Property 5: Entailment threshold filters spans into mismatched_spans correctly
@given(st.lists(
    st.tuples(st.text(min_size=1, max_size=20), st.floats(min_value=0.0, max_value=1.0)),
    min_size=0,
    max_size=10,
    unique_by=lambda x: x[0],   # deduplicate by span text
))
@settings(max_examples=100, deadline=None)
def test_property_5_entailment_span_filtering(span_scores):
    from server.tools.verify_logic import run_verification

    with patch("server.tools.verify_logic.build_semantic_graph") as mock_graph, \
         patch("server.tools.verify_logic.compute_ged", return_value=(0.0, 0.0)), \
         patch("server.tools.verify_logic.extract_frames", return_value=[
             {"predicate": "p", "arguments": {f"A{i}": s for i, (s, _) in enumerate(span_scores)}}
         ]), \
         patch("server.tools.verify_logic.score_spans", return_value=span_scores):
        mock_graph.return_value = nx.DiGraph()
        result = run_verification("hyp", "prem", threshold=0.5)

    mismatched_texts = {m.span for m in result.mismatched_spans}
    for span, score in span_scores:
        if score < ENTAILMENT_THRESHOLD:
            assert span in mismatched_texts, (
                f"span {span!r} with score {score} < {ENTAILMENT_THRESHOLD} "
                f"should be in mismatched_spans"
            )
        else:
            assert span not in mismatched_texts, (
                f"span {span!r} with score {score} >= {ENTAILMENT_THRESHOLD} "
                f"should NOT be in mismatched_spans"
            )


# ─── Property 6 ────────────────────────────────────────────────────────────────

# Feature: mcp-hallucination-checker, Property 6: Schema drift score is matched fields over total required fields
@given(
    st.integers(min_value=0, max_value=10),
    st.integers(min_value=0, max_value=10),
)
@settings(max_examples=100)
def test_property_6_schema_drift_score_arithmetic(total_required, n_missing):
    assume(n_missing <= total_required)
    from server.tools.schema import run_schema_alignment

    required = [f"field_{i}" for i in range(total_required)]
    present = required[n_missing:]
    agent_args = {f: "value" for f in present}
    tool_schema = {
        "required": required,
        "properties": {f: {"type": "string"} for f in required},
    }

    result = run_schema_alignment(agent_args, tool_schema)

    expected = (total_required - n_missing) / total_required if total_required > 0 else 1.0
    assert result.schema_drift_score == pytest.approx(expected, abs=1e-4)


# ─── Property 7 ────────────────────────────────────────────────────────────────

# Feature: mcp-hallucination-checker, Property 7: Every MismatchedSpan has a categorised hallucination type
@given(st.integers(min_value=0, max_value=10))
@settings(max_examples=100)
def test_property_7_every_span_has_hallucination_type(n):
    spans = [f"span_{i}" for i in range(n)]
    issues = [f"issue_{i}" for i in range(n)]
    result = classify_all(spans, issues)
    valid_types = set(HallucinationType)
    for span_obj in result:
        assert span_obj.hallucination_type is not None
        assert span_obj.hallucination_type in valid_types


# ─── Property 8 ────────────────────────────────────────────────────────────────

# Feature: mcp-hallucination-checker, Property 8: Schema and format mismatches are classified correctly
@given(
    st.integers(min_value=1, max_value=8),
    st.integers(min_value=0, max_value=8),
)
@settings(max_examples=100)
def test_property_8_schema_format_mismatch_classification(n_missing, n_type_mismatch):
    from server.tools.schema import run_schema_alignment

    total = n_missing + n_type_mismatch
    assume(total <= 15)

    missing_fields = [f"miss_{i}" for i in range(n_missing)]
    type_fields = [f"type_{i}" for i in range(n_type_mismatch)]
    all_required = missing_fields + type_fields

    properties = {}
    for f in missing_fields:
        properties[f] = {"type": "string"}
    for f in type_fields:
        properties[f] = {"type": "integer"}

    agent_args = {f: "wrong_type" for f in type_fields}
    tool_schema = {"required": all_required, "properties": properties}

    result = run_schema_alignment(agent_args, tool_schema)

    for m in result.mismatches:
        if m.span in missing_fields:
            assert m.hallucination_type == HallucinationType.SCHEMA
        elif m.span in type_fields:
            assert m.hallucination_type == HallucinationType.FORMAT


# ─── Property 9 ────────────────────────────────────────────────────────────────

# Feature: mcp-hallucination-checker, Property 9: Session rolling mean equals arithmetic mean of the last window scores
@given(
    st.lists(st.floats(min_value=0.0, max_value=1.0, allow_nan=False), min_size=1, max_size=20),
    st.integers(min_value=1, max_value=10),
)
@settings(max_examples=100)
def test_property_9_rolling_mean_arithmetic(scores, window):
    sid = f"prop9_{id(scores)}_{window}"
    session_tracker.clear_session(sid)
    for s in scores:
        session_tracker.record(sid, s, window=window)
    expected = statistics.mean(scores[-window:])
    result = session_tracker.get_rolling_mean(sid, window=window)
    assert result == pytest.approx(expected, abs=1e-9)
    session_tracker.clear_session(sid)


# ─── Property 10 ───────────────────────────────────────────────────────────────

# Feature: mcp-hallucination-checker, Property 10: Drift alert triggered exactly when rolling mean is below threshold
@given(
    st.lists(st.floats(min_value=0.0, max_value=1.0, allow_nan=False), min_size=1, max_size=10),
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
)
@settings(max_examples=100)
def test_property_10_drift_alert_threshold(scores, threshold):
    sid = f"prop10_{id(scores)}_{threshold}"
    session_tracker.clear_session(sid)
    for s in scores:
        session_tracker.record(sid, s)
    mean = session_tracker.get_rolling_mean(sid)
    drifting = session_tracker.is_drifting(sid, drift_threshold=threshold)
    assert drifting == (mean < threshold)
    session_tracker.clear_session(sid)


# ─── Property 11 ───────────────────────────────────────────────────────────────

# Feature: mcp-hallucination-checker, Property 11: Constraint score equals preserved fraction, with zero-denominator safety
@given(
    st.lists(st.text(min_size=2, max_size=12, alphabet=st.characters(whitelist_categories=("Ll",))), min_size=0, max_size=10),
    st.text(min_size=0, max_size=200),
)
@settings(max_examples=100)
def test_property_11_constraint_score_arithmetic(constraints, hypothesis):
    score, missing = compute_constraint_score(constraints, hypothesis)
    assert 0.0 <= score <= 1.0
    if not constraints:
        assert score == 1.0
    else:
        hyp_lower = hypothesis.lower()
        expected_preserved = sum(1 for c in constraints if c.lower() in hyp_lower)
        expected_score = expected_preserved / len(constraints)
        assert score == pytest.approx(expected_score, abs=1e-9)


# ─── Property 12 ───────────────────────────────────────────────────────────────

# Feature: mcp-hallucination-checker, Property 12: Missing constraints appear in mismatched_spans with content type
@given(
    st.lists(
        st.text(min_size=3, max_size=10, alphabet=st.characters(whitelist_categories=("Ll",))),
        min_size=1,
        max_size=6,
        unique=True,
    )
)
@settings(max_examples=100)
def test_property_12_missing_constraints_are_content_spans(constraints):
    from server.tools.verify_logic import run_verification

    # hypothesis deliberately contains none of the constraints
    hypothesis = "the agent performs an unrelated action"
    assume(all(c.lower() not in hypothesis.lower() for c in constraints))

    with patch("server.tools.verify_logic.build_semantic_graph") as mock_graph, \
         patch("server.tools.verify_logic.compute_ged", return_value=(0.0, 0.0)), \
         patch("server.tools.verify_logic.extract_frames", return_value=[]), \
         patch("server.tools.verify_logic.score_spans", return_value=[]), \
         patch("server.tools.verify_logic.extract_constraints", return_value=constraints):
        mock_graph.return_value = nx.DiGraph()
        result = run_verification("hyp", "prem", user_query="dummy query with constraints")

    content_spans = {m.span for m in result.mismatched_spans if m.hallucination_type == HallucinationType.CONTENT}
    for c in constraints:
        assert c in content_spans
