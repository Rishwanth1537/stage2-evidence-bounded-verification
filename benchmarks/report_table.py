"""
Markdown summary table generator for benchmark evaluation runs.

Follows Stage 2 Prompt 3 specification:
Columns: System, n_pos, n_neg, Detection [95% CI], False-Block [95% CI],
         Interruption [95% CI], Youden J [95% CI], Latency ms (median / p95), Tokens (in / out).
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np

from .results_io import ResultRow, read_rows
from .stats import (
    detection_rate,
    false_block_rate,
    hard_block_rate,
    interruption_rate,
    wilson_ci,
    youden_j,
)


def _fmt_ci(val: float, low: float, high: float, decimals: int = 3) -> str:
    """Format an estimate with its confidence interval."""
    return f"{val:.{decimals}f} [{low:.{decimals}f}, {high:.{decimals}f}]"


def build_report_table(
    rows: Sequence[Union[ResultRow, Dict[str, Any]]],
    legacy_semantics: bool = False,
    ci_method: str = "wilson",
    cluster_key: str = "cluster_id",
    bootstrap_b: int = 2000,
    seed: int = 0,
) -> str:
    """
    Generate a GitHub Flavored Markdown table summarizing benchmark results by system.

    Columns:
        System | n_pos | n_neg | Detection [95% CI] | False-Block [95% CI] |
        Interruption [95% CI] | Youden J [95% CI] | Latency ms [med/p95] | Tokens [in/out]

    Args:
        rows: Sequence of ResultRow objects or dicts.
        legacy_semantics: If True, detection requires BLOCK; if False, ASK or BLOCK.
        ci_method: CI method ('wilson' or 'cluster_bootstrap').
        cluster_key: Cluster grouping key.
        bootstrap_b: Bootstrap resample count if bootstrap is used.
        seed: Random seed.

    Returns:
        Markdown table string.
    """
    if not rows:
        return "*(No evaluation rows provided)*"

    # Group by system and system_version
    systems: Dict[str, List[Any]] = {}
    for r in rows:
        sys_name = r.system if isinstance(r, ResultRow) else r.get("system", "unknown")
        sys_ver = r.system_version if isinstance(r, ResultRow) else r.get("system_version", "")
        key = f"{sys_name} ({sys_ver})" if sys_ver else sys_name
        systems.setdefault(key, []).append(r)

    headers = [
        "System",
        "n_pos",
        "n_neg",
        f"Detection [{ci_method.capitalize()} CI]",
        f"False-Block [{ci_method.capitalize()} CI]",
        "Interruption [95% CI]",
        "Youden J [95% CI]",
        "Latency ms [med / p95]",
        "Tokens [in / out]",
    ]

    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    table_lines = [header_line, separator_line]

    for sys_label, sys_rows in sorted(systems.items()):
        pos_rows = [
            r for r in sys_rows
            if (r.label if isinstance(r, ResultRow) else r.get("label")) == 1
        ]
        neg_rows = [
            r for r in sys_rows
            if (r.label if isinstance(r, ResultRow) else r.get("label")) == 0
        ]
        n_pos = len(pos_rows)
        n_neg = len(neg_rows)

        # Detection rate
        det_est, det_low, det_high = detection_rate(
            sys_rows,
            legacy_semantics=legacy_semantics,
            ci_method=ci_method,
            cluster_key=cluster_key,
            B=bootstrap_b,
            seed=seed,
        )
        det_str = _fmt_ci(det_est, det_low, det_high)

        # False-block rate (strict legacy BLOCK)
        fb_est, fb_low, fb_high = false_block_rate(
            sys_rows,
            legacy_semantics=True,
            ci_method=ci_method,
            cluster_key=cluster_key,
            B=bootstrap_b,
            seed=seed,
        )
        fb_str = _fmt_ci(fb_est, fb_low, fb_high)

        # Interruption rate (ASK or BLOCK on clean calls)
        ir_est, ir_low, ir_high = interruption_rate(
            sys_rows,
            ci_method=ci_method,
            cluster_key=cluster_key,
            B=bootstrap_b,
            seed=seed,
        )
        ir_str = _fmt_ci(ir_est, ir_low, ir_high)

        # Youden's J
        j_est, j_low, j_high = youden_j(
            sys_rows,
            legacy_semantics=legacy_semantics,
            cluster_key=cluster_key,
            B=bootstrap_b,
            seed=seed,
        )
        j_str = _fmt_ci(j_est, j_low, j_high)

        # Latency statistics
        latencies = [
            (r.latency_ms if isinstance(r, ResultRow) else float(r.get("latency_ms", 0.0)))
            for r in sys_rows
        ]
        if latencies:
            lat_med = float(np.median(latencies))
            lat_p95 = float(np.percentile(latencies, 95))
            lat_str = f"{lat_med:.1f} / {lat_p95:.1f}"
        else:
            lat_str = "N/A"

        # Token statistics
        tokens_in = [
            (r.tokens_in if isinstance(r, ResultRow) else int(r.get("tokens_in", 0)))
            for r in sys_rows
        ]
        tokens_out = [
            (r.tokens_out if isinstance(r, ResultRow) else int(r.get("tokens_out", 0)))
            for r in sys_rows
        ]
        tok_in_avg = int(np.mean(tokens_in)) if tokens_in else 0
        tok_out_avg = int(np.mean(tokens_out)) if tokens_out else 0
        tok_str = f"{tok_in_avg} / {tok_out_avg}"

        row_line = (
            f"| {sys_label} | {n_pos} | {n_neg} | {det_str} | {fb_str} | "
            f"{ir_str} | {j_str} | {lat_str} | {tok_str} |"
        )
        table_lines.append(row_line)

    return "\n".join(table_lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Markdown report table from ResultRow JSONL.")
    parser.add_argument("results_file", type=str, help="Path to JSONL file containing ResultRows")
    parser.add_argument("--legacy", action="store_true", help="Use legacy semantics (BLOCK only for detection)")
    parser.add_argument("--ci-method", choices=["wilson", "cluster_bootstrap"], default="wilson")
    parser.add_argument("--output", "-o", type=str, default=None, help="Output markdown file path")

    args = parser.parse_args()
    rows = read_rows(args.results_file)
    table_md = build_report_table(rows, legacy_semantics=args.legacy, ci_method=args.ci_method)

    if args.output:
        Path(args.output).write_text(table_md, encoding="utf-8")
        print(f"Report table written to {args.output}")
    else:
        print(table_md)


if __name__ == "__main__":
    main()
