"""
Unit tests for explicit degraded mode and fail-closed verification gates.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import networkx as nx
import pytest

from server.config import FAIL_CLOSED_ON_DEGRADED
from server.models.schemas import VerifyResponse, SchemaAlignmentResponse, ArgumentGroundingResponse
from server.pipeline import arg_ground, constraints, dep_parser, ged, srl
from server.proxy.interceptor import InterceptingToolProxy, RiskLevel, BlockReason


def test_normal_call_has_degraded_false():
    """When models and libraries are available, degraded flag must be False."""
    # Mock spacy.load to succeed for en_core_web_trf
    mock_nlp = MagicMock()
    mock_doc = MagicMock()
    mock_doc.ents = []
    mock_doc.__iter__.return_value = []
    mock_nlp.return_value = mock_doc

    with patch("spacy.load", return_value=mock_nlp):
        # Clear lru_caches
        constraints._load_nlp.cache_clear()
        dep_parser._load_nlp.cache_clear()
        srl._load_nlp.cache_clear()

        # Load NLP models with mock
        constraints._load_nlp()
        dep_parser._load_nlp()
        srl._load_nlp()

        deg_c, reasons_c = constraints.get_constraints_degraded_status()
        deg_d, reasons_d = dep_parser.get_dep_parser_degraded_status()
        deg_s, reasons_s = srl.get_srl_degraded_status()

        assert deg_c is False and reasons_c == []
        assert deg_d is False and reasons_d == []
        assert deg_s is False and reasons_s == []

    # Reset cache
    constraints._load_nlp.cache_clear()
    dep_parser._load_nlp.cache_clear()
    srl._load_nlp.cache_clear()


def test_spacy_downgrade_sets_degraded_flag():
    """When en_core_web_trf is unavailable, falling back to en_core_web_sm sets degraded=True."""
    def fake_spacy_load(name, *args, **kwargs):
        if name == "en_core_web_trf":
            raise OSError("Model en_core_web_trf not found")
        # return a mock for en_core_web_sm
        mock_sm = MagicMock()
        mock_sm.ents = []
        mock_sm.__iter__.return_value = []
        return mock_sm

    with patch("spacy.load", side_effect=fake_spacy_load):
        constraints._load_nlp.cache_clear()
        dep_parser._load_nlp.cache_clear()
        srl._load_nlp.cache_clear()

        constraints._load_nlp()
        dep_parser._load_nlp()
        srl._load_nlp()

        deg_c, reasons_c = constraints.get_constraints_degraded_status()
        deg_d, reasons_d = dep_parser.get_dep_parser_degraded_status()
        deg_s, reasons_s = srl.get_srl_degraded_status()

        assert deg_c is True
        assert "spaCy model downgraded to en_core_web_sm (en_core_web_trf unavailable)" in reasons_c[0]
        assert deg_d is True
        assert "spaCy model downgraded to en_core_web_sm (en_core_web_trf unavailable)" in reasons_d[0]
        assert deg_s is True
        assert "spaCy model downgraded to en_core_web_sm (en_core_web_trf unavailable)" in reasons_s[0]

    # Reset cache
    constraints._load_nlp.cache_clear()
    dep_parser._load_nlp.cache_clear()
    srl._load_nlp.cache_clear()


def test_scipy_import_error_in_ged_sets_degraded_flag():
    """When scipy import fails in _greedy_ged, fallback to greedy matching sets degraded=True."""
    G1 = nx.DiGraph()
    G1.add_node("transfer", kind="VERB")
    G2 = nx.DiGraph()
    G2.add_node("pay", kind="VERB")

    with patch("scipy.optimize.linear_sum_assignment", side_effect=ImportError("No scipy")):
        res = ged.compute_ged(G1, G2)
        raw, norm = res

        assert isinstance(res, ged.GedResult)
        assert res.degraded is True
        assert len(res.degraded_reasons) == 1
        assert "scipy.optimize.linear_sum_assignment unavailable" in res.degraded_reasons[0]
        deg, reasons = ged.get_ged_degraded_status()
        assert deg is True


def test_unparseable_numeric_token_in_arg_ground_sets_degraded():
    """Unparseable float matches in arg_ground increment skipped counter and surface degraded flag."""
    context = "Transfer amount is 100 dollars."
    real_float = float

    def mock_float(val):
        if val == "100":
            raise ValueError("simulated unparseable token")
        return real_float(val)

    with patch("builtins.float", side_effect=mock_float):
        nums, skipped = arg_ground.numbers_in_detailed(context)
        assert skipped == 1

        verdicts = arg_ground.check_arguments({"amount": 100}, context)
        assert verdicts.degraded is True
        assert "unparseable numeric token(s) skipped: 1" in verdicts.degraded_reasons[0]


def test_fail_closed_engages_on_degraded_schema():
    """When FAIL_CLOSED_ON_DEGRADED is True and schema check is degraded, tool call is blocked."""
    tool = MagicMock(return_value="executed")
    tool.__name__ = "stub_tool"
    proxy = InterceptingToolProxy(
        tool_fn=tool,
        tool_schema={"properties": {"x": {"type": "integer"}}},
        risk_level=RiskLevel.MEDIUM,
    )

    degraded_schema_res = SchemaAlignmentResponse(
        is_aligned=True,
        schema_drift_score=1.0,
        mismatches=[],
        degraded=True,
        degraded_reasons=["schema verifier rule evaluation degraded"],
    )

    with patch("server.tools.schema.run_schema_alignment", return_value=degraded_schema_res):
        res = proxy.call(agent_args={"x": 10})

    assert res.blocked is True
    assert res.block_reason == BlockReason.VERIFIER_DEGRADED
    assert res.block_reason == "verifier degraded"
    assert res.degraded is True
    assert "verifier degraded" in res.feedback
    assert len(tool.mock_calls) == 0


def test_fail_closed_engages_on_degraded_logic():
    """When FAIL_CLOSED_ON_DEGRADED is True and logic verification is degraded, tool call is blocked."""
    tool = MagicMock(return_value="executed")
    tool.__name__ = "stub_tool"
    proxy = InterceptingToolProxy(
        tool_fn=tool,
        tool_schema={"properties": {"amount": {"type": "number"}}},
        risk_level=RiskLevel.HIGH,
        logic_mode="hybrid",
    )

    schema_ok = SchemaAlignmentResponse(is_aligned=True, schema_drift_score=1.0, mismatches=[], degraded=False)
    degraded_logic_res = VerifyResponse(
        factual_consistency_score=0.95,
        is_consistent=True,
        mismatched_spans=[],
        feedback="Consistent",
        ged_raw=0.05,
        ged_normalised=0.05,
        degraded=True,
        degraded_reasons=["spaCy model downgraded to en_core_web_sm (en_core_web_trf unavailable)"],
    )

    with patch("server.tools.schema.run_schema_alignment", return_value=schema_ok), \
         patch("server.tools.verify_logic.run_verification", return_value=degraded_logic_res):
        res = proxy.call(
            agent_args={"amount": 50},
            reasoning_context="Transfer 50 dollars",
            source_context="Approved 50 dollars transfer",
        )

    assert res.blocked is True
    assert res.block_reason == BlockReason.VERIFIER_DEGRADED
    assert res.degraded is True
    assert len(tool.mock_calls) == 0


def test_fail_closed_disabled_allows_degraded_call():
    """When FAIL_CLOSED_ON_DEGRADED is False, a degraded check that passes is allowed through."""
    tool = MagicMock(return_value="executed")
    tool.__name__ = "stub_tool"
    proxy = InterceptingToolProxy(
        tool_fn=tool,
        tool_schema={"properties": {"amount": {"type": "number"}}},
        risk_level=RiskLevel.HIGH,
        logic_mode="hybrid",
    )

    schema_ok = SchemaAlignmentResponse(is_aligned=True, schema_drift_score=1.0, mismatches=[], degraded=False)
    degraded_logic_res = VerifyResponse(
        factual_consistency_score=0.95,
        is_consistent=True,
        mismatched_spans=[],
        feedback="Consistent",
        ged_raw=0.05,
        ged_normalised=0.05,
        degraded=True,
        degraded_reasons=["spaCy model downgraded to en_core_web_sm (en_core_web_trf unavailable)"],
    )

    with patch("server.proxy.interceptor.FAIL_CLOSED_ON_DEGRADED", False), \
         patch("server.tools.schema.run_schema_alignment", return_value=schema_ok), \
         patch("server.tools.verify_logic.run_verification", return_value=degraded_logic_res):
        res = proxy.call(
            agent_args={"amount": 50},
            reasoning_context="Transfer 50 dollars",
            source_context="Approved 50 dollars transfer",
        )

    assert res.blocked is False
    assert res.tool_output == "executed"
    assert res.degraded is True
    assert len(res.degraded_reasons) == 1
