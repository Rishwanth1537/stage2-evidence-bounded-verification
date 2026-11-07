"""
End-to-end integration tests using real ML models (no mocks).

Run with:
    pytest tests/test_integration.py -m integration -v

These tests are skipped gracefully if models are not downloaded.
Mark with @pytest.mark.integration so CI can exclude them:
    pytest tests/ -m "not integration"
"""
from __future__ import annotations
import pytest


# Skip entire module if models or spacy are absent
spacy = pytest.importorskip("spacy", reason="spaCy not installed")
transformers = pytest.importorskip("transformers", reason="transformers not installed")

from server.tools.verify_logic import run_verification  # noqa: E402
from server.tools.schema import run_schema_alignment  # noqa: E402


pytestmark = pytest.mark.integration


# ── verify_logic_chain: content cases ────────────────────────────────────────


def test_int_consistent_paraphrase():
    """Paraphrase of the same fact → should be consistent."""
    result = run_verification(
        hypothesis="The company's revenue rose by 20% to $5M in Q3.",
        premise="In Q3, the company saw a 20% increase in revenue, reaching a total of $5M.",
    )
    assert result.is_consistent is True, (
        f"Expected consistent; got score={result.factual_consistency_score}, "
        f"ged={result.ged_normalised}"
    )


def test_int_numeric_hallucination_detected():
    """$500 vs $50 — numeric substitution must be detected."""
    result = run_verification(
        hypothesis="Alice transferred $500 to Bob on Monday.",
        premise="Alice transferred $50 to Bob on Monday.",
    )
    assert result.is_consistent is False, (
        f"Expected inconsistent (numeric hallucination); "
        f"got score={result.factual_consistency_score}, ged={result.ged_normalised}"
    )


def test_int_version_hallucination_detected():
    """v2.4.1 vs v2.4.0 — version substitution must be detected."""
    result = run_verification(
        hypothesis="Deployed version 2.4.1 to production server.",
        premise="Deployed version 2.4.0 to production server.",
    )
    assert result.is_consistent is False, (
        f"Expected inconsistent (version hallucination); "
        f"got score={result.factual_consistency_score}, ged={result.ged_normalised}"
    )


def test_int_action_mismatch_detected():
    """delete vs read — semantic action mismatch must be detected."""
    result = run_verification(
        hypothesis="The agent will call the delete_file tool on path /data/config.json.",
        premise="The user asked the agent to read the file at /data/config.json.",
    )
    assert result.is_consistent is False, (
        f"Expected inconsistent (action mismatch); "
        f"got score={result.factual_consistency_score}, ged={result.ged_normalised}"
    )


def test_int_consistent_tool_call():
    """Correct tool/doc ID paraphrase → consistent."""
    result = run_verification(
        hypothesis="I will use the extract_text tool on document ID 456.",
        premise="The user requested text extraction for document ID 456.",
    )
    assert result.is_consistent is True, (
        f"Expected consistent; got score={result.factual_consistency_score}, "
        f"ged={result.ged_normalised}"
    )


# ── verify_schema_alignment: schema / format cases ───────────────────────────


def test_int_schema_missing_field():
    """Missing required field → schema mismatch."""
    from server.models.schemas import HallucinationType
    result = run_schema_alignment(
        agent_args={"product_id": 88},
        tool_schema={
            "required": ["product_id", "quantity", "address"],
            "properties": {
                "product_id": {"type": "integer"},
                "quantity": {"type": "integer"},
                "address": {"type": "string"},
            },
        },
    )
    assert result.is_aligned is False
    schema_mismatches = [
        m for m in result.mismatches
        if m.hallucination_type == HallucinationType.SCHEMA
    ]
    assert len(schema_mismatches) >= 2, (
        f"Expected ≥2 schema mismatches (quantity, address); got {result.mismatches}"
    )


def test_int_format_type_mismatch():
    """Wrong type for field → format mismatch."""
    from server.models.schemas import HallucinationType
    result = run_schema_alignment(
        agent_args={"quantity": "five", "price": "twenty dollars"},
        tool_schema={
            "required": ["quantity", "price"],
            "properties": {
                "quantity": {"type": "integer"},
                "price": {"type": "number"},
            },
        },
    )
    assert result.is_aligned is False
    format_mismatches = [
        m for m in result.mismatches
        if m.hallucination_type == HallucinationType.FORMAT
    ]
    assert len(format_mismatches) == 2, (
        f"Expected 2 format mismatches; got {result.mismatches}"
    )


def test_int_schema_fully_aligned():
    """All required fields present and correct type → aligned."""
    result = run_schema_alignment(
        agent_args={"to": "alice@corp.com", "subject": "Report", "body": "See attached."},
        tool_schema={
            "required": ["to", "subject", "body"],
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
        },
    )
    assert result.is_aligned is True
    assert result.schema_drift_score == pytest.approx(1.0)
