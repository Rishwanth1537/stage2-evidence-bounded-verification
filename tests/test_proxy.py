"""
Unit tests for the InterceptingToolProxy middleware.

All ML model calls are mocked — these tests run without downloading models.
"""
from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock

from server.proxy.interceptor import (
    InterceptingToolProxy,
    RiskLevel,
    BlockReason,
    guarded,
)
from server.models.schemas import HallucinationType, MismatchedSpan


# ── Test helpers ───────────────────────────────────────────────────────────────

def _make_tool(return_value="executed"):
    """Return a simple stub function that records calls."""
    calls = []
    def _tool(**kwargs):
        calls.append(kwargs)
        return return_value
    _tool.calls = calls
    return _tool


_SIMPLE_SCHEMA = {
    "required": ["amount", "to_account"],
    "properties": {
        "amount":     {"type": "number"},
        "to_account": {"type": "string"},
    },
}

_ALIGNED_RESULT = MagicMock(
    is_aligned=True, mismatches=[], schema_drift_score=1.0
)
_SCHEMA_FAIL_RESULT = MagicMock(
    is_aligned=False,
    mismatches=[
        MismatchedSpan(
            span="to_account",
            issue="Required field 'to_account' is missing.",
            hallucination_type=HallucinationType.SCHEMA,
        )
    ],
    schema_drift_score=0.5,
)
_LOGIC_PASS_RESULT = MagicMock(
    is_consistent=True,
    mismatched_spans=[],
    factual_consistency_score=0.92,
    ged_normalised=0.08,
    feedback="Reasoning chain is structurally consistent.",
)
_LOGIC_FAIL_RESULT = MagicMock(
    is_consistent=False,
    mismatched_spans=[
        MismatchedSpan(
            span="500",
            issue="Entailment score 0.01 — span not supported by premise.",
            hallucination_type=HallucinationType.CONTENT,
        )
    ],
    factual_consistency_score=0.12,
    ged_normalised=0.88,
    feedback="Reasoning chain inconsistent.",
)


# ── LOW risk: always passes through ───────────────────────────────────────────

def test_low_risk_bypasses_all_verification():
    tool = _make_tool("read_ok")
    proxy = InterceptingToolProxy(tool_fn=tool, risk_level=RiskLevel.LOW)
    result = proxy.call(agent_args={"query": "SELECT * FROM logs"})
    assert result.blocked is False
    assert result.tool_output == "read_ok"
    assert len(tool.calls) == 1


# ── MEDIUM risk: schema only ──────────────────────────────────────────────────

def test_medium_risk_passes_on_valid_schema():
    tool = _make_tool()
    proxy = InterceptingToolProxy(
        tool_fn=tool,
        tool_schema=_SIMPLE_SCHEMA,
        risk_level=RiskLevel.MEDIUM,
    )
    with patch("server.tools.schema.run_schema_alignment", return_value=_ALIGNED_RESULT):
        result = proxy.call(agent_args={"amount": 50.0, "to_account": "ACC-001"})
    assert result.blocked is False
    assert len(tool.calls) == 1


def test_medium_risk_blocks_on_schema_failure():
    tool = _make_tool()
    proxy = InterceptingToolProxy(
        tool_fn=tool,
        tool_schema=_SIMPLE_SCHEMA,
        risk_level=RiskLevel.MEDIUM,
    )
    with patch("server.tools.schema.run_schema_alignment", return_value=_SCHEMA_FAIL_RESULT):
        result = proxy.call(agent_args={"amount": 50.0})  # missing to_account
    assert result.blocked is True
    assert result.block_reason == BlockReason.SCHEMA_MISMATCH
    assert len(result.schema_mismatches) == 1
    assert len(tool.calls) == 0  # tool must NOT have been called


# ── HIGH risk: schema + logic ─────────────────────────────────────────────────

def test_high_risk_executes_when_both_pass():
    tool = _make_tool("transfer_ok")
    proxy = InterceptingToolProxy(
        tool_fn=tool,
        tool_schema=_SIMPLE_SCHEMA,
        risk_level=RiskLevel.HIGH,
    )
    with patch("server.tools.schema.run_schema_alignment", return_value=_ALIGNED_RESULT), \
         patch("server.tools.verify_logic.run_verification", return_value=_LOGIC_PASS_RESULT):
        result = proxy.call(
            agent_args={"amount": 50.0, "to_account": "ACC-001"},
            reasoning_context="Transfer $50 to ACC-001.",
            source_context="Approved: transfer $50 to ACC-001.",
        )
    assert result.blocked is False
    assert result.tool_output == "transfer_ok"
    assert len(tool.calls) == 1


def test_high_risk_blocks_on_schema_failure_before_logic():
    """Schema failure short-circuits before logic check is even attempted."""
    tool = _make_tool()
    proxy = InterceptingToolProxy(
        tool_fn=tool,
        tool_schema=_SIMPLE_SCHEMA,
        risk_level=RiskLevel.HIGH,
    )
    with patch("server.tools.schema.run_schema_alignment", return_value=_SCHEMA_FAIL_RESULT) as mock_schema, \
         patch("server.tools.verify_logic.run_verification") as mock_logic:
        result = proxy.call(
            agent_args={"amount": 50.0},
            reasoning_context="Transfer $50.",
            source_context="Approved: $50.",
        )
    assert result.blocked is True
    assert result.block_reason == BlockReason.SCHEMA_MISMATCH
    mock_logic.assert_not_called()  # logic check never ran
    assert len(tool.calls) == 0


def test_high_risk_blocks_on_logic_failure():
    """Schema passes but logic is inconsistent → blocked."""
    tool = _make_tool()
    proxy = InterceptingToolProxy(
        tool_fn=tool,
        tool_schema=_SIMPLE_SCHEMA,
        risk_level=RiskLevel.HIGH,
    )
    with patch("server.tools.schema.run_schema_alignment", return_value=_ALIGNED_RESULT), \
         patch("server.tools.verify_logic.run_verification", return_value=_LOGIC_FAIL_RESULT):
        result = proxy.call(
            agent_args={"amount": 500.0, "to_account": "ACC-001"},
            reasoning_context="Transfer $500 to ACC-001.",  # hallucinated amount
            source_context="Approved: transfer $50 to ACC-001.",
        )
    assert result.blocked is True
    assert result.block_reason == BlockReason.LOGIC_INCONSISTENT
    assert len(result.logic_mismatches) == 1
    assert result.logic_mismatches[0].span == "500"
    assert len(tool.calls) == 0


def test_high_risk_skips_logic_when_no_context():
    """When reasoning_context or source_context not provided, logic check is skipped."""
    tool = _make_tool("ok")
    proxy = InterceptingToolProxy(
        tool_fn=tool,
        tool_schema=_SIMPLE_SCHEMA,
        risk_level=RiskLevel.HIGH,
    )
    with patch("server.tools.schema.run_schema_alignment", return_value=_ALIGNED_RESULT), \
         patch("server.tools.verify_logic.run_verification") as mock_logic:
        result = proxy.call(
            agent_args={"amount": 50.0, "to_account": "ACC-001"},
            # No reasoning_context / source_context provided
        )
    assert result.blocked is False
    mock_logic.assert_not_called()
    assert len(tool.calls) == 1


# ── Custom GED threshold ───────────────────────────────────────────────────────

def test_custom_ged_threshold_passed_to_logic_check():
    """The proxy's ged_threshold is forwarded to run_verification."""
    tool = _make_tool()
    proxy = InterceptingToolProxy(
        tool_fn=tool,
        tool_schema=_SIMPLE_SCHEMA,
        risk_level=RiskLevel.HIGH,
        ged_threshold=0.20,
    )
    captured_kwargs = {}

    def _capture(**kwargs):
        captured_kwargs.update(kwargs)
        return _LOGIC_PASS_RESULT

    with patch("server.tools.schema.run_schema_alignment", return_value=_ALIGNED_RESULT), \
         patch("server.tools.verify_logic.run_verification", side_effect=_capture):
        proxy.call(
            agent_args={"amount": 50.0, "to_account": "ACC-001"},
            reasoning_context="Transfer $50.",
            source_context="Approved: $50.",
        )
    assert captured_kwargs.get("threshold") == 0.20


# ── @guarded decorator ─────────────────────────────────────────────────────────

def test_guarded_decorator_attaches_proxy():
    @guarded(tool_schema=_SIMPLE_SCHEMA, risk_level=RiskLevel.HIGH)
    def my_tool(amount: float, to_account: str) -> str:
        return "done"

    # Direct call still works (bypasses proxy)
    assert my_tool(amount=50.0, to_account="X") == "done"
    # Proxy attribute exists
    assert hasattr(my_tool, "proxy")
    assert isinstance(my_tool.proxy, InterceptingToolProxy)


def test_guarded_decorator_proxy_blocks():
    @guarded(tool_schema=_SIMPLE_SCHEMA, risk_level=RiskLevel.HIGH)
    def my_tool(amount: float, to_account: str) -> str:
        return "done"

    with patch("server.tools.schema.run_schema_alignment", return_value=_SCHEMA_FAIL_RESULT):
        result = my_tool.proxy.call(agent_args={"amount": 50.0})  # missing to_account

    assert result.blocked is True


# ── No tool_schema: logic-only check ─────────────────────────────────────────

def test_no_schema_skips_to_logic_check():
    """When tool_schema is empty, schema check is skipped; logic check runs."""
    tool = _make_tool("ok")
    proxy = InterceptingToolProxy(
        tool_fn=tool,
        tool_schema={},  # no schema
        risk_level=RiskLevel.HIGH,
    )
    with patch("server.tools.verify_logic.run_verification", return_value=_LOGIC_PASS_RESULT):
        result = proxy.call(
            agent_args={"x": 1},
            reasoning_context="Do something.",
            source_context="Context.",
        )
    assert result.blocked is False
    assert len(tool.calls) == 1
