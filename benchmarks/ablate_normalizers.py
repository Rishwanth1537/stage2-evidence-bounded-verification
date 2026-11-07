"""
benchmarks/ablate_normalizers.py: Normalizer ablation harness (Prompt 5).

Evaluates the contribution of each typed normalizer in server/pipeline/arg_ground.py
on DEV DATA ONLY across:
- ArgGround dev
- DeRef fcrb dev
- DeRef cfb dev
- Clean-call subset of MCP-Atlas on disk

Configs:
- all-on (default, all normalizers active)
- all-off (exact match only)
- leave-one-out (8 configs, one switch disabled at a time)
- add-one-in (8 configs, from all-off, one switch enabled at a time)

Outputs:
- ResultRow JSONLs under review/ablation_dev/
- Markdown report with raw metrics, 95% CIs, and paired differences vs all-on with cluster-bootstrap CIs.
- Top 30 most frequent false blocks under all-on with nearest context span.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmarks.results_io import ResultRow, read_rows, write_rows  # noqa: E402
from benchmarks.splits import load_split  # noqa: E402
from benchmarks.stats import cluster_bootstrap_ci, paired_cluster_bootstrap_diff  # noqa: E402
from server.models.schemas import CheckOutcome, CheckResult, CheckTier, Decision  # noqa: E402
from server.pipeline.arg_ground import (  # noqa: E402
    GroundingConfig,
    check_arguments,
)
from server.proxy.gate_policy import GatePolicy  # noqa: E402
from server.tools.schema import run_schema_alignment  # noqa: E402


SWITCH_NAMES = [
    "spelled_numbers",
    "numeric_formats",
    "iso_dates",
    "spoken_dates_times",
    "currency_equivalence",
    "stemming",
    "fuzzy_match",
    "token_set_containment",
]


def _format_ci(val: float, low: float, high: float, decimals: int = 3) -> str:
    return f"{val:.{decimals}f} [{low:.{decimals}f}, {high:.{decimals}f}]"


def _format_diff(diff: float, low: float, high: float, decimals: int = 3) -> str:
    sign = "+" if diff > 0 else ""
    return f"{sign}{diff:.{decimals}f} [{low:.{decimals}f}, {high:.{decimals}f}]"


def _load_deref_schema_notes(dataset_name: str) -> Dict[str, Dict[str, Any]]:
    """Extract embedded tool schemas from cases_schema_note.json if present."""
    note_path = ROOT / "benchmarks" / "data" / "deref" / f"cases_{dataset_name}_schema_note.json"
    schemas: Dict[str, Dict[str, Any]] = {}
    if not note_path.exists():
        return schemas

    try:
        with note_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        for c in data.get("cases", []):
            cid = c.get("id")
            premise = c.get("premise", "")
            if "Tool definition" in premise:
                m = re.search(r"Tool definition[^\n]*\n(\{.*\})", premise, re.DOTALL)
                if m:
                    try:
                        s_obj = json.loads(m.group(1))
                        params = s_obj.get("parameters", {})
                        if "properties" in params:
                            schemas[cid] = params
                    except Exception:
                        pass
    except Exception:
        pass
    return schemas


def find_nearest_context_span(val: Any, text: str) -> Tuple[str, float]:
    """
    Find the window in text with the highest string similarity to val.
    """
    val_str = str(val).strip()
    if not val_str or not text.strip():
        return "", 0.0

    toks = text.split()
    if not toks:
        return "", 0.0

    val_toks = val_str.split()
    n = max(1, len(val_toks))
    best_ratio, best_span = -1.0, ""

    # Check windows of size [n-1, n, n+1]
    for w in range(max(1, n - 1), min(len(toks) + 1, n + 3)):
        for i in range(len(toks) - w + 1):
            cand = " ".join(toks[i : i + w])
            r = SequenceMatcher(None, val_str.lower(), cand.lower()).ratio()
            if r > best_ratio:
                best_ratio, best_span = r, cand
            if best_ratio >= 1.0:
                return best_span, 1.0

    return best_span, round(best_ratio, 3)


def get_ablation_configs() -> Dict[str, GroundingConfig]:
    """Construct all 18 ablation configurations."""
    configs: Dict[str, GroundingConfig] = {
        "all-on": GroundingConfig.all_on(),
        "all-off": GroundingConfig.all_off(),
    }
    # Leave-one-out (all on except switch s)
    for s in SWITCH_NAMES:
        configs[f"loo_{s}"] = GroundingConfig.leave_one_out(s)

    # Add-one-in (all off except switch s)
    for s in SWITCH_NAMES:
        configs[f"aoi_{s}"] = GroundingConfig.add_one_in(s)

    return configs


def evaluate_case(
    case: Dict[str, Any],
    dataset_name: str,
    config: GroundingConfig,
    policy: GatePolicy,
    deref_schemas: Dict[str, Dict[str, Any]],
) -> Tuple[Decision, List[CheckResult], List[Tuple[str, Any]]]:
    """
    Evaluate a single benchmark case under a specific GroundingConfig and GatePolicy.
    Returns (decision, check_results, ungrounded_args).
    """
    premise = case.get("premise", "")
    call = case.get("call") or (case.get("calls", [{}])[0])
    args = call.get("arguments", {})

    check_results: List[CheckResult] = []
    ungrounded_args: List[Tuple[str, Any]] = []

    # 1. Argument Grounding
    verdicts = check_arguments(args, premise, config=config)
    for v in verdicts:
        if v.verdict == "UNCHECKABLE":
            check_results.append(CheckResult(
                check_id=f"arg_ground:{v.argument}",
                tier=CheckTier.UNCHECKABLE,
                outcome=CheckOutcome.ABSTAIN,
                evidence_tier="E1",
                arg_path=v.argument,
                reason=v.reason or "boolean, null, or empty value",
            ))
        elif v.verdict == "GROUNDED":
            check_results.append(CheckResult(
                check_id=f"arg_ground:{v.argument}",
                tier=CheckTier.COVERAGE_BOUNDED,
                outcome=CheckOutcome.PASS,
                evidence_tier="E1",
                arg_path=v.argument,
                reason="Value is supported by context.",
            ))
        else:  # UNGROUNDED
            ungrounded_args.append((v.argument, v.value))
            check_results.append(CheckResult(
                check_id=f"arg_ground:{v.argument}",
                tier=CheckTier.COVERAGE_BOUNDED,
                outcome=CheckOutcome.FAIL,
                evidence_tier="E1",
                arg_path=v.argument,
                reason=v.reason or f"Argument '{v.argument}' value {v.value!r} not supported by context.",
            ))

    # 2. Schema check (ORACLE_EXACT E2) if present
    case_id = case.get("id", "")
    schema = deref_schemas.get(case_id)
    if schema:
        schema_res = run_schema_alignment(agent_args=args, tool_schema=schema)
        check_results.extend(schema_res.check_results)

    # 3. Gate Policy decision
    decision, _, _ = policy.evaluate(check_results, agent_args=args)
    return decision, check_results, ungrounded_args


def run_ablation(
    output_dir: Path,
    B: int = 1000,
    seed: int = 42,
) -> Tuple[Dict[str, Dict[str, List[ResultRow]]], List[Dict[str, Any]]]:
    """
    Run ablation across all 18 configs on ArgGround, DeRef fcrb, DeRef cfb, and MCP-Atlas.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    configs = get_ablation_configs()
    policy = GatePolicy(legacy_blocking=False, coverage_fail_decision=Decision.ASK, oracle_fail_decision=Decision.BLOCK)

    datasets = ["argground", "deref_fcrb", "deref_cfb", "mcpatlas"]
    schemas_fcrb = _load_deref_schema_notes("fcrb")
    schemas_cfb = _load_deref_schema_notes("cfb")

    all_dataset_rows: Dict[str, Dict[str, List[ResultRow]]] = {}
    all_on_false_blocks: List[Dict[str, Any]] = []

    for ds in datasets:
        print(f"\n--- Loading {ds} dev split ---")
        if ds == "argground":
            raw_cases = load_split("argground", "dev")
            schemas = {}
        elif ds == "deref_fcrb":
            raw_cases = load_split("fcrb", "dev")
            schemas = schemas_fcrb
        elif ds == "deref_cfb":
            raw_cases = load_split("cfb", "dev")
            schemas = schemas_cfb
        elif ds == "mcpatlas":
            raw_cases = load_split("benchmarks/data/mcpatlas/cases.json", "dev")
            schemas = {}
        else:
            raise ValueError(f"Unknown dataset {ds}")

        print(f"Loaded {len(raw_cases)} cases for {ds}")
        ds_rows_by_config: Dict[str, List[ResultRow]] = {}

        for cfg_name, cfg in configs.items():
            out_file = output_dir / f"ablate_{ds}_{cfg_name}.jsonl"
            if out_file.exists():
                print(f"  [{ds}] {cfg_name:<25} loading existing {out_file.name}")
                rows = read_rows(out_file)
                ds_rows_by_config[cfg_name] = rows
                continue

            t0 = time.time()
            rows: List[ResultRow] = []

            for case in raw_cases:
                cid = str(case.get("id", ""))
                # Cluster id: premise for argground/mcpatlas, dialogue_id for deref
                if ds in ("argground", "mcpatlas"):
                    cluster_id = str(case.get("premise", cid))
                else:
                    cluster_id = str(case.get("dialogue_id", cid))

                # Binary label: 1 = error/hallucinated, 0 = clean
                # In argground: case["label"] is True for clean, False for changed
                # In deref: case["label"] is True for clean, False for buggy
                # In mcpatlas: all clean (case["label"] == True)
                if ds == "mcpatlas":
                    binary_label = 0
                else:
                    binary_label = 0 if case.get("label", True) else 1

                dec, checks, ungrounded = evaluate_case(
                    case=case,
                    dataset_name=ds,
                    config=cfg,
                    policy=policy,
                    deref_schemas=schemas,
                )

                # Record false block for "Where the checker is wrong" under all-on
                if cfg_name == "all-on" and binary_label == 0 and ungrounded:
                    premise = case.get("premise", "")
                    for u_arg, u_val in ungrounded:
                        span, sim = find_nearest_context_span(u_val, premise)
                        all_on_false_blocks.append({
                            "dataset": ds,
                            "item_id": cid,
                            "argument": u_arg,
                            "value": u_val,
                            "nearest_span": span,
                            "similarity": sim,
                        })

                row = ResultRow(
                    run_id=f"ablate_{ds}_{cfg_name}",
                    dataset=ds,
                    split="dev",
                    item_id=cid,
                    cluster_id=cluster_id,
                    label=binary_label,
                    system="arg_ground_normalizer",
                    system_version=cfg_name,
                    decision=dec.value,
                    latency_ms=round((time.time() - t0) * 1000.0 / max(1, len(raw_cases)), 3),
                )
                rows.append(row)

            ds_rows_by_config[cfg_name] = rows
            write_rows(out_file, rows)
            print(f"  [{ds}] {cfg_name:<25} ({len(rows)} cases) done in {time.time() - t0:.2f}s")

        all_dataset_rows[ds] = ds_rows_by_config

        # If false blocks were not populated (loaded from disk), populate from all-on
        if not any(fb["dataset"] == ds for fb in all_on_false_blocks):
            print(f"  Extracting top false blocks under all-on for {ds}...")
            all_on_rows = ds_rows_by_config["all-on"]
            flagged_clean_ids = {r.item_id for r in all_on_rows if r.label == 0 and r.decision in ("ASK", "BLOCK")}
            for case in raw_cases:
                cid = str(case.get("id", ""))
                if cid in flagged_clean_ids:
                    premise = case.get("premise", "")
                    call = case.get("call") or (case.get("calls", [{}])[0])
                    args = call.get("arguments", {})
                    verdicts = check_arguments(args, premise, config=configs["all-on"])
                    for v in verdicts:
                        if v.verdict == "UNGROUNDED":
                            span, sim = find_nearest_context_span(v.value, premise)
                            all_on_false_blocks.append({
                                "dataset": ds,
                                "item_id": cid,
                                "argument": v.argument,
                                "value": v.value,
                                "nearest_span": span,
                                "similarity": sim,
                            })

    return all_dataset_rows, all_on_false_blocks


def compute_metrics_and_diffs(
    all_dataset_rows: Dict[str, Dict[str, List[ResultRow]]],
    B: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Vectorized computation of point estimates, cluster bootstrap 95% CIs,
    and paired differences vs all-on with paired cluster-bootstrap CIs.
    """
    results: Dict[str, Any] = {}

    for ds, configs in all_dataset_rows.items():
        results[ds] = {}
        all_on_rows = configs["all-on"]

        # Deterministic cluster grouping
        clusters = sorted({r.cluster_id for r in all_on_rows})
        c_map = {c: i for i, c in enumerate(clusters)}
        K = len(clusters)

        # Precompute per-cluster count arrays for each config
        cfg_counts: Dict[str, Dict[str, np.ndarray]] = {}
        for cfg_name, rows in configs.items():
            err_n = np.zeros(K, dtype=float)
            err_k = np.zeros(K, dtype=float)
            clean_n = np.zeros(K, dtype=float)
            clean_hb = np.zeros(K, dtype=float)
            clean_int = np.zeros(K, dtype=float)

            for r in rows:
                c_idx = c_map.get(r.cluster_id)
                if c_idx is None:
                    continue
                if r.label == 1:
                    err_n[c_idx] += 1
                    if r.decision in ("ASK", "BLOCK"):
                        err_k[c_idx] += 1
                else:
                    clean_n[c_idx] += 1
                    if r.decision == "BLOCK":
                        clean_hb[c_idx] += 1
                    if r.decision in ("ASK", "BLOCK"):
                        clean_int[c_idx] += 1

            cfg_counts[cfg_name] = {
                "err_n": err_n,
                "err_k": err_k,
                "clean_n": clean_n,
                "clean_hb": clean_hb,
                "clean_int": clean_int,
            }

        # Vectorized resampling
        rng = np.random.default_rng(seed)
        boot_idx = rng.choice(K, size=(B, K), replace=True)

        ao_counts = cfg_counts["all-on"]
        boot_ao_err_n = ao_counts["err_n"][boot_idx].sum(axis=1)
        boot_ao_err_k = ao_counts["err_k"][boot_idx].sum(axis=1)
        boot_ao_det = np.where(boot_ao_err_n > 0, boot_ao_err_k / boot_ao_err_n, 0.0)

        boot_ao_clean_n = ao_counts["clean_n"][boot_idx].sum(axis=1)
        boot_ao_clean_hb = ao_counts["clean_hb"][boot_idx].sum(axis=1)
        boot_ao_hb = np.where(boot_ao_clean_n > 0, boot_ao_clean_hb / boot_ao_clean_n, 0.0)

        boot_ao_clean_int = ao_counts["clean_int"][boot_idx].sum(axis=1)
        boot_ao_int = np.where(boot_ao_clean_n > 0, boot_ao_clean_int / boot_ao_clean_n, 0.0)

        for cfg_name, counts in cfg_counts.items():
            # Detection
            tot_err_n = counts["err_n"].sum()
            tot_err_k = counts["err_k"].sum()
            pt_det = float(tot_err_k / tot_err_n) if tot_err_n > 0 else 0.0

            boot_err_n = counts["err_n"][boot_idx].sum(axis=1)
            boot_err_k = counts["err_k"][boot_idx].sum(axis=1)
            boot_det = np.where(boot_err_n > 0, boot_err_k / boot_err_n, 0.0)
            det_lo = float(np.percentile(boot_det, 2.5)) if tot_err_n > 0 else 0.0
            det_hi = float(np.percentile(boot_det, 97.5)) if tot_err_n > 0 else 0.0

            # Paired diff Detection vs all-on
            diff_det_vals = boot_det - boot_ao_det
            pt_diff_det = float(pt_det - (ao_counts["err_k"].sum() / tot_err_n)) if tot_err_n > 0 else 0.0
            diff_det_lo = float(np.percentile(diff_det_vals, 2.5)) if tot_err_n > 0 else 0.0
            diff_det_hi = float(np.percentile(diff_det_vals, 97.5)) if tot_err_n > 0 else 0.0

            # Hard-block
            tot_clean_n = counts["clean_n"].sum()
            tot_clean_hb = counts["clean_hb"].sum()
            pt_hb = float(tot_clean_hb / tot_clean_n) if tot_clean_n > 0 else 0.0

            boot_clean_n = counts["clean_n"][boot_idx].sum(axis=1)
            boot_clean_hb = counts["clean_hb"][boot_idx].sum(axis=1)
            boot_hb = np.where(boot_clean_n > 0, boot_clean_hb / boot_clean_n, 0.0)
            hb_lo = float(np.percentile(boot_hb, 2.5)) if tot_clean_n > 0 else 0.0
            hb_hi = float(np.percentile(boot_hb, 97.5)) if tot_clean_n > 0 else 0.0

            # Paired diff HB vs all-on
            diff_hb_vals = boot_hb - boot_ao_hb
            pt_diff_hb = float(pt_hb - (ao_counts["clean_hb"].sum() / tot_clean_n)) if tot_clean_n > 0 else 0.0
            diff_hb_lo = float(np.percentile(diff_hb_vals, 2.5)) if tot_clean_n > 0 else 0.0
            diff_hb_hi = float(np.percentile(diff_hb_vals, 97.5)) if tot_clean_n > 0 else 0.0

            # Interruption
            tot_clean_int = counts["clean_int"].sum()
            pt_int = float(tot_clean_int / tot_clean_n) if tot_clean_n > 0 else 0.0

            boot_clean_int = counts["clean_int"][boot_idx].sum(axis=1)
            boot_int = np.where(boot_clean_n > 0, boot_clean_int / boot_clean_n, 0.0)
            int_lo = float(np.percentile(boot_int, 2.5)) if tot_clean_n > 0 else 0.0
            int_hi = float(np.percentile(boot_int, 97.5)) if tot_clean_n > 0 else 0.0

            # Paired diff Interruption vs all-on
            diff_int_vals = boot_int - boot_ao_int
            pt_diff_int = float(pt_int - (ao_counts["clean_int"].sum() / tot_clean_n)) if tot_clean_n > 0 else 0.0
            diff_int_lo = float(np.percentile(diff_int_vals, 2.5)) if tot_clean_n > 0 else 0.0
            diff_int_hi = float(np.percentile(diff_int_vals, 97.5)) if tot_clean_n > 0 else 0.0

            results[ds][cfg_name] = {
                "det": (pt_det, det_lo, det_hi),
                "hb": (pt_hb, hb_lo, hb_hi),
                "interr": (pt_int, int_lo, int_hi),
                "diff_det": (pt_diff_det, diff_det_lo, diff_det_hi),
                "diff_hb": (pt_diff_hb, diff_hb_lo, diff_hb_hi),
                "diff_int": (pt_diff_int, diff_int_lo, diff_int_hi),
            }

    return results


def generate_ablation_report(
    results: Dict[str, Any],
    all_on_false_blocks: List[Dict[str, Any]],
    output_path: Path,
) -> str:
    """Generate Markdown report containing ablation table and top 30 false blocks."""
    lines: List[str] = [
        "# Prompt 5: Normalizer Ablation Report",
        "",
        "Evaluated on DEV DATA ONLY: ArgGround dev, DeRef fcrb dev, DeRef cfb dev, and MCP-Atlas dev.",
        "Paired difference $\\Delta = \\text{Metric}(\\text{config}) - \\text{Metric}(\\text{all-on})$ with 95% paired cluster-bootstrap CIs.",
        "",
        "## 1. Ablation Results Table",
        "",
        "| Dataset | Configuration | Detection [95% CI] | Diff Detection vs all-on [95% CI] | Hard-Block [95% CI] | Interruption [95% CI] | Diff Interruption vs all-on [95% CI] |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]

    neutral_normalizers: Dict[str, List[str]] = {}

    for ds, configs in results.items():
        neutral_normalizers[ds] = []
        for cfg_name, m in configs.items():
            det_s = _format_ci(*m["det"])
            diff_det_s = _format_diff(*m["diff_det"])
            hb_s = _format_ci(*m["hb"])
            int_s = _format_ci(*m["interr"])
            diff_int_s = _format_diff(*m["diff_int"])

            lines.append(
                f"| {ds} | {cfg_name} | {det_s} | {diff_det_s} | {hb_s} | {int_s} | {diff_int_s} |"
            )

            # Check if leave-one-out difference CI for interruption contains zero
            if cfg_name.startswith("loo_"):
                switch = cfg_name[4:]
                _, diff_lo, diff_hi = m["diff_int"]
                if diff_lo <= 0.0 <= diff_hi:
                    neutral_normalizers[ds].append(switch)

    lines.extend([
        "",
        "## 2. Normalizers that Do NOT Statistically Significantly Help (95% CI Contains Zero)",
        "",
        "A normalizer is reported here if removing it (`leave-one-out`) produces a $\\Delta \\text{Interruption}$ whose 95% paired CI includes 0.0:",
        "",
    ])

    for ds, neutrals in neutral_normalizers.items():
        if neutrals:
            lines.append(f"- **{ds}**: {', '.join(sorted(set(neutrals)))}")
        else:
            lines.append(f"- **{ds}**: None (all tested normalizers showed significant effects)")

    lines.extend([
        "",
        "## 3. Top 30 Most Frequent False Blocks under all-on",
        "",
        "Clean calls (`label == 0`) flagged as ungrounded by the checker, with nearest context span found via string/numeric distance.",
        "",
        "| Rank | Dataset | Argument | Value | Count | Nearest Context Span | Similarity Ratio |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ])

    # Count frequency of (dataset, argument, str(value))
    freq = Counter((fb["dataset"], fb["argument"], str(fb["value"])) for fb in all_on_false_blocks)
    top_30 = freq.most_common(30)

    # Map tuple to representative item for span/similarity
    sample_map: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for fb in all_on_false_blocks:
        key = (fb["dataset"], fb["argument"], str(fb["value"]))
        if key not in sample_map:
            sample_map[key] = fb

    for rank, (key, count) in enumerate(top_30, start=1):
        sample = sample_map[key]
        val_clean = str(sample["value"]).replace("|", "\\|").replace("\n", " ")
        if len(val_clean) > 40:
            val_clean = val_clean[:37] + "..."
        span_clean = str(sample["nearest_span"]).replace("|", "\\|").replace("\n", " ")
        if len(span_clean) > 40:
            span_clean = span_clean[:37] + "..."

        lines.append(
            f"| {rank} | {sample['dataset']} | {sample['argument']} | `{val_clean}` | {count} | `{span_clean}` | {sample['similarity']} |"
        )

    lines.append("")
    report_content = "\n".join(lines)
    output_path.write_text(report_content, encoding="utf-8")
    return report_content


def main():
    parser = argparse.ArgumentParser(description="Normalizer ablation harness (Prompt 5).")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "review" / "ablation_dev")
    parser.add_argument("--B", type=int, default=1000, help="Bootstrap iterations (default 1000)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default 42)")
    args = parser.parse_args()

    print("=== Starting Normalizer Ablation (Prompt 5) ===")
    all_dataset_rows, all_on_false_blocks = run_ablation(
        output_dir=args.output_dir,
        B=args.B,
        seed=args.seed,
    )

    print("\nComputing bootstrap CIs and paired differences...")
    results = compute_metrics_and_diffs(all_dataset_rows, B=args.B, seed=args.seed)

    report_path = args.output_dir / "ABLATION_REPORT.md"
    report_md = generate_ablation_report(results, all_on_false_blocks, report_path)
    print(f"\nAblation report written to {report_path}")
    print("\n=== Ablation Report Preview ===\n")
    print(report_md[:2000])


if __name__ == "__main__":
    main()
