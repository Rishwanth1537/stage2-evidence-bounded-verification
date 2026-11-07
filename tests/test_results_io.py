"""
Unit tests for benchmarks/results_io.py.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from benchmarks.results_io import (
    ResultRow,
    convert_legacy_results,
    read_rows,
    run_manifest,
    write_rows,
)


def test_result_row_valid_creation():
    """Verify standard valid ResultRow creation."""
    row = ResultRow(
        run_id="run_001",
        dataset="argground",
        split="dev",
        item_id="item_42",
        cluster_id="dialogue_99",
        label=1,
        system="context_checker",
        system_version="v2.0",
        decision="BLOCK",
        score=0.15,
        latency_ms=12.5,
        tokens_in=100,
        tokens_out=20,
        seed=42,
        degraded=False,
    )
    assert row.cluster_id == "dialogue_99"
    assert row.label == 1
    assert row.decision == "BLOCK"


def test_schema_rejects_missing_or_empty_cluster_id():
    """Schema must strictly reject rows without cluster_id or with empty/whitespace cluster_id."""
    base_dict = {
        "run_id": "run_001",
        "dataset": "argground",
        "split": "dev",
        "item_id": "item_1",
        "label": 0,
        "system": "checker",
        "latency_ms": 10.0,
    }

    # Missing cluster_id
    with pytest.raises(ValidationError):
        ResultRow.model_validate(base_dict)

    # cluster_id = None
    with pytest.raises(ValidationError):
        ResultRow.model_validate({**base_dict, "cluster_id": None})

    # cluster_id = empty string
    with pytest.raises(ValidationError):
        ResultRow.model_validate({**base_dict, "cluster_id": ""})

    # cluster_id = whitespace only
    with pytest.raises(ValidationError):
        ResultRow.model_validate({**base_dict, "cluster_id": "   "})


def test_schema_rejects_invalid_label():
    """Label must be strictly 0 or 1."""
    base_dict = {
        "run_id": "run_001",
        "dataset": "argground",
        "split": "dev",
        "item_id": "item_1",
        "cluster_id": "c1",
        "system": "checker",
    }
    with pytest.raises(ValidationError):
        ResultRow.model_validate({**base_dict, "label": 2})

    with pytest.raises(ValidationError):
        ResultRow.model_validate({**base_dict, "label": -1})


def test_write_and_read_rows_roundtrip(tmp_path: Path):
    """Write rows to JSONL and read them back, asserting round-trip fidelity."""
    jsonl_path = tmp_path / "test_results.jsonl"

    rows = [
        ResultRow(
            run_id="run_a",
            dataset="fcrb",
            split="dev",
            item_id="item_1",
            cluster_id="query_101",
            label=0,
            system="agent_opus",
            decision="ALLOW",
            latency_ms=15.0,
            seed=0,
        ),
        ResultRow(
            run_id="run_a",
            dataset="fcrb",
            split="dev",
            item_id="item_2",
            cluster_id="query_101",
            label=1,
            system="agent_opus",
            decision="BLOCK",
            latency_ms=25.0,
            seed=0,
        ),
    ]

    count = write_rows(jsonl_path, rows)
    assert count == 2
    assert jsonl_path.exists()

    loaded = read_rows(jsonl_path)
    assert len(loaded) == 2
    assert loaded[0].item_id == "item_1"
    assert loaded[0].cluster_id == "query_101"
    assert loaded[1].decision == "BLOCK"


def test_write_rows_rejects_invalid_dict(tmp_path: Path):
    """write_rows must fail if any input dict violates schema."""
    jsonl_path = tmp_path / "bad.jsonl"
    invalid_rows = [
        {"run_id": "r1", "dataset": "d1", "split": "dev", "item_id": "i1"}  # missing cluster_id
    ]
    with pytest.raises(ValidationError):
        write_rows(jsonl_path, invalid_rows)


def test_run_manifest_generation(tmp_path: Path):
    """run_manifest generates valid manifest.json with required fields."""
    dummy_dataset = tmp_path / "dataset.json"
    dummy_dataset.write_text('{"sample": 1}', encoding="utf-8")

    manifest = run_manifest(
        output_path=tmp_path,
        config={"tau": 0.05, "logic_mode": "hybrid"},
        dataset_paths={"sample_data": dummy_dataset},
        seed=42,
    )

    manifest_file = tmp_path / "manifest.json"
    assert manifest_file.exists()
    assert manifest["seed"] == 42
    assert "git_hash" in manifest
    assert "dirty" in manifest
    assert "package_versions" in manifest
    assert "spacy" in manifest["package_versions"]
    assert "sample_data" in manifest["dataset_shas"]
    assert manifest["dataset_shas"]["sample_data"] != "file_not_found"


def test_convert_legacy_results_unambiguous(tmp_path: Path):
    """Convert an existing unambiguous llm_judge_args JSON file."""
    src = Path("benchmarks/llm_judge_args_fcrb_agent_haiku_dev_v0.json")
    if not src.exists():
        pytest.skip(f"Benchmark file {src} not found on disk")

    out_file = tmp_path / "converted_haiku.jsonl"
    rows, report = convert_legacy_results(src, output_path=out_file)

    assert report["status"] == "converted"
    assert len(rows) > 0
    assert out_file.exists()
    assert all(r.cluster_id for r in rows)
    assert all(r.label in (0, 1) for r in rows)


def test_convert_legacy_results_skips_aggregates_without_guessing():
    """Convert must cleanly skip aggregate-only summary files."""
    agg_file = Path("benchmarks/argground_dev_results.json")
    if not agg_file.exists():
        pytest.skip("argground_dev_results.json not found")

    rows, report = convert_legacy_results(agg_file)
    assert rows == []
    assert report["status"] == "skipped"
    assert "Aggregate-only" in report["reason"]
