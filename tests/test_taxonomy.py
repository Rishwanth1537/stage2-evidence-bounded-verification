"""Unit tests for taxonomy classifier."""
import pytest
from server.pipeline.taxonomy import classify_span, classify_all
from server.models.schemas import HallucinationType


def test_missing_field_is_schema():
    assert classify_span("amount", "missing", is_missing_field=True) == HallucinationType.SCHEMA


def test_type_mismatch_is_format():
    assert classify_span("amount", "wrong type", is_type_mismatch=True) == HallucinationType.FORMAT


def test_entailment_miss_is_content():
    assert classify_span("Alice", "low entailment") == HallucinationType.CONTENT


def test_schema_takes_priority_over_format():
    assert classify_span("x", "both", is_missing_field=True, is_type_mismatch=True) == HallucinationType.SCHEMA


def test_classify_all_no_spans():
    assert classify_all([], []) == []


def test_classify_all_assigns_types():
    result = classify_all(
        ["field_a", "field_b", "field_c"],
        ["missing", "wrong type", "not grounded"],
        missing_flags=[True, False, False],
        type_mismatch_flags=[False, True, False],
    )
    assert result[0].hallucination_type == HallucinationType.SCHEMA
    assert result[1].hallucination_type == HallucinationType.FORMAT
    assert result[2].hallucination_type == HallucinationType.CONTENT


def test_classify_all_no_none_types():
    result = classify_all(["a", "b"], ["i1", "i2"])
    for span in result:
        assert span.hallucination_type is not None
        assert span.hallucination_type in list(HallucinationType)
