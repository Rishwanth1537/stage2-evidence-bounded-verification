"""
Frontier Gate Evaluation across Two-Tier Gate Policy Variants (Prompt 4).

Evaluates dev splits only:
- ArgGround dev
- DeRef fcrb dev
- DeRef cfb dev

Across 4 gate policy variants:
1. legacy_blocking: Strict legacy gate (any fail -> BLOCK).
2. ASK-on-coverage: Two-tier gate (Oracle FAIL -> BLOCK, Coverage FAIL -> ASK).
3. WARN-on-coverage: Non-blocking coverage (Oracle FAIL -> BLOCK, Coverage FAIL -> WARN).
4. block-on-oracle-only: Contract only (Oracle FAIL -> BLOCK, Coverage FAIL -> ALLOW).

Reports with 95% Wilson / Cluster-bootstrap CIs:
- Detection rate (ASK or BLOCK)
- Detection rate (BLOCK only)
- Hard-block rate on clean calls (BLOCK on label=0)
- Interruption rate on clean calls (ASK or BLOCK on label=0)
- Youden's J statistic

Strict adherence to Prompt 0:
- Dev splits only via load_split.
- Does not touch the AgentHallu confirmatory slice or test splits.
- Records ResultRow JSONL outputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .results_io import ResultRow, write_rows
from .splits import load_split
from .stats import (
    detection_rate,
    false_block_rate,
    hard_block_rate,
    interruption_rate,
    wilson_ci,
    youden_j,
)
from server.models.schemas import (
    CheckOutcome,
    CheckResult,
    CheckTier,
    Decision,
)
from server.pipeline.arg_ground import check_arguments, check_value
from server.proxy.gate_policy import GatePolicy
from server.tools.schema import run_schema_alignment

ROOT = Path(__file__).resolve().parents[1]


def _format_ci(val: float, low: float, high: float, decimals: int = 3) -> str:
    return f"{val:.{decimals}f} [{low:.{decimals}f}, {high:.{decimals}f}]"


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
                        # Convert to standard JSON Schema properties dict
                        if "properties" in params:
                            schemas[cid] = params
                    except Exception:
                        pass
    except Exception:
        pass
    return schemas


def extract_checks_for_case(
    case: Dict[str, Any],
    dataset_name: str,
    deref_schemas: Dict[str, Dict[str, Any]],
) -> List[CheckResult]:
    """
    Run argument grounding and schema alignment checks on a test case,
    returning structured CheckResult objects categorized by tier.
    """
    check_results: List[CheckResult] = []
    premise = case.get("premise", "")
    call = case.get("call") or (case.get("calls", [{}])[0])
    args = call.get("arguments", {})

    # 1. Argument Grounding Check (COVERAGE_BOUNDED E1 / UNCHECKABLE)
    verdicts = check_arguments(args, premise)
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
            check_results.append(CheckResult(
                check_id=f"arg_ground:{v.argument}",
                tier=CheckTier.COVERAGE_BOUNDED,
                outcome=CheckOutcome.FAIL,
                evidence_tier="E1",
                arg_path=v.argument,
                reason=v.reason or f"Argument '{v.argument}' value {v.value!r} not supported by context.",
            ))

    # 2. Schema / Contract Check (ORACLE_EXACT E2)
    case_id = case.get("id", "")
    schema = deref_schemas.get(case_id)
    if schema:
        schema_res = run_schema_alignment(agent_args=args, tool_schema=schema)
        check_results.extend(schema_res.check_results)

    return check_results


def evaluate_dataset(
    dataset_name: str,
    output_dir: Path,
) -> Dict[str, List[ResultRow]]:
    """
    Evaluate dev split for a dataset across 4 policy variants.
    """
    cases = load_split(dataset_name, "dev")
    deref_schemas = _load_deref_schema_notes("fcrb" if "fcrb" in dataset_name else "cfb")

    policies = {
        "legacy_blocking": GatePolicy(legacy_blocking=True),
        "ASK-on-coverage": GatePolicy(legacy_blocking=False, coverage_fail_decision=Decision.ASK, oracle_fail_decision=Decision.BLOCK),
        "WARN-on-coverage": GatePolicy(legacy_blocking=False, coverage_fail_decision=Decision.WARN, oracle_fail_decision=Decision.BLOCK),
        "block-on-oracle-only": GatePolicy(legacy_blocking=False, coverage_fail_decision=Decision.ALLOW, oracle_fail_decision=Decision.BLOCK),
    }

    variant_rows: Dict[str, List[ResultRow]] = {v: [] for v in policies}

    for idx, case in enumerate(cases):
        item_id = str(case.get("id") or f"{dataset_name}_dev_{idx}")

        # Compute cluster_id (trajectory/query/dialogue grouping)
        if "query_id" in case and case["query_id"]:
            cluster_id = str(case["query_id"]).strip()
        elif "premise_id" in case and case["premise_id"]:
            cluster_id = str(case["premise_id"]).strip()
        else:
            premise_text = case.get("premise", "")
            cluster_id = hashlib.md5(premise_text.encode("utf-8")).hexdigest()[:12]

        # In ArgGround, DeRef fcrb, and DeRef cfb:
        # label=True is genuine/clean call (0); label=False is mutated/error call (1)
        raw_lbl = case.get("label")
        if isinstance(raw_lbl, bool):
            is_error = 1 if not raw_lbl else 0
        else:
            is_error = 1 if raw_lbl in (0, "0", False) else 0

        # Run checks once per case
        check_results = extract_checks_for_case(case, dataset_name, deref_schemas)
        call = case.get("call") or (case.get("calls", [{}])[0])
        args = call.get("arguments", {})

        # Evaluate decisions under each policy variant
        for v_name, policy in policies.items():
            decision, clarification, reasons = policy.evaluate(check_results, agent_args=args)

            row = ResultRow(
                run_id=f"frontier_{dataset_name}_{v_name}",
                dataset=dataset_name,
                split="dev",
                item_id=item_id,
                cluster_id=cluster_id,
                label=is_error,
                system=v_name,
                system_version="p4_frontier",
                decision=decision.value,
                latency_ms=0.5,
                tokens_in=0,
                tokens_out=0,
                seed=0,
                degraded=False,
            )
            variant_rows[v_name].append(row)

    # Save rows
    output_dir.mkdir(parents=True, exist_ok=True)
    for v_name, rows in variant_rows.items():
        out_file = output_dir / f"frontier_{dataset_name}_{v_name}.jsonl"
        write_rows(out_file, rows)

    return variant_rows


def build_frontier_table(all_results: Dict[str, Dict[str, List[ResultRow]]]) -> str:
    """
    Build Markdown table comparing detection, hard-block, and interruption rates across variants.
    """
    headers = [
        "Dataset",
        "Policy Variant",
        "Detection (ASK/BLOCK) [95% CI]",
        "Detection (BLOCK-only) [95% CI]",
        "Hard-Block Rate (Clean) [95% CI]",
        "Interruption Rate (Clean) [95% CI]",
        "Youden J [95% CI]",
    ]

    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    lines = [header_line, sep_line]

    for ds_name, variant_map in all_results.items():
        for v_name, rows in variant_map.items():
            # Detection (ASK or BLOCK)
            det_all, det_all_low, det_all_high = detection_rate(rows, legacy_semantics=False, ci_method="wilson")
            det_all_str = _format_ci(det_all, det_all_low, det_all_high)

            # Detection (BLOCK only)
            det_blk, det_blk_low, det_blk_high = detection_rate(rows, legacy_semantics=True, ci_method="wilson")
            det_blk_str = _format_ci(det_blk, det_blk_low, det_blk_high)

            # Hard-block rate on clean calls (BLOCK on label=0)
            hb, hb_low, hb_high = hard_block_rate(rows, ci_method="wilson")
            hb_str = _format_ci(hb, hb_low, hb_high)

            # Interruption rate on clean calls (ASK or BLOCK on label=0)
            ir, ir_low, ir_high = interruption_rate(rows, ci_method="wilson")
            ir_str = _format_ci(ir, ir_low, ir_high)

            # Youden's J
            j_est, j_low, j_high = youden_j(rows, legacy_semantics=False, B=2000, seed=42)
            j_str = _format_ci(j_est, j_low, j_high)

            row_line = (
                f"| {ds_name} | {v_name} | {det_all_str} | {det_blk_str} | "
                f"{hb_str} | {ir_str} | {j_str} |"
            )
            lines.append(row_line)

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Two-Tier Gate Policy across dev splits.")
    parser.add_argument("--out-dir", type=str, default=str(ROOT / "review" / "frontier_dev"),
                        help="Output directory for ResultRow JSONL files")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    datasets = ["argground", "deref_fcrb", "deref_cfb"]
    all_results: Dict[str, Dict[str, List[ResultRow]]] = {}

    print(f"Evaluating Two-Tier Frontier Gate on dev splits: {datasets}...")
    for ds in datasets:
        print(f"  Evaluating {ds} dev...")
        all_results[ds] = evaluate_dataset(ds, out_dir)

    table_md = build_frontier_table(all_results)
    summary_path = out_dir / "FRONTIER_REPORT.md"
    summary_path.write_text(table_md, encoding="utf-8")

    print("\n" + table_md + "\n")
    print(f"Frontier summary saved to {summary_path}")


if __name__ == "__main__":
    main()
