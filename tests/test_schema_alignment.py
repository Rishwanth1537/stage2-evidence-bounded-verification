"""Unit tests for schema alignment tool."""
import pytest
from server.tools.schema import run_schema_alignment
from server.models.schemas import HallucinationType
from server.session.tracker import clear_session


def _schema(required, properties):
    return {"required": required, "properties": properties}


def test_perfect_match_is_aligned():
    schema = _schema(["name", "amount"], {"name": {"type": "string"}, "amount": {"type": "integer"}})
    result = run_schema_alignment({"name": "Alice", "amount": 100}, schema)
    assert result.is_aligned is True
    assert result.schema_drift_score == 1.0
    assert result.mismatches == []


def test_missing_field_is_schema_type():
    schema = _schema(["name", "amount"], {"name": {"type": "string"}, "amount": {"type": "integer"}})
    result = run_schema_alignment({"name": "Alice"}, schema)
    assert result.is_aligned is False
    mismatch = next(m for m in result.mismatches if m.span == "amount")
    assert mismatch.hallucination_type == HallucinationType.SCHEMA


def test_type_mismatch_is_format_type():
    schema = _schema(["amount"], {"amount": {"type": "integer"}})
    result = run_schema_alignment({"amount": "one hundred"}, schema)
    assert result.is_aligned is False
    assert result.mismatches[0].hallucination_type == HallucinationType.FORMAT


def test_no_required_fields_score_is_one():
    schema = _schema([], {})
    result = run_schema_alignment({"extra": "value"}, schema)
    assert result.schema_drift_score == 1.0
    assert result.is_aligned is True


def test_session_score_recorded():
    clear_session("schema_test_session")
    schema = _schema(["x"], {"x": {"type": "string"}})
    result = run_schema_alignment({"x": "hello"}, schema, session_id="schema_test_session")
    assert result.session_mean_score is not None
    assert result.drift_alert is not None


def test_no_session_returns_none_drift():
    schema = _schema(["x"], {"x": {"type": "string"}})
    result = run_schema_alignment({"x": "hello"}, schema)
    assert result.drift_alert is None
    assert result.session_mean_score is None
