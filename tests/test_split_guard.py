"""
Unit tests for test-split guards and deterministic membership.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from unittest.mock import patch
import pytest

from benchmarks.splits import (
    LockedSplitError,
    append_ledger_entry,
    check_test_guard,
    load_split,
)
import benchmarks.eval_argground as eval_argground
import benchmarks.external_eval as external_eval


def test_locked_split_error_without_locked_run_env(monkeypatch):
    """Attempting to load a test split without LOCKED_RUN=1 must raise LockedSplitError."""
    monkeypatch.delenv("LOCKED_RUN", raising=False)
    with pytest.raises(LockedSplitError, match="requires LOCKED_RUN=1"):
        load_split("argground", split="test", purpose="unit test", reason="testing guard", allow_test=True)


def test_locked_split_error_without_allow_test_flag(monkeypatch):
    """Attempting to load a test split with allow_test=False must raise LockedSplitError."""
    monkeypatch.setenv("LOCKED_RUN", "1")
    with pytest.raises(LockedSplitError, match="without --allow-test"):
        load_split("argground", split="test", purpose="unit test", reason="testing guard", allow_test=False)


def test_locked_split_error_without_reason(monkeypatch):
    """Attempting to load a test split without a non-empty reason must raise LockedSplitError."""
    monkeypatch.setenv("LOCKED_RUN", "1")
    with pytest.raises(LockedSplitError, match="requires a non-empty reason"):
        load_split("argground", split="test", purpose="", reason="", allow_test=True)


def test_dev_split_loads_freely_and_never_writes_to_ledger(tmp_path, monkeypatch):
    """Dev split loading must succeed without env vars and must never write to the ledger."""
    monkeypatch.delenv("LOCKED_RUN", raising=False)
    test_ledger = tmp_path / "test_ledger.jsonl"

    cases = load_split("argground", split="dev", ledger_path=test_ledger)
    assert len(cases) == 1753
    assert all(c.get("split") == "dev" for c in cases)
    assert not test_ledger.exists()


def test_ledger_line_appended_when_authorized(tmp_path, monkeypatch):
    """When authorized, ledger entry is appended with expected metadata schema."""
    monkeypatch.setenv("LOCKED_RUN", "1")
    test_ledger = tmp_path / "custom_ledger.jsonl"

    entry = append_ledger_entry(
        dataset_name="mock_dataset",
        split="test",
        file_sha256="abc123sha",
        purpose="audit test run",
        reason="authorized pre-registration verification",
        caller="test_caller.py",
        ledger_path=test_ledger,
    )

    assert test_ledger.exists()
    lines = test_ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])

    assert parsed["dataset"] == "mock_dataset"
    assert parsed["split"] == "test"
    assert parsed["sha256"] == "abc123sha"
    assert parsed["purpose"] == "audit test run"
    assert parsed["reason"] == "authorized pre-registration verification"
    assert parsed["caller"] == "test_caller.py"
    assert "when" in parsed
    assert "timestamp" in parsed
    assert "git_commit" in parsed
    assert "dirty" in parsed


def test_membership_deterministic():
    """Repeated split partition of argground must be byte-for-byte identical."""
    cases_1 = load_split("argground", split="dev")
    cases_2 = load_split("argground", split="dev")

    assert len(cases_1) == 1753
    assert len(cases_2) == 1753
    assert [c["id"] for c in cases_1] == [c["id"] for c in cases_2]


def test_eval_argground_defaults_to_dev():
    """eval_argground parser must default --split to 'dev'."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev", choices=["dev", "test", "all"])
    parser.add_argument("--allow-test", action="store_true")
    parser.add_argument("--note", default="")
    args = parser.parse_args([])

    assert args.split == "dev"
    assert args.allow_test is False


def test_external_eval_defaults_to_dev():
    """external_eval parser must default --split to 'dev'."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev", choices=("dev", "test"))
    parser.add_argument("--allow-test", action="store_true")
    parser.add_argument("--note", default="")
    args = parser.parse_args([])

    assert args.split == "dev"
    assert args.allow_test is False


def test_mcpatlas_x1_heldout_locked(monkeypatch):
    """mcpatlas_x1 heldout must raise LockedSplitError without LOCKED_RUN=1."""
    monkeypatch.delenv("LOCKED_RUN", raising=False)
    with pytest.raises(LockedSplitError, match="requires LOCKED_RUN=1"):
        load_split("mcpatlas_x1", split="heldout", purpose="unit test", reason="testing guard")


def test_mcpatlas_x1_dev_loads_without_ledger(tmp_path, monkeypatch):
    """mcpatlas_x1 dev loads freely and never writes to the ledger."""
    monkeypatch.delenv("LOCKED_RUN", raising=False)
    test_ledger = tmp_path / "test_ledger.jsonl"
    dev_cases = load_split("mcpatlas_x1", split="dev", ledger_path=test_ledger)
    assert len(dev_cases) == 1697
    assert all(c.get("split") == "dev" for c in dev_cases)
    assert not test_ledger.exists()



def test_agenthallu_confirmatory_slice_is_locked(monkeypatch):
    """The frozen agenthallu confirmatory slice must raise LockedSplitError without LOCKED_RUN=1."""
    monkeypatch.delenv("LOCKED_RUN", raising=False)
    with pytest.raises(LockedSplitError, match="requires LOCKED_RUN=1"):
        load_split("agenthallu_confirmatory", split="dev")
