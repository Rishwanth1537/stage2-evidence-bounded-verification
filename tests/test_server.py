"""Integration test: verify_logic_chain tool end-to-end (mocked pipeline)."""
import pytest
from unittest.mock import patch, MagicMock
import networkx as nx

from server.tools.verify_logic import run_verification


def _make_graph(n_nodes=3, n_edges=2):
    G = nx.DiGraph()
    for i in range(n_nodes):
        G.add_node(f"node_{i}")
    for i in range(n_edges):
        G.add_edge(f"node_{i}", f"node_{i+1}", label=f"rel_{i}")
    return G


MOCK_FRAMES = [{"predicate": "send", "arguments": {"ARG0": "agent", "ARG1": "data"}}]


@patch("server.tools.verify_logic.build_semantic_graph")
@patch("server.tools.verify_logic.compute_ged", return_value=(0.0, 0.0))
@patch("server.tools.verify_logic.extract_frames", return_value=MOCK_FRAMES)
@patch("server.tools.verify_logic.score_spans", return_value=[("agent", 0.9), ("data", 0.85)])
def test_consistent_chain(mock_spans, mock_srl, mock_ged, mock_graph):
    mock_graph.return_value = _make_graph()
    result = run_verification("agent sends data", "agent sends data", threshold=0.35)
    assert result.is_consistent is True
    assert result.factual_consistency_score == 1.0
    assert len(result.mismatched_spans) == 0


@patch("server.tools.verify_logic.build_semantic_graph")
@patch("server.tools.verify_logic.compute_ged", return_value=(5.0, 0.8))
@patch("server.tools.verify_logic.extract_frames", return_value=MOCK_FRAMES)
@patch("server.tools.verify_logic.score_spans", return_value=[("agent", 0.2), ("data", 0.1)])
def test_inconsistent_chain_flagged(mock_spans, mock_srl, mock_ged, mock_graph):
    mock_graph.return_value = _make_graph()
    result = run_verification("agent deletes all records", "agent sends data", threshold=0.35)
    assert result.is_consistent is False
    assert result.factual_consistency_score < 1.0
    assert len(result.mismatched_spans) > 0
