"""
Unit and property-based tests for Two-Tier Gate Policy (Prompt 4).

Verifies:
- Table-driven check tier mapping (ORACLE_EXACT vs COVERAGE_BOUNDED vs UNCHECKABLE).
- Hypothesis property test: schema-valid calls never trigger ORACLE_EXACT FAIL.
- legacy_blocking=True reproduces old strict decisions on a fixed fixture set.
- ASK decision never executes a @guarded downstream tool function.
"""
from __future__ import annotations

from unittest.mock import MagicMock
import hypothesis.strategies as st
from hypothesis import given, settings
import pytest

from server.models.schemas import (
    CheckOutcome,
    CheckResult,
    CheckTier,
    Decision,
    HallucinationType,
    MismatchedSpan,
)
from server.pipeline.arg_ground import check_arguments, check_value
from server.proxy.gate_policy import GatePolicy
from server.proxy.interceptor import InterceptingToolProxy, RiskLevel, guarded
from server.tools.schema import run_schema_alignment


# ── 1. Table-driven Tier Mapping ───────────────────────────────────────────────

@pytest.mark.parametrize(
    "arg_name,arg_value,schema_def,context,expected_tier,expected_evidence_tier,expected_outcome",
    [
        # JSON-Schema type mismatch -> ORACLE_EXACT (E2), FAIL
        ("count", "not_an_int", {"type": "integer"}, "there are 5 items", CheckTier.ORACLE_EXACT, "E2", CheckOutcome.FAIL),
        # JSON-Schema required missing -> ORACLE_EXACT (E2), FAIL
        ("missing_field", None, {"type": "string"}, "any context", CheckTier.ORACLE_EXACT, "E2", CheckOutcome.FAIL),
        # JSON-Schema enum mismatch -> ORACLE_EXACT (E2), FAIL
        ("status", "pending", {"type": "string", "enum": ["active", "closed"]}, "pending status", CheckTier.ORACLE_EXACT, "E2", CheckOutcome.FAIL),
        # JSON-Schema pattern mismatch -> ORACLE_EXACT (E2), FAIL
        ("code", "123", {"type": "string", "pattern": r"^[A-Z]{3}$"}, "code 123", CheckTier.ORACLE_EXACT, "E2", CheckOutcome.FAIL),
        # JSON-Schema range mismatch -> ORACLE_EXACT (E2), FAIL
        ("amount", -5.0, {"type": "number", "minimum": 0.0}, "amount is 5", CheckTier.ORACLE_EXACT, "E2", CheckOutcome.FAIL),
        # Free-text parameter description ("City, State") -> COVERAGE_BOUNDED (E2), FAIL
        ("loc", "Boston", {"type": "string", "description": "City, State format required"}, "Boston, MA", CheckTier.COVERAGE_BOUNDED, "E2", CheckOutcome.FAIL),
        # Context-ungrounded number -> COVERAGE_BOUNDED (E1), FAIL
        ("price", 500.0, None, "The approved price is 50 dollars.", CheckTier.COVERAGE_BOUNDED, "E1", CheckOutcome.FAIL),
        # Context-ungrounded string -> COVERAGE_BOUNDED (E1), FAIL
        ("recipient", "Alice", None, "Send the funds to Bob.", CheckTier.COVERAGE_BOUNDED, "E1", CheckOutcome.FAIL),
        # Context-grounded number -> COVERAGE_BOUNDED (E1), PASS
        ("price", 50.0, None, "The approved price is 50 dollars.", CheckTier.COVERAGE_BOUNDED, "E1", CheckOutcome.PASS),
        # Booleans -> UNCHECKABLE, ABSTAIN
        ("confirmed", True, None, "The user confirmed.", CheckTier.UNCHECKABLE, "E1", CheckOutcome.ABSTAIN),
        # Null values -> UNCHECKABLE, ABSTAIN
        ("extra", None, None, "Context.", CheckTier.UNCHECKABLE, "E1", CheckOutcome.ABSTAIN),
        # Empty string -> UNCHECKABLE, ABSTAIN
        ("comment", "", None, "Context.", CheckTier.UNCHECKABLE, "E1", CheckOutcome.ABSTAIN),
    ],
)
def test_table_driven_tier_mapping(
    arg_name, arg_value, schema_def, context, expected_tier, expected_evidence_tier, expected_outcome
):
    """Verify each check is classified into its authoritative tier and evidence tier."""
    if schema_def is not None:
        # Schema test
        schema = {
            "required": [arg_name] if arg_value is None else [],
            "properties": {arg_name: schema_def},
        }
        agent_args = {} if arg_value is None else {arg_name: arg_value}
        res = run_schema_alignment(agent_args, schema)
        if expected_outcome == CheckOutcome.FAIL:
            matching = [
                c for c in res.check_results
                if (c.arg_path == arg_name or arg_name in c.check_id) and c.outcome == CheckOutcome.FAIL
            ]
        else:
            matching = [
                c for c in res.check_results
                if (c.arg_path == arg_name or arg_name in c.check_id) and c.tier == expected_tier
            ]
        assert len(matching) > 0, f"No matching check for {arg_name}: {res.check_results}"
        chk = matching[0]
        assert chk.tier == expected_tier
        assert chk.evidence_tier == expected_evidence_tier
        assert chk.outcome == expected_outcome
    else:
        # Grounding test
        v = check_value(arg_name, arg_value, context)
        if expected_outcome == CheckOutcome.ABSTAIN:
            assert v.verdict == "UNCHECKABLE"
        elif expected_outcome == CheckOutcome.PASS:
            assert v.verdict == "GROUNDED"
        else:
            assert v.verdict == "UNGROUNDED"


# ── 2. Hypothesis Property Test ───────────────────────────────────────────────

@given(
    amount=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False),
    account=st.from_regex(r"^[A-Z]{3}-\d{3}$", fullmatch=True),
)
@settings(max_examples=100)
def test_schema_valid_call_never_triggers_oracle_exact_fail(amount, account):
    """
    Property: A call that conforms to the JSON Schema contract
    never triggers an ORACLE_EXACT FAIL.
    """
    tool_schema = {
        "required": ["amount", "account"],
        "properties": {
            "amount": {"type": "number", "minimum": 0.0},
            "account": {"type": "string", "pattern": r"^[A-Z]{3}-\d{3}$"},
        },
    }
    agent_args = {"amount": amount, "account": account}
    res = run_schema_alignment(agent_args, tool_schema)

    oracle_fails = [
        c for c in res.check_results
        if c.tier == CheckTier.ORACLE_EXACT and c.outcome == CheckOutcome.FAIL
    ]
    assert len(oracle_fails) == 0
    assert res.is_aligned is True


# ── 3. Legacy Blocking Reproduces Old Decisions ───────────────────────────────

def test_legacy_blocking_reproduces_old_decisions_side_by_side():
    """
    Verify legacy_blocking=True reproduces old decisions (BLOCK on any error)
    while ASK-on-coverage converts ungrounded values to ASK.
    """
    fixtures = [
        # (args, schema, context, old_blocked_expected, old_decision_expected)
        # Case A: Valid schema, grounded context -> PASS
        ({"amount": 50.0}, {"properties": {"amount": {"type": "number"}}}, "Transfer 50 dollars.", False, Decision.ALLOW),
        # Case B: Schema type violation -> ORACLE_EXACT FAIL -> BLOCK in both
        ({"amount": "fifty"}, {"properties": {"amount": {"type": "number"}}}, "Transfer 50 dollars.", True, Decision.BLOCK),
        # Case C: Valid schema, ungrounded context -> COVERAGE FAIL
        # Legacy: BLOCK; New: ASK
        ({"amount": 500.0}, {"properties": {"amount": {"type": "number"}}}, "Transfer 50 dollars.", True, Decision.BLOCK),
    ]

    legacy_policy = GatePolicy(legacy_blocking=True)
    two_tier_policy = GatePolicy(legacy_blocking=False, coverage_fail_decision=Decision.ASK, oracle_fail_decision=Decision.BLOCK)

    for args, schema, context, old_blocked, old_decision in fixtures:
        stub = MagicMock(return_value="executed")
        proxy_legacy = InterceptingToolProxy(
            tool_fn=stub, tool_schema=schema, risk_level=RiskLevel.HIGH, logic_mode="arguments", policy=legacy_policy
        )
        res_legacy = proxy_legacy.call(agent_args=args, source_context=context)

        # Under legacy policy:
        assert res_legacy.blocked == old_blocked
        assert res_legacy.decision == old_decision

        stub_new = MagicMock(return_value="executed")
        proxy_new = InterceptingToolProxy(
            tool_fn=stub_new, tool_schema=schema, risk_level=RiskLevel.HIGH, logic_mode="arguments", policy=two_tier_policy
        )
        res_new = proxy_new.call(agent_args=args, source_context=context)

        # Under two-tier policy:
        if args["amount"] == 500.0:  # ungrounded case
            assert res_new.blocked is True
            assert res_new.decision == Decision.ASK
            assert res_new.clarification_request is not None
            assert len(stub_new.mock_calls) == 0  # tool not executed


# ── 4. ASK Never Executes a @guarded Function ─────────────────────────────────

def test_ask_decision_never_executes_guarded_function():
    """
    When the decision is ASK, the proxy must pause execution, populate
    ClarificationRequest, and NEVER call the underlying tool.
    """
    tool_executed = False

    @guarded(
        tool_schema={"properties": {"amount": {"type": "number"}}},
        risk_level=RiskLevel.HIGH,
        logic_mode="arguments",
        policy=GatePolicy(legacy_blocking=False, coverage_fail_decision=Decision.ASK),
    )
    def sensitive_payment(amount: float) -> str:
        nonlocal tool_executed
        tool_executed = True
        return "payment_processed"

    # Call with ungrounded amount (500 dollars not in context)
    result = sensitive_payment.proxy.call(
        agent_args={"amount": 500.0},
        source_context="Approved transaction for 50 dollars only.",
    )

    assert result.blocked is True
    assert result.decision == Decision.ASK
    assert result.tool_output is None
    assert tool_executed is False, "Tool function MUST NOT be called on ASK decision!"
    assert result.clarification_request is not None
    assert "amount" in result.clarification_request.arguments
    assert result.clarification_request.missing_evidence_tier == "E1"
