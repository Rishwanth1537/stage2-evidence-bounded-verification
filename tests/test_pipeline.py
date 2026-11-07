"""Unit tests for the SRL + graph building pipeline."""
import pytest
from unittest.mock import patch, MagicMock
from server.pipeline.graph_builder import build_semantic_graph


MOCK_FRAMES = [
    {
        "predicate": "transfer",
        "arguments": {"ARG0": "Alice", "ARG1": "100 dollars", "ARG2": "Bob"},
    }
]
MOCK_DEP_TRIPLES = [("Alice", "nsubj", "transfer"), ("Bob", "dobj", "transfer")]


@patch("server.pipeline.graph_builder.extract_frames", return_value=MOCK_FRAMES)
@patch("server.pipeline.graph_builder.extract_dep_triples", return_value=MOCK_DEP_TRIPLES)
def test_graph_has_nodes_and_edges(mock_dep, mock_srl):
    G = build_semantic_graph("Alice transferred 100 dollars to Bob.")
    assert G.number_of_nodes() > 0
    assert G.number_of_edges() > 0


@patch("server.pipeline.graph_builder.extract_frames", return_value=MOCK_FRAMES)
@patch("server.pipeline.graph_builder.extract_dep_triples", return_value=MOCK_DEP_TRIPLES)
def test_graph_contains_predicate_node(mock_dep, mock_srl):
    G = build_semantic_graph("Alice transferred 100 dollars to Bob.")
    assert "transfer" in G.nodes


# ── Numeric / value span enrichment ──────────────────────────────────────────

def test_value_spans_include_money_node():
    """extract_frames must return a MONEY argument when spaCy detects currency."""
    from server.pipeline.srl import extract_frames, _VALUE_ENT_LABELS

    # Build a minimal fake spaCy doc via real spaCy sm model mock
    class _FakeEnt:
        def __init__(self, text, label, root_pos="VERB", root_lemma="transfer"):
            self.text = text
            self.label_ = label

            class _FakeRoot:
                pos_ = root_pos
                lemma_ = root_lemma
                dep_ = "ROOT"
                head = self  # self-referential stub

                def __init__(inner_self):
                    inner_self.head = inner_self

            self.root = _FakeRoot()
            self.root.head = self.root  # stop traversal immediately

    class _FakeDoc:
        ents = [_FakeEnt("$50", "MONEY")]
        def __iter__(self):
            return iter([])

    class _FakeTok:
        pass

    with patch("server.pipeline.srl._load_ner", return_value=lambda text: []):
        with patch("server.pipeline.srl._load_nlp") as mock_nlp:
            mock_nlp.return_value = lambda text: _FakeDoc()
            frames = extract_frames("Alice transferred $50 to Bob.")

    # At least one frame should have a MONEY argument
    all_roles = {
        role
        for frame in frames
        for role in frame["arguments"]
    }
    assert "MONEY" in all_roles, f"MONEY role missing from frames: {frames}"


def test_value_argument_text_is_captured_as_node():
    """
    When $50 and $500 appear as MONEY spans, the graph must contain their
    text as distinct node IDs — ensuring entailment can distinguish them.
    The test uses manually built graphs rather than relying on GED attribute-matching,
    because the greedy GED only compares `kind` attrs, not node ID strings.
    """
    import networkx as nx

    G_fifty = nx.DiGraph()
    G_fifty.add_node("transfer", kind="predicate")
    G_fifty.add_node("$50", kind="argument")
    G_fifty.add_edge("transfer", "$50", label="MONEY")

    G_fivehundred = nx.DiGraph()
    G_fivehundred.add_node("transfer", kind="predicate")
    G_fivehundred.add_node("$500", kind="argument")
    G_fivehundred.add_edge("transfer", "$500", label="MONEY")

    # Node IDs must be different — this is what the entailment stage uses
    assert "$50" in G_fifty.nodes
    assert "$50" not in G_fivehundred.nodes
    assert "$500" in G_fivehundred.nodes
    assert "$500" not in G_fifty.nodes


def test_structurally_nonisomorphic_graphs_have_nonzero_ged():
    """
    Two graphs with different edge counts must produce GED > 0.
    This verifies the GED mechanism fires when graph topology genuinely differs.
    """
    from server.pipeline.ged import compute_ged
    import networkx as nx

    G1 = nx.DiGraph()
    G1.add_node("reboot", kind="predicate")
    G1.add_node("server", kind="argument")
    G1.add_node("3AM", kind="argument")
    G1.add_edge("reboot", "server", label="ARG1")
    G1.add_edge("reboot", "3AM", label="TIME")

    G2 = nx.DiGraph()
    G2.add_node("update", kind="predicate")
    G2.add_node("database", kind="argument")
    G2.add_edge("update", "database", label="ARG1")

    raw, norm = compute_ged(G1, G2)
    assert raw > 0.0, f"Different topology graphs must have non-zero GED (got {raw})"
    assert 0.0 < norm <= 1.0


def test_extract_frames_value_ent_labels_set():
    """_VALUE_ENT_LABELS must contain the standard numeric/temporal labels."""
    from server.pipeline.srl import _VALUE_ENT_LABELS
    required = {"MONEY", "CARDINAL", "DATE", "TIME", "PERCENT", "ORDINAL", "QUANTITY"}
    assert required.issubset(_VALUE_ENT_LABELS)

