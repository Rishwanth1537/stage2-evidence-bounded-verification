from __future__ import annotations

import sys
import types

import pytest

from benchmarks.external_eval import load_local_pairs, load_public_pairs
from server.pipeline.entailment import _premise_windows


class _FakeDataset:
    column_names = ["doc", "claim", "label", "dataset", "contamination_identifier"]

    def __init__(self, rows):
        self.rows = rows
        self.shuffled_seed = None

    def __len__(self):
        return len(self.rows)

    def __iter__(self):
        return iter(self.rows)

    def shuffle(self, seed):
        self.shuffled_seed = seed
        return _FakeDataset(list(reversed(self.rows)))

    def select(self, indexes):
        return _FakeDataset([self.rows[index] for index in indexes])


def test_load_public_pairs_records_source_and_deterministic_sample(monkeypatch):
    dataset = _FakeDataset([
        {"doc": "doc one", "claim": "claim one", "label": 1,
         "dataset": "source-a", "contamination_identifier": "a"},
        {"doc": "doc two", "claim": "claim two", "label": 0,
         "dataset": "source-b", "contamination_identifier": "b"},
    ])
    fake_datasets = types.SimpleNamespace(
        load_dataset=lambda dataset_id, split: dataset,
    )
    monkeypatch.setitem(sys.modules, "datasets", fake_datasets)

    pairs, metadata = load_public_pairs(split="test", limit=1, seed=7)

    assert len(pairs) == 1
    assert pairs[0]["premise"] == "doc two"
    assert pairs[0]["hypothesis"] == "claim two"
    assert pairs[0]["label"] is False
    assert metadata["dataset_id"] == "lytang/LLM-AggreFact"
    assert metadata["split"] == "test"
    assert metadata["seed"] == 7
    assert metadata["limit"] == 1
    assert metadata["rows_loaded"] == 1


def test_load_public_pairs_rejects_missing_columns(monkeypatch):
    class MissingColumns:
        column_names = ["doc", "claim"]

    fake_datasets = types.SimpleNamespace(
        load_dataset=lambda dataset_id, split: MissingColumns(),
    )
    monkeypatch.setitem(sys.modules, "datasets", fake_datasets)

    with pytest.raises(ValueError, match="missing required columns"):
        load_public_pairs()


def test_load_local_pairs_uses_split_shards(monkeypatch, tmp_path):
    (tmp_path / "test-00000-of-00001.parquet").touch()
    dataset = _FakeDataset([
        {"doc": "local doc", "claim": "local claim", "label": 1,
         "dataset": "source", "contamination_identifier": "id"},
    ])
    calls = []

    def fake_load_dataset(builder, data_files, split):
        calls.append((builder, data_files, split))
        return dataset

    monkeypatch.setitem(
        sys.modules,
        "datasets",
        types.SimpleNamespace(load_dataset=fake_load_dataset),
    )

    pairs, metadata = load_local_pairs(tmp_path, split="test")

    assert pairs[0]["premise"] == "local doc"
    assert metadata["source"] == "local_parquet"
    assert metadata["split"] == "test"
    assert calls[0][0] == "parquet"
    assert calls[0][2] == "train"


def test_premise_windows_overlap_long_documents():
    words = [f"word-{index}" for index in range(300)]

    windows = _premise_windows(" ".join(words))

    assert len(windows) == 3
    assert windows[0].split()[-40:] == windows[1].split()[:40]
