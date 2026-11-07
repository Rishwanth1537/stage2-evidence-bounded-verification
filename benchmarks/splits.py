"""
benchmarks/splits.py: Dataset split loading and pre-registration test-split guard.

Rules:
- dev and train splits load freely without ledger logging.
- test splits (and the frozen AgentHallu confirmatory slice) raise LockedSplitError
  unless BOTH LOCKED_RUN=1 is set in the environment AND a reason string is provided.
- CLI scripts support the --allow-test flag which maps to this guard.
- When authorized, test access appends a single JSON line to benchmarks/test_run_ledger.jsonl
  recording UTC timestamp, git commit, dirty flag, caller, dataset, sha256, purpose, and reason.
- Split membership is deterministic and exactly matches historical benchmark splits.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = ROOT / "benchmarks" / "test_run_ledger.jsonl"


class LockedSplitError(RuntimeError):
    """Raised when access to a locked test split is attempted without required authorization."""
    pass


def _get_git_info() -> Tuple[str, bool]:
    """Return (commit_hash, is_dirty) for the current repository state."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        commit = "unknown"

    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
        dirty = len(status) > 0
    except Exception:
        dirty = False

    return commit, dirty


def compute_file_sha256(path: Path) -> str:
    """Compute hex SHA-256 digest of a file on disk."""
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def append_ledger_entry(
    dataset_name: str,
    split: str,
    file_sha256: str,
    purpose: str,
    reason: str,
    caller: Optional[str] = None,
    ledger_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Append an authorized test-split run to the test run ledger.
    Never rewrites or modifies existing entries.
    """
    target_ledger = ledger_path or LEDGER_PATH
    now_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    commit, dirty = _get_git_info()
    caller_script = caller or (sys.argv[0] if sys.argv else "unknown")

    entry = {
        "when": now_utc,
        "timestamp": now_utc,
        "git_commit": commit,
        "dirty": dirty,
        "caller": caller_script,
        "script": Path(caller_script).name,
        "dataset": dataset_name,
        "split": split,
        "sha256": file_sha256,
        "purpose": purpose,
        "reason": reason,
        "note": reason,
    }

    target_ledger.parent.mkdir(parents=True, exist_ok=True)
    with target_ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    return entry


def check_test_guard(
    dataset: str,
    split: str,
    purpose: str = "",
    reason: str = "",
    allow_test: bool = True,
) -> None:
    """
    Enforce test split access restrictions.
    Raises LockedSplitError if authorization is missing.
    """
    is_locked = (split == "test") or (dataset in ("agenthallu_confirmatory", "confirmatory"))
    if not is_locked:
        return

    if not allow_test:
        raise LockedSplitError(
            f"Access to test split for '{dataset}' requested without --allow-test flag."
        )

    locked_env = os.environ.get("LOCKED_RUN", "").strip()
    if locked_env != "1":
        raise LockedSplitError(
            f"Access to locked test split for '{dataset}' requires LOCKED_RUN=1 environment variable."
        )

    clean_reason = (reason or purpose or "").strip()
    if not clean_reason:
        raise LockedSplitError(
            f"Access to locked test split for '{dataset}' requires a non-empty reason / note string."
        )


def _split_argground_cases(cases: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Deterministic dev/test split for ArgGround cases.
    Reproduces the exact historical 1753 dev / 1751 test partition.
    """
    rng = random.Random(11)
    ids = sorted({c["premise"] for c in cases})
    rng.shuffle(ids)
    dev_premises = set(ids[: len(ids) // 2])

    dev = []
    test = []
    for c in cases:
        c_copy = dict(c)
        if c["premise"] in dev_premises:
            c_copy["split"] = "dev"
            dev.append(c_copy)
        else:
            c_copy["split"] = "test"
            test.append(c_copy)
    return dev, test


def load_split(
    dataset: str,
    split: str,
    purpose: str = "",
    reason: str = "",
    allow_test: bool = True,
    ledger_path: Optional[Path] = None,
) -> Any:
    """
    Load a dataset split with guard enforcement and deterministic membership.

    Parameters
    ----------
    dataset:
        Dataset identifier: "argground", "fcrb", "cfb", "agenthallu_confirmatory",
        "external", or a path to a json/parquet file.
    split:
        Split name: "dev", "test", "train", or "all".
    purpose:
        Description of why this data is being loaded.
    reason:
        Required authorization reason when split='test'.
    allow_test:
        CLI flag or explicit permission boolean (default True for programmatic calls;
        CLI scripts pass args.allow_test).
    ledger_path:
        Override path to ledger file (used for testing).
    """
    clean_split = split.lower().strip()
    ds_name = dataset.lower().strip()

    # Guard check for test splits or confirmatory slices
    if clean_split == "test" or ds_name in ("agenthallu_confirmatory", "confirmatory"):
        check_test_guard(dataset=dataset, split=clean_split, purpose=purpose, reason=reason, allow_test=allow_test)

    # 1. ArgGround benchmark
    if ds_name in ("argground", "argground_bench", "argground_bench.json") or ds_name.endswith("argground_bench.json"):
        path = ROOT / "benchmarks" / "argground_bench.json"
        if not path.exists():
            path = Path(dataset)
        file_sha256 = compute_file_sha256(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        cases = data.get("cases", [])
        dev, test = _split_argground_cases(cases)

        if clean_split == "test":
            append_ledger_entry(
                dataset_name="argground",
                split="test",
                file_sha256=file_sha256,
                purpose=purpose,
                reason=reason or purpose,
                ledger_path=ledger_path,
            )
            return test
        elif clean_split == "dev":
            return dev
        elif clean_split == "all":
            # If all is requested, test split access is required
            check_test_guard(dataset=dataset, split="test", purpose=purpose, reason=reason, allow_test=allow_test)
            append_ledger_entry(
                dataset_name="argground",
                split="all (dev+test)",
                file_sha256=file_sha256,
                purpose=purpose,
                reason=reason or purpose,
                ledger_path=ledger_path,
            )
            return dev + test
        else:
            raise ValueError(f"Unknown split '{split}' for argground")

    # 2. DeRef benchmarks (fcrb, cfb)
    if ds_name in ("fcrb", "cfb", "deref_fcrb", "deref_cfb") or "cases_" in ds_name:
        sub = "fcrb" if "fcrb" in ds_name else "cfb"
        path = ROOT / "benchmarks" / "data" / "deref" / f"cases_{sub}.json"
        if not path.exists():
            path = Path(dataset)
        file_sha256 = compute_file_sha256(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        cases = [c for c in data.get("cases", []) if c.get("split") == clean_split]

        if clean_split == "test":
            append_ledger_entry(
                dataset_name=f"deref_{sub}",
                split="test",
                file_sha256=file_sha256,
                purpose=purpose,
                reason=reason or purpose,
                ledger_path=ledger_path,
            )
        return cases

    # 3. AgentHallu Confirmatory Slice
    if ds_name in ("agenthallu_confirmatory", "confirmatory", "agenthallu"):
        path = ROOT / "benchmarks" / "agenthallu_confirmatory.json"
        if not path.exists():
            path = ROOT / "benchmarks" / "data" / "agenthallu" / "cases_eval.json"
        file_sha256 = compute_file_sha256(path)
        check_test_guard(dataset="agenthallu_confirmatory", split="test", purpose=purpose, reason=reason, allow_test=allow_test)
        append_ledger_entry(
            dataset_name="agenthallu_confirmatory",
            split="confirmatory",
            file_sha256=file_sha256,
            purpose=purpose,
            reason=reason or purpose,
            ledger_path=ledger_path,
        )
        return json.loads(path.read_text(encoding="utf-8"))

    # 4. External LLM-AggreFact dataset
    if ds_name in ("external", "llm_aggrefact", "aggrefact"):
        if clean_split == "test":
            append_ledger_entry(
                dataset_name="llm_aggrefact",
                split="test",
                file_sha256="",
                purpose=purpose,
                reason=reason or purpose,
                ledger_path=ledger_path,
            )
        return clean_split

    # 5. Generic file path
    p = Path(dataset)
    if p.exists() and p.is_file():
        file_sha256 = compute_file_sha256(p)
        if clean_split == "test":
            append_ledger_entry(
                dataset_name=p.name,
                split="test",
                file_sha256=file_sha256,
                purpose=purpose,
                reason=reason or purpose,
                ledger_path=ledger_path,
            )
        if p.suffix == ".json":
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "cases" in data:
                return [c for c in data["cases"] if c.get("split") == clean_split]
            return data
        return p

    raise ValueError(f"Unknown dataset '{dataset}'")
