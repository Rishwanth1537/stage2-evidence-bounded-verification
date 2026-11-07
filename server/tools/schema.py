"""
Schema alignment tool implementation.
Checks agent_args against a JSON Schema tool definition.
Classifies mismatches as schema (missing field) or format (type mismatch).

Supports two-tier check classification (Prompt 4):
- Core JSON-Schema constraints (type, required, undeclared, enum, pattern, min/max) -> ORACLE_EXACT (E2).
- Free-text parameter description constraints (e.g. 'City, State') -> COVERAGE_BOUNDED (E2).
- Produces structured CheckResult records and overall GatePolicy Decision.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from ..models.schemas import (
    CheckOutcome,
    CheckResult,
    CheckTier,
    Decision,
    HallucinationType,
    MismatchedSpan,
    SchemaAlignmentRequest,
    SchemaAlignmentResponse,
)
from ..pipeline.taxonomy import classify_span
from ..proxy.gate_policy import load_gate_policy
from .. import session as session_module

# JSON Schema → Python type mapping
_TYPE_MAP: Dict[str, type] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}

# Free-text description hints (prose-derived, not machine-authoritative -> COVERAGE_BOUNDED)
_CITY_HINT = re.compile(r"City, State|city and state|e\.g\.,? '?[A-Z][a-z]+, [A-Z]{2}", re.I)
_CITY_OK = re.compile(r"^[^,]+,\s*[A-Z]{2}$")


def _check_type(value: Any, declared_type: str) -> bool:
    py_type = _TYPE_MAP.get(declared_type)
    if py_type is None:
        return True  # unknown type — don't flag
    # bool is subclass of int in Python; treat separately
    if declared_type == "integer" and isinstance(value, bool):
        return False
    return isinstance(value, py_type)


def _validate_field(
    field: str,
    value: Any,
    prop_schema: Dict[str, Any],
    mismatches: List[MismatchedSpan],
    check_results: List[CheckResult],
) -> bool:
    """
    Run all applicable constraints on a single field value.
    Returns True if the field passes all checks.
    Populates check_results with typed CheckResult records.
    """
    ok = True
    declared_type = prop_schema.get("type")

    # 1. Type check (ORACLE_EXACT)
    if declared_type:
        if not _check_type(value, declared_type):
            issue = (
                f"Field '{field}' expected type '{declared_type}' "
                f"but got {type(value).__name__}."
            )
            mismatches.append(MismatchedSpan(
                span=field,
                issue=issue,
                hallucination_type=HallucinationType.FORMAT,
            ))
            check_results.append(CheckResult(
                check_id=f"schema_type:{field}",
                tier=CheckTier.ORACLE_EXACT,
                outcome=CheckOutcome.FAIL,
                evidence_tier="E2",
                arg_path=field,
                reason=issue,
                details={"declared_type": declared_type, "actual_type": type(value).__name__},
            ))
            return False  # further checks on wrong type would be misleading
        else:
            check_results.append(CheckResult(
                check_id=f"schema_type:{field}",
                tier=CheckTier.ORACLE_EXACT,
                outcome=CheckOutcome.PASS,
                evidence_tier="E2",
                arg_path=field,
                reason=f"Type '{declared_type}' matched.",
            ))

    # 2. Enum constraint (ORACLE_EXACT)
    enum_vals = prop_schema.get("enum")
    if enum_vals is not None:
        if value not in enum_vals:
            issue = (
                f"Field '{field}' value {value!r} is not one of the "
                f"allowed enum values: {enum_vals}."
            )
            mismatches.append(MismatchedSpan(
                span=field,
                issue=issue,
                hallucination_type=HallucinationType.FORMAT,
            ))
            check_results.append(CheckResult(
                check_id=f"schema_enum:{field}",
                tier=CheckTier.ORACLE_EXACT,
                outcome=CheckOutcome.FAIL,
                evidence_tier="E2",
                arg_path=field,
                reason=issue,
                details={"allowed_enums": enum_vals, "actual_value": value},
            ))
            ok = False
        else:
            check_results.append(CheckResult(
                check_id=f"schema_enum:{field}",
                tier=CheckTier.ORACLE_EXACT,
                outcome=CheckOutcome.PASS,
                evidence_tier="E2",
                arg_path=field,
            ))

    # 3. String-specific constraints
    if isinstance(value, str):
        pattern = prop_schema.get("pattern")
        if pattern:
            if not re.search(pattern, value):
                issue = (
                    f"Field '{field}' value {value!r} does not match "
                    f"required pattern /{pattern}/."
                )
                mismatches.append(MismatchedSpan(
                    span=field,
                    issue=issue,
                    hallucination_type=HallucinationType.FORMAT,
                ))
                check_results.append(CheckResult(
                    check_id=f"schema_pattern:{field}",
                    tier=CheckTier.ORACLE_EXACT,
                    outcome=CheckOutcome.FAIL,
                    evidence_tier="E2",
                    arg_path=field,
                    reason=issue,
                ))
                ok = False
            else:
                check_results.append(CheckResult(
                    check_id=f"schema_pattern:{field}",
                    tier=CheckTier.ORACLE_EXACT,
                    outcome=CheckOutcome.PASS,
                    evidence_tier="E2",
                    arg_path=field,
                ))

        min_len = prop_schema.get("minLength")
        if min_len is not None:
            if len(value) < min_len:
                issue = f"Field '{field}' is too short (min {min_len} chars)."
                mismatches.append(MismatchedSpan(
                    span=field,
                    issue=issue,
                    hallucination_type=HallucinationType.FORMAT,
                ))
                check_results.append(CheckResult(
                    check_id=f"schema_min_length:{field}",
                    tier=CheckTier.ORACLE_EXACT,
                    outcome=CheckOutcome.FAIL,
                    evidence_tier="E2",
                    arg_path=field,
                    reason=issue,
                ))
                ok = False
            else:
                check_results.append(CheckResult(
                    check_id=f"schema_min_length:{field}",
                    tier=CheckTier.ORACLE_EXACT,
                    outcome=CheckOutcome.PASS,
                    evidence_tier="E2",
                    arg_path=field,
                ))

        max_len = prop_schema.get("maxLength")
        if max_len is not None:
            if len(value) > max_len:
                issue = f"Field '{field}' is too long (max {max_len} chars)."
                mismatches.append(MismatchedSpan(
                    span=field,
                    issue=issue,
                    hallucination_type=HallucinationType.FORMAT,
                ))
                check_results.append(CheckResult(
                    check_id=f"schema_max_length:{field}",
                    tier=CheckTier.ORACLE_EXACT,
                    outcome=CheckOutcome.FAIL,
                    evidence_tier="E2",
                    arg_path=field,
                    reason=issue,
                ))
                ok = False
            else:
                check_results.append(CheckResult(
                    check_id=f"schema_max_length:{field}",
                    tier=CheckTier.ORACLE_EXACT,
                    outcome=CheckOutcome.PASS,
                    evidence_tier="E2",
                    arg_path=field,
                ))

        # Check for free-text description hint (COVERAGE_BOUNDED)
        desc = prop_schema.get("description", "")
        if desc and _CITY_HINT.search(desc):
            if not _CITY_OK.match(value):
                issue = f"Field '{field}' does not match description format requirement 'City, State': {value!r}"
                mismatches.append(MismatchedSpan(
                    span=field,
                    issue=issue,
                    hallucination_type=HallucinationType.FORMAT,
                ))
                check_results.append(CheckResult(
                    check_id=f"schema_desc_city_state:{field}",
                    tier=CheckTier.COVERAGE_BOUNDED,
                    outcome=CheckOutcome.FAIL,
                    evidence_tier="E2",
                    arg_path=field,
                    reason=issue,
                ))
                ok = False
            else:
                check_results.append(CheckResult(
                    check_id=f"schema_desc_city_state:{field}",
                    tier=CheckTier.COVERAGE_BOUNDED,
                    outcome=CheckOutcome.PASS,
                    evidence_tier="E2",
                    arg_path=field,
                ))

    # 4. Numeric-specific: minimum, maximum
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = prop_schema.get("minimum")
        if minimum is not None:
            if value < minimum:
                issue = f"Field '{field}' value {value} is below minimum {minimum}."
                mismatches.append(MismatchedSpan(
                    span=field,
                    issue=issue,
                    hallucination_type=HallucinationType.FORMAT,
                ))
                check_results.append(CheckResult(
                    check_id=f"schema_minimum:{field}",
                    tier=CheckTier.ORACLE_EXACT,
                    outcome=CheckOutcome.FAIL,
                    evidence_tier="E2",
                    arg_path=field,
                    reason=issue,
                ))
                ok = False
            else:
                check_results.append(CheckResult(
                    check_id=f"schema_minimum:{field}",
                    tier=CheckTier.ORACLE_EXACT,
                    outcome=CheckOutcome.PASS,
                    evidence_tier="E2",
                    arg_path=field,
                ))

        maximum = prop_schema.get("maximum")
        if maximum is not None:
            if value > maximum:
                issue = f"Field '{field}' value {value} exceeds maximum {maximum}."
                mismatches.append(MismatchedSpan(
                    span=field,
                    issue=issue,
                    hallucination_type=HallucinationType.FORMAT,
                ))
                check_results.append(CheckResult(
                    check_id=f"schema_maximum:{field}",
                    tier=CheckTier.ORACLE_EXACT,
                    outcome=CheckOutcome.FAIL,
                    evidence_tier="E2",
                    arg_path=field,
                    reason=issue,
                ))
                ok = False
            else:
                check_results.append(CheckResult(
                    check_id=f"schema_maximum:{field}",
                    tier=CheckTier.ORACLE_EXACT,
                    outcome=CheckOutcome.PASS,
                    evidence_tier="E2",
                    arg_path=field,
                ))

    return ok


def run_schema_alignment(
    agent_args: Dict[str, Any],
    tool_schema: Dict[str, Any],
    session_id: Optional[str] = None,
    threshold: float = 0.35,
) -> SchemaAlignmentResponse:
    required_fields: List[str] = tool_schema.get("required", [])
    properties: Dict[str, Any] = tool_schema.get("properties", {})

    total = len(required_fields)
    matched = 0
    mismatches: List[MismatchedSpan] = []
    check_results: List[CheckResult] = []

    # --- 1. Required field checks (ORACLE_EXACT) ---
    for field in required_fields:
        if field not in agent_args:
            issue = f"Required field '{field}' is missing from agent_args."
            mismatches.append(MismatchedSpan(
                span=field,
                issue=issue,
                hallucination_type=HallucinationType.SCHEMA,
            ))
            check_results.append(CheckResult(
                check_id=f"schema_required:{field}",
                tier=CheckTier.ORACLE_EXACT,
                outcome=CheckOutcome.FAIL,
                evidence_tier="E2",
                arg_path=field,
                reason=issue,
            ))
        else:
            prop_schema = properties.get(field, {})
            if _validate_field(field, agent_args[field], prop_schema, mismatches, check_results):
                matched += 1
                check_results.append(CheckResult(
                    check_id=f"schema_required:{field}",
                    tier=CheckTier.ORACLE_EXACT,
                    outcome=CheckOutcome.PASS,
                    evidence_tier="E2",
                    arg_path=field,
                ))

    # --- 2. Optional field checks (present in args) ---
    optional_fields = set(properties.keys()) - set(required_fields)
    for field in optional_fields:
        if field in agent_args:
            prop_schema = properties[field]
            _validate_field(field, agent_args[field], prop_schema, mismatches, check_results)

    # --- 3. Undeclared argument checks (ORACLE_EXACT) ---
    if properties:
        declared_set = set(properties.keys())
        for arg_key in agent_args:
            if arg_key not in declared_set:
                issue = f"Argument '{arg_key}' is not declared in tool schema properties."
                mismatches.append(MismatchedSpan(
                    span=arg_key,
                    issue=issue,
                    hallucination_type=HallucinationType.SCHEMA,
                ))
                check_results.append(CheckResult(
                    check_id=f"schema_undeclared:{arg_key}",
                    tier=CheckTier.ORACLE_EXACT,
                    outcome=CheckOutcome.FAIL,
                    evidence_tier="E2",
                    arg_path=arg_key,
                    reason=issue,
                ))

    schema_drift_score = matched / total if total > 0 else 1.0
    is_aligned = len(mismatches) == 0

    drift_alert: Optional[bool] = None
    session_mean: Optional[float] = None
    if session_id:
        session_module.tracker.record(session_id, schema_drift_score)
        session_mean = session_module.tracker.get_rolling_mean(session_id)
        drift_alert = session_module.tracker.is_drifting(session_id)

    # Evaluate decision using GatePolicy
    policy = load_gate_policy()
    decision, _, _ = policy.evaluate(check_results, agent_args=agent_args)

    return SchemaAlignmentResponse(
        is_aligned=is_aligned,
        schema_drift_score=round(schema_drift_score, 4),
        mismatches=mismatches,
        drift_alert=drift_alert,
        session_mean_score=round(session_mean, 4) if session_mean is not None else None,
        decision=decision,
        check_results=check_results,
    )
