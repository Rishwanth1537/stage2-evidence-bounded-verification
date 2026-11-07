"""Unit tests for constraint extractor and constraint score."""
import pytest
from unittest.mock import patch, MagicMock
from server.pipeline.constraints import compute_constraint_score


def test_zero_constraints_returns_one():
    score, missing = compute_constraint_score([], "anything")
    assert score == 1.0
    assert missing == []


def test_all_preserved():
    constraints = ["Alice", "100"]
    hypothesis = "Alice sends 100 dollars to Bob."
    score, missing = compute_constraint_score(constraints, hypothesis)
    assert score == 1.0
    assert missing == []


def test_all_missing():
    constraints = ["Alice", "100"]
    hypothesis = "Someone transfers money."
    score, missing = compute_constraint_score(constraints, hypothesis)
    assert score == 0.0
    assert set(missing) == {"Alice", "100"}


def test_partial_missing():
    constraints = ["Alice", "100", "Bob"]
    hypothesis = "Alice transfers funds."
    score, missing = compute_constraint_score(constraints, hypothesis)
    # Alice is present, 100 and Bob are missing
    assert score == pytest.approx(1 / 3)
    assert "100" in missing
    assert "Bob" in missing


def test_case_insensitive_match():
    constraints = ["alice"]
    hypothesis = "ALICE sent the message."
    score, missing = compute_constraint_score(constraints, hypothesis)
    assert score == 1.0
