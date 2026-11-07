"""
Tests for OraclePolicy and COERCIBLE tier (Prompt 5D).

Verifies:
- One test per COERCIBLE case:
  (1) explicit null for optional parameter
  (2) numeric string for integer parameter that parses cleanly
  (3) numeric string for number parameter that parses cleanly
  (4) boolean-like string ("true", "false") for boolean parameter
  (5) enum casing differences (case-insensitive match)
  (6) undeclared key when additionalProperties is permitted (not False)
- One test per ORACLE_EXACT case:
  (1) missing required parameter
  (2) undeclared key when schema forbids additional properties (additionalProperties=False)
  (3) enum mismatch after case-insensitive comparison
  (4) unparseable type mismatch (e.g. list where integer required, or non-numeric string)
  (5) null for a required parameter
- legacy_strict reproduces old strict behavior (all schema mismatches become ORACLE_EXACT FAIL)
- Hypothesis property test: schema-valid calls never trigger ORACLE_EXACT FAIL
- GatePolicy decision: COERCIBLE failures trigger WARN, never BLOCK
"""
from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given, settings
import pytest

from server.models.schemas import (
    CheckOutcome,
    CheckTier,
    Decision,
    OraclePolicy,
)
from server.proxy.gate_policy import GatePolicy
from server.tools.schema import run_schema_alignment


# ── 1. COERCIBLE cases ────────────────────────────────────────────────────────

def test_coercible_explicit_null_for_optional_param():
    schema = {
        "required": ["name"],
        "properties": {
            "name": {"type": "string"},
            "description": {"type": "string"},
        },
    }
    res = run_schema_alignment(
        {"name": "test", "description": None},
        schema,
        oracle_policy=OraclePolicy.COERCIBLE,
    )
    chk = next(c for c in res.check_results if c.arg_path == "description")
    assert chk.tier == CheckTier.COERCIBLE
    assert chk.outcome == CheckOutcome.FAIL
    assert res.decision == Decision.WARN  # Never BLOCK


def test_coercible_numeric_string_for_integer():
    schema = {
        "required": ["count"],
        "properties": {"count": {"type": "integer"}},
    }
    res = run_schema_alignment(
        {"count": "2024"},
        schema,
        oracle_policy=OraclePolicy.COERCIBLE,
    )
    chk = next(c for c in res.check_results if c.arg_path == "count")
    assert chk.tier == CheckTier.COERCIBLE
    assert chk.outcome == CheckOutcome.FAIL
    assert res.decision == Decision.WARN


def test_coercible_numeric_string_for_number():
    schema = {
        "required": ["ratio"],
        "properties": {"ratio": {"type": "number"}},
    }
    res = run_schema_alignment(
        {"ratio": "3.14159"},
        schema,
        oracle_policy=OraclePolicy.COERCIBLE,
    )
    chk = next(c for c in res.check_results if c.arg_path == "ratio")
    assert chk.tier == CheckTier.COERCIBLE
    assert chk.outcome == CheckOutcome.FAIL
    assert res.decision == Decision.WARN


def test_coercible_boolean_string_for_boolean():
    schema = {
        "required": ["active"],
        "properties": {"active": {"type": "boolean"}},
    }
    for val in ["true", "false", "True", "False"]:
        res = run_schema_alignment(
            {"active": val},
            schema,
            oracle_policy=OraclePolicy.COERCIBLE,
        )
        chk = next(c for c in res.check_results if c.arg_path == "active")
        assert chk.tier == CheckTier.COERCIBLE
        assert chk.outcome == CheckOutcome.FAIL
        assert res.decision == Decision.WARN


def test_coercible_enum_casing_differences():
    schema = {
        "required": ["status"],
        "properties": {"status": {"type": "string", "enum": ["ACTIVE", "CLOSED"]}},
    }
    res = run_schema_alignment(
        {"status": "active"},
        schema,
        oracle_policy=OraclePolicy.COERCIBLE,
    )
    chk = next(c for c in res.check_results if c.check_id == "schema_enum:status")
    assert chk.tier == CheckTier.COERCIBLE
    assert chk.outcome == CheckOutcome.FAIL
    assert res.decision == Decision.WARN


def test_coercible_undeclared_key_when_additional_properties_permitted():
    schema = {
        "required": ["name"],
        "properties": {"name": {"type": "string"}},
        # additionalProperties is not False (defaults to True in JSON Schema)
    }
    res = run_schema_alignment(
        {"name": "item", "extra_param": "extra_value"},
        schema,
        oracle_policy=OraclePolicy.COERCIBLE,
    )
    chk = next(c for c in res.check_results if c.check_id == "schema_undeclared:extra_param")
    assert chk.tier == CheckTier.COERCIBLE
    assert chk.outcome == CheckOutcome.FAIL
    assert res.decision == Decision.WARN


# ── 2. ORACLE_EXACT cases (Genuine Contract Violations) ────────────────────────

def test_oracle_exact_missing_required_param():
    schema = {
        "required": ["name", "id"],
        "properties": {"name": {"type": "string"}, "id": {"type": "integer"}},
    }
    res = run_schema_alignment(
        {"name": "item"},  # missing 'id'
        schema,
        oracle_policy=OraclePolicy.COERCIBLE,
    )
    chk = next(c for c in res.check_results if c.check_id == "schema_required:id")
    assert chk.tier == CheckTier.ORACLE_EXACT
    assert chk.outcome == CheckOutcome.FAIL
    assert res.decision == Decision.BLOCK


def test_oracle_exact_undeclared_key_when_additional_properties_forbidden():
    schema = {
        "required": ["name"],
        "properties": {"name": {"type": "string"}},
        "additionalProperties": False,
    }
    res = run_schema_alignment(
        {"name": "item", "illegal_param": 123},
        schema,
        oracle_policy=OraclePolicy.COERCIBLE,
    )
    chk = next(c for c in res.check_results if c.check_id == "schema_undeclared:illegal_param")
    assert chk.tier == CheckTier.ORACLE_EXACT
    assert chk.outcome == CheckOutcome.FAIL
    assert res.decision == Decision.BLOCK


def test_oracle_exact_enum_mismatch_after_case_insensitive_check():
    schema = {
        "required": ["unit"],
        "properties": {"unit": {"type": "string", "enum": ["metric", "imperial"]}},
    }
    res = run_schema_alignment(
        {"unit": "celsius"},
        schema,
        oracle_policy=OraclePolicy.COERCIBLE,
    )
    chk = next(c for c in res.check_results if c.check_id == "schema_enum:unit")
    assert chk.tier == CheckTier.ORACLE_EXACT
    assert chk.outcome == CheckOutcome.FAIL
    assert res.decision == Decision.BLOCK


def test_oracle_exact_unparseable_type_mismatch():
    schema = {
        "required": ["count"],
        "properties": {"count": {"type": "integer"}},
    }
    # List where int required
    res = run_schema_alignment(
        {"count": [1, 2, 3]},
        schema,
        oracle_policy=OraclePolicy.COERCIBLE,
    )
    chk = next(c for c in res.check_results if c.arg_path == "count")
    assert chk.tier == CheckTier.ORACLE_EXACT
    assert chk.outcome == CheckOutcome.FAIL
    assert res.decision == Decision.BLOCK

    # Non-numeric string where int required
    res2 = run_schema_alignment(
        {"count": "dontcare"},
        schema,
        oracle_policy=OraclePolicy.COERCIBLE,
    )
    chk2 = next(c for c in res2.check_results if c.arg_path == "count")
    assert chk2.tier == CheckTier.ORACLE_EXACT
    assert chk2.outcome == CheckOutcome.FAIL
    assert res2.decision == Decision.BLOCK


def test_oracle_exact_null_for_required_parameter():
    schema = {
        "required": ["count"],
        "properties": {"count": {"type": "integer"}},
    }
    res = run_schema_alignment(
        {"count": None},
        schema,
        oracle_policy=OraclePolicy.COERCIBLE,
    )
    chk = next(c for c in res.check_results if c.arg_path == "count")
    assert chk.tier == CheckTier.ORACLE_EXACT
    assert chk.outcome == CheckOutcome.FAIL
    assert res.decision == Decision.BLOCK


# ── 3. legacy_strict Reproduces Old Decisions ──────────────────────────────────

def test_legacy_strict_reproduces_old_decisions():
    """
    Under legacy_strict, all coercible type mismatches become ORACLE_EXACT FAIL,
    resulting in BLOCK.
    """
    schema = {
        "required": ["count"],
        "properties": {
            "count": {"type": "integer"},
            "status": {"type": "string", "enum": ["ACTIVE", "CLOSED"]},
            "opt": {"type": "string"},
        },
    }
    # Case with numeric string and enum casing
    args = {"count": "42", "status": "active", "opt": None}

    # Under COERCIBLE policy: decision is WARN, no ORACLE_EXACT failures
    res_new = run_schema_alignment(args, schema, oracle_policy=OraclePolicy.COERCIBLE)
    assert res_new.decision == Decision.WARN
    assert all(c.tier != CheckTier.ORACLE_EXACT for c in res_new.check_results if c.outcome == CheckOutcome.FAIL)

    # Under LEGACY_STRICT policy: all failures are ORACLE_EXACT -> BLOCK
    res_old = run_schema_alignment(args, schema, oracle_policy=OraclePolicy.LEGACY_STRICT)
    assert res_old.decision == Decision.BLOCK
    fails_old = [c for c in res_old.check_results if c.outcome == CheckOutcome.FAIL]
    assert all(c.tier == CheckTier.ORACLE_EXACT for c in fails_old)


# ── 4. Hypothesis Property Test ───────────────────────────────────────────────

@given(
    amount=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False),
    account=st.from_regex(r"^[A-Z]{3}-\d{3}$", fullmatch=True),
)
@settings(max_examples=100)
def test_schema_valid_call_never_triggers_oracle_exact_fail(amount, account):
    """
    Property: A call that conforms to the JSON Schema contract
    never triggers an ORACLE_EXACT FAIL under either policy.
    """
    tool_schema = {
        "required": ["amount", "account"],
        "properties": {
            "amount": {"type": "number", "minimum": 0.0},
            "account": {"type": "string", "pattern": r"^[A-Z]{3}-\d{3}$"},
        },
    }
    agent_args = {"amount": amount, "account": account}

    for pol in [OraclePolicy.COERCIBLE, OraclePolicy.LEGACY_STRICT]:
        res = run_schema_alignment(agent_args, tool_schema, oracle_policy=pol)
        oracle_fails = [
            c for c in res.check_results
            if c.tier == CheckTier.ORACLE_EXACT and c.outcome == CheckOutcome.FAIL
        ]
        assert len(oracle_fails) == 0
        assert res.is_aligned is True
