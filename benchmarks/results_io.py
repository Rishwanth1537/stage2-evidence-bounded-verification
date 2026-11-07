"""
Per-item results schema, JSONL I/O, manifest generator, and legacy converter.

Follows Stage 2 Prompt 3 specification:
- ResultRow: Strict per-item evaluation record with required cluster_id.
- write_rows / read_rows: Line-delimited JSON I/O with Pydantic validation.
- run_manifest: Provenance tracking (git hash, dirty flag, package versions, dataset SHAs).
- convert_legacy_results: Safe converter for unambiguous legacy benchmark formats.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# Allowed decisions and evidence tiers
DecisionType = Literal["ALLOW", "WARN", "ASK", "BLOCK"]
EvidenceTierType = Literal["E1", "E2", "E3", "E4", "E5"]


class ResultRow(BaseModel):
    """
    Standardized per-item result record across all hallucination checker evaluations.
    """
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(description="Unique evaluation run identifier")
    dataset: str = Field(description="Dataset name (e.g. argground, deref_fcrb, agenthallu)")
    split: str = Field(description="Split name (e.g. dev, test)")
    item_id: str = Field(description="Unique per-item identifier")
    cluster_id: str = Field(
        description="Dialogue, trajectory, or session grouping key (REQUIRED; cannot be empty)"
    )
    label: int = Field(description="Ground truth: 1 = erroneous/unsupported call, 0 = clean/supported call")
    error_class: Optional[str] = Field(default=None, description="Detailed error category or taxonomy label")
    evidence_tier: Optional[str] = Field(default=None, description="Evidence tier (E1..E5)")
    system: str = Field(description="System or model evaluated (e.g. context_checker, claude_opus)")
    system_version: str = Field(default="", description="Version, checkpoint, prompt version, or model identifier")
    decision: Optional[DecisionType] = Field(
        default=None,
        description="Gate decision: ALLOW, WARN, ASK, BLOCK (or None for continuous scorers)",
    )
    score: Optional[float] = Field(default=None, description="Continuous suspicion or consistency score")
    latency_ms: float = Field(default=0.0, description="End-to-end evaluation latency in milliseconds")
    tokens_in: int = Field(default=0, description="Prompt / input token count")
    tokens_out: int = Field(default=0, description="Completion / output token count")
    cost_usd: Optional[float] = Field(default=None, description="Estimated inference cost in USD")
    repeat_idx: int = Field(default=0, description="Repetition index (for multi-pass evaluations)")
    seed: int = Field(default=0, description="Random seed used for this evaluation item")
    degraded: bool = Field(default=False, description="Whether verifier was operating in degraded mode")

    @field_validator("cluster_id")
    @classmethod
    def validate_cluster_id(cls, v: Any) -> str:
        if v is None:
            raise ValueError("cluster_id is required and cannot be None")
        s = str(v).strip()
        if not s:
            raise ValueError("cluster_id cannot be an empty or whitespace string")
        return s

    @field_validator("label")
    @classmethod
    def validate_label(cls, v: Any) -> int:
        if v not in (0, 1):
            raise ValueError(f"label must be binary 0 or 1, got {v}")
        return int(v)

    @field_validator("evidence_tier")
    @classmethod
    def validate_evidence_tier(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v_clean = v.strip().upper()
        if not re.match(r"^E[1-5]$", v_clean):
            raise ValueError(f"evidence_tier must match E1..E5 if provided, got {v}")
        return v_clean


def write_rows(
    path: Union[Path, str],
    rows: Sequence[Union[ResultRow, Dict[str, Any]]],
    append: bool = False,
) -> int:
    """
    Validate and write a sequence of ResultRow objects to a JSONL file.
    Rejects rows without cluster_id.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"

    count = 0
    with p.open(mode, encoding="utf-8") as f:
        for r in rows:
            if isinstance(r, ResultRow):
                row_obj = r
            elif isinstance(r, dict):
                row_obj = ResultRow.model_validate(r)
            else:
                raise TypeError(f"Expected ResultRow or dict, got {type(r)}")

            f.write(row_obj.model_dump_json() + "\n")
            count += 1

    return count


def read_rows(path: Union[Path, str]) -> List[ResultRow]:
    """
    Read and validate ResultRow objects from a JSONL file.
    Raises ValueError / ValidationError on invalid rows or missing cluster_id.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Result file not found: {p}")

    results: List[ResultRow] = []
    with p.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            s = line.strip()
            if not s:
                continue
            try:
                row = ResultRow.model_validate_json(s)
                results.append(row)
            except Exception as e:
                raise ValueError(f"Invalid ResultRow at {p}:{line_no}: {e}") from e

    return results


def _get_git_info() -> Tuple[str, bool]:
    """Return (git_hash, is_dirty)."""
    try:
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
    except Exception:
        git_hash = "unknown"

    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
        is_dirty = bool(status)
    except Exception:
        is_dirty = False

    return git_hash, is_dirty


def _get_package_versions() -> Dict[str, str]:
    """Collect installed versions of core project dependencies."""
    packages = [
        "spacy",
        "torch",
        "transformers",
        "pydantic",
        "scipy",
        "numpy",
        "networkx",
        "fastmcp",
        "datasets",
        "statsmodels",
    ]
    versions: Dict[str, str] = {}
    for pkg in packages:
        try:
            versions[pkg] = importlib.metadata.version(pkg)
        except Exception:
            versions[pkg] = "not_installed"
    return versions


def _compute_sha256(path: Union[Path, str]) -> str:
    """Compute hex SHA-256 digest of a file."""
    p = Path(path)
    if not p.is_file():
        return "file_not_found"
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def run_manifest(
    output_path: Union[Path, str],
    config: Optional[Dict[str, Any]] = None,
    dataset_paths: Optional[Dict[str, Union[Path, str]]] = None,
    dataset_shas: Optional[Dict[str, str]] = None,
    seed: int = 0,
    start_time: Optional[Union[str, datetime]] = None,
    end_time: Optional[Union[str, datetime]] = None,
    **extra_meta: Any,
) -> Dict[str, Any]:
    """
    Generate and save manifest.json tracking provenance:
    - config dictionary
    - git hash and dirty flag
    - package versions
    - dataset SHA-256 digests
    - seed
    - start and end timestamps (ISO 8601 UTC)
    """
    out = Path(output_path)
    if out.is_dir() or not out.suffix:
        out.mkdir(parents=True, exist_ok=True)
        manifest_file = out / "manifest.json"
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        manifest_file = out

    git_hash, dirty = _get_git_info()
    packages = _get_package_versions()

    # Calculate dataset SHAs
    shas: Dict[str, str] = {}
    if dataset_shas:
        shas.update(dataset_shas)
    if dataset_paths:
        for name, p in dataset_paths.items():
            shas[name] = _compute_sha256(p)

    now_iso = datetime.now(timezone.utc).isoformat()
    s_time = start_time.isoformat() if isinstance(start_time, datetime) else (start_time or now_iso)
    e_time = end_time.isoformat() if isinstance(end_time, datetime) else (end_time or now_iso)

    manifest_data: Dict[str, Any] = {
        "manifest_version": "1.0",
        "generated_at": now_iso,
        "git_hash": git_hash,
        "dirty": dirty,
        "seed": seed,
        "start_time": s_time,
        "end_time": e_time,
        "config": config or {},
        "package_versions": packages,
        "dataset_shas": shas,
        **extra_meta,
    }

    with manifest_file.open("w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, sort_keys=True)

    return manifest_data


def convert_legacy_results(
    input_path: Union[Path, str],
    output_path: Optional[Union[Path, str]] = None,
    default_system: Optional[str] = None,
    default_split: str = "dev",
) -> Tuple[List[ResultRow], Dict[str, Any]]:
    """
    Safely convert legacy benchmark result files into the ResultRow format.
    ONLY converts files where the per-item mapping and cluster_id are UNAMBIGUOUS.
    Files holding aggregates only (e.g. argground_dev_results.json) or ambiguous mappings
    are cleanly skipped and documented; test splits are never re-run.

    Returns:
        (converted_rows, report_dict)
    """
    p = Path(input_path)
    if not p.is_file():
        return [], {"path": str(p), "status": "error", "reason": "File not found"}

    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return [], {"path": str(p), "status": "error", "reason": f"JSON decode error: {e}"}

    # Case 1: Aggregate-only dictionaries
    if isinstance(data, dict):
        # Known aggregate-only keys
        if "methods" in data and ("split" in data or "n" in data):
            return [], {
                "path": str(p),
                "status": "skipped",
                "reason": "Aggregate-only summary without per-item records (argground format)",
            }
        if "n_instances" in data and "n_wrong" in data and "rows" not in data:
            return [], {
                "path": str(p),
                "status": "skipped",
                "reason": "Aggregate-only summary without per-item records (consensus format)",
            }
        if "accuracy" in data and "precision" in data and "rows" not in data:
            return [], {
                "path": str(p),
                "status": "skipped",
                "reason": "Aggregate-only metrics without per-item records",
            }

    converted: List[ResultRow] = []
    run_id = p.stem

    # Case 2: LLM judge format (`llm_judge_args_*.json`)
    # Metadata keys: provider, model, split, variant, rows
    # Row keys: id, query_id, label, parsed, supported, unsupported_arguments, latency_s, prompt_tokens, completion_tokens
    if isinstance(data, dict) and "rows" in data and isinstance(data["rows"], list):
        rows = data["rows"]
        if rows and isinstance(rows[0], dict) and "query_id" in rows[0]:
            sys_name = default_system or data.get("model") or data.get("provider") or "llm_judge"
            sys_ver = str(data.get("variant", data.get("prompt_hash", "")))
            split_name = data.get("split", default_split)
            seed = int(data.get("seed", 0))

            # Determine dataset from filename / id prefix
            sample_id = str(rows[0].get("id", ""))
            if sample_id.startswith("fcrb"):
                ds_name = "fcrb"
            elif sample_id.startswith("cfb"):
                ds_name = "cfb"
            elif "agenthallu" in run_id or sample_id.startswith("ah"):
                ds_name = "agenthallu"
            else:
                ds_name = "llm_judge_benchmark"

            for item in rows:
                query_id = str(item.get("query_id", "")).strip()
                item_id = str(item.get("id", "")).strip()
                if not query_id or not item_id:
                    continue

                raw_lbl = item.get("label")
                if isinstance(raw_lbl, bool):
                    lbl = 1 if raw_lbl else 0
                else:
                    lbl = int(raw_lbl) if raw_lbl is not None else 0

                # In judge format: parsed=False or supported=False means error was flagged (decision=BLOCK)
                # supported=True means clean (decision=ALLOW)
                parsed = bool(item.get("parsed", True))
                supported = bool(item.get("supported", True))
                if not parsed or not supported:
                    decision = "BLOCK"
                else:
                    decision = "ALLOW"

                lat_s = item.get("latency_s")
                lat_ms = float(lat_s * 1000.0) if (lat_s is not None and lat_s >= 0) else 0.0
                tok_in = int(item.get("prompt_tokens", 0) or 0)
                tok_out = int(item.get("completion_tokens", 0) or 0)

                row = ResultRow(
                    run_id=run_id,
                    dataset=ds_name,
                    split=split_name,
                    item_id=item_id,
                    cluster_id=query_id,
                    label=lbl,
                    system=sys_name,
                    system_version=sys_ver,
                    decision=decision,
                    latency_ms=lat_ms,
                    tokens_in=tok_in,
                    tokens_out=tok_out,
                    seed=seed,
                    degraded=False,
                )
                converted.append(row)

            if output_path:
                write_rows(output_path, converted)

            return converted, {
                "path": str(p),
                "status": "converted",
                "format": "llm_judge_args",
                "count": len(converted),
            }

    # Case 3: Other files without an unambiguous cluster_id mapping
    return [], {
        "path": str(p),
        "status": "skipped",
        "reason": "Missing cluster_id grouping or ambiguous label direction; skipped without guessing",
    }
