"""
Schema alignment tool implementation.
Checks agent_args against a JSON Schema tool definition.
Classifies mismatches as schema (missing field) or format (type mismatch).

L5 fix: Validator now covers the full core JSON Schema subset:
  - required field presence  (schema)
  - type mismatch            (format)
  - enum constraint          (format)
  - pattern constraint       (format, string fields only)
  - minimum / maximum        (format, numeric fields only)
  - minLength / maxLength    (format, string fields only)
  - optional fields present with wrong type are also checked
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional

from ..models.schemas import (
    HallucinationType,
    MismatchedSpan,
    SchemaAlignmentRequest,
    SchemaAlignmentResponse,
)
from ..pipeline.taxonomy import classify_span
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
) -> bool:
    """
    Run all applicable constraints on a single field value.
    Returns True if the field passes all checks (contributes to matched count).
    """
    ok = True

    declared_type = prop_schema.get("type")

    # 1. Type check
    if declared_type and not _check_type(value, declared_type):
        mismatches.append(MismatchedSpan(
            span=field,
            issue=(
                f"Field '{field}' expected type '{declared_type}' "
                f"but got {type(value).__name__}."
            ),
            hallucination_type=HallucinationType.FORMAT,
        ))
        ok = False
        return ok  # further checks on wrong type would be misleading

    # 2. Enum constraint
    enum_vals = prop_schema.get("enum")
    if enum_vals is not None and value not in enum_vals:
        mismatches.append(MismatchedSpan(
            span=field,
            issue=(
                f"Field '{field}' value {value!r} is not one of the "
                f"allowed enum values: {enum_vals}."
            ),
            hallucination_type=HallucinationType.FORMAT,
        ))
        ok = False

    # 3. String-specific: pattern, minLength, maxLength
    if isinstance(value, str):
        pattern = prop_schema.get("pattern")
        if pattern and not re.search(pattern, value):
            mismatches.append(MismatchedSpan(
                span=field,
                issue=(
                    f"Field '{field}' value {value!r} does not match "
                    f"required pattern /{pattern}/."
                ),
                hallucination_type=HallucinationType.FORMAT,
            ))
            ok = False

        min_len = prop_schema.get("minLength")
        if min_len is not None and len(value) < min_len:
            mismatches.append(MismatchedSpan(
                span=field,
                issue=f"Field '{field}' is too short (min {min_len} chars).",
                hallucination_type=HallucinationType.FORMAT,
            ))
            ok = False

        max_len = prop_schema.get("maxLength")
        if max_len is not None and len(value) > max_len:
            mismatches.append(MismatchedSpan(
                span=field,
                issue=f"Field '{field}' is too long (max {max_len} chars).",
                hallucination_type=HallucinationType.FORMAT,
            ))
            ok = False

    # 4. Numeric-specific: minimum, maximum
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = prop_schema.get("minimum")
        if minimum is not None and value < minimum:
            mismatches.append(MismatchedSpan(
                span=field,
                issue=f"Field '{field}' value {value} is below minimum {minimum}.",
                hallucination_type=HallucinationType.FORMAT,
            ))
            ok = False

        maximum = prop_schema.get("maximum")
        if maximum is not None and value > maximum:
            mismatches.append(MismatchedSpan(
                span=field,
                issue=f"Field '{field}' value {value} exceeds maximum {maximum}.",
                hallucination_type=HallucinationType.FORMAT,
            ))
            ok = False

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

    # --- Required field checks ---
    for field in required_fields:
        if field not in agent_args:
            mismatches.append(MismatchedSpan(
                span=field,
                issue=f"Required field '{field}' is missing from agent_args.",
                hallucination_type=HallucinationType.SCHEMA,
            ))
        else:
            prop_schema = properties.get(field, {})
            if _validate_field(field, agent_args[field], prop_schema, mismatches):
                matched += 1

    # --- Optional field checks (present but wrong type/constraint) ---
    optional_fields = set(properties.keys()) - set(required_fields)
    for field in optional_fields:
        if field in agent_args:
            prop_schema = properties[field]
            _validate_field(field, agent_args[field], prop_schema, mismatches)

    schema_drift_score = matched / total if total > 0 else 1.0
    is_aligned = len(mismatches) == 0

    drift_alert: Optional[bool] = None
    session_mean: Optional[float] = None
    if session_id:
        session_module.tracker.record(session_id, schema_drift_score)
        session_mean = session_module.tracker.get_rolling_mean(session_id)
        drift_alert = session_module.tracker.is_drifting(session_id)

    return SchemaAlignmentResponse(
        is_aligned=is_aligned,
        schema_drift_score=round(schema_drift_score, 4),
        mismatches=mismatches,
        drift_alert=drift_alert,
        session_mean_score=round(session_mean, 4) if session_mean is not None else None,
    )
