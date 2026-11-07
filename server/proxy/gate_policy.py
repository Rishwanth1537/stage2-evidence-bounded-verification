"""
Two-tier gate policy module (Prompt 4).

Classifies verification checks into authoritative tiers:
- ORACLE_EXACT (E2): Contractually decided by schema (type, required, undeclared, enum, pattern, range).
  Failure is definitely wrong -> triggers BLOCK.
- COVERAGE_BOUNDED (E1): Grounding against context or free-text descriptions.
  Failure means 'unsupported', not 'wrong' -> triggers ASK by default (or WARN / BLOCK if configured).
- UNCHECKABLE: Booleans, nulls, empty strings -> ABSTAIN (never blocks).

Severity hierarchy: BLOCK > ASK > WARN > ALLOW.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

from ..models.schemas import (
    CheckOutcome,
    CheckResult,
    CheckTier,
    ClarificationRequest,
    Decision,
)


class GatePolicy(BaseModel):
    """
    Configurable gate policy for two-tier verification decisions.
    """
    legacy_blocking: bool = Field(
        default=False,
        description="If True, any check failure (oracle or coverage) immediately triggers BLOCK.",
    )
    coverage_fail_decision: Decision = Field(
        default=Decision.ASK,
        description="Decision when a COVERAGE_BOUNDED check fails (default: ASK).",
    )
    oracle_fail_decision: Decision = Field(
        default=Decision.BLOCK,
        description="Decision when an ORACLE_EXACT check fails (default: BLOCK).",
    )

    def evaluate(
        self,
        check_results: List[CheckResult],
        agent_args: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Decision, Optional[ClarificationRequest], List[str]]:
        """
        Evaluate a collection of CheckResult instances under this policy.

        Returns:
            (overall_decision, clarification_request_or_none, reasons)
        """
        if not check_results:
            return Decision.ALLOW, None, []

        failed_checks = [c for c in check_results if c.outcome == CheckOutcome.FAIL]
        if not failed_checks:
            return Decision.ALLOW, None, []

        reasons = [c.reason for c in failed_checks if c.reason]

        # ── Legacy blocking mode ──────────────────────────────────────────────
        if self.legacy_blocking:
            return Decision.BLOCK, None, reasons

        # ── Two-tier severity evaluation ──────────────────────────────────────
        decisions: List[Decision] = []
        unsupported_reasons: List[str] = []
        unsupported_args: Dict[str, Any] = {}
        unsupported_values: Dict[str, Any] = {}
        missing_evidence_tier: Optional[str] = None

        for c in failed_checks:
            if c.tier == CheckTier.ORACLE_EXACT:
                decisions.append(self.oracle_fail_decision)
            elif c.tier == CheckTier.COVERAGE_BOUNDED:
                decisions.append(self.coverage_fail_decision)
                if c.arg_path:
                    arg_name = c.arg_path
                    val = agent_args.get(arg_name) if agent_args else c.details.get("value")
                    unsupported_args[arg_name] = val
                    unsupported_values[arg_name] = val
                if c.reason:
                    unsupported_reasons.append(c.reason)
                if not missing_evidence_tier and c.evidence_tier:
                    missing_evidence_tier = c.evidence_tier
            elif c.tier == CheckTier.UNCHECKABLE:
                # UNCHECKABLE never blocks or escalates decision
                pass

        if not decisions:
            return Decision.ALLOW, None, []

        # Determine overall decision by severity: BLOCK > ASK > WARN > ALLOW
        severity_order = {
            Decision.BLOCK: 3,
            Decision.ASK: 2,
            Decision.WARN: 1,
            Decision.ALLOW: 0,
        }
        overall = max(decisions, key=lambda d: severity_order.get(d, 0))

        clarification: Optional[ClarificationRequest] = None
        if overall == Decision.ASK:
            clarification = ClarificationRequest(
                arguments=unsupported_args,
                values=unsupported_values,
                unsupported_reasons=unsupported_reasons,
                missing_evidence_tier=missing_evidence_tier or "E1",
                details={"check_count": len(failed_checks)},
            )

        return overall, clarification, reasons


def load_gate_policy() -> GatePolicy:
    """
    Load the configured GatePolicy from environment variables and thresholds.yaml.
    """
    from ..config import _THRESHOLDS

    gp_dict = _THRESHOLDS.get("gate_policy", {})

    # Environment variable overrides
    legacy_env = os.environ.get("GATE_POLICY_LEGACY_BLOCKING")
    if legacy_env is not None:
        legacy_blocking = legacy_env.strip().lower() in ("1", "true", "yes", "on")
    else:
        legacy_blocking = bool(gp_dict.get("legacy_blocking", False))

    cov_env = os.environ.get("GATE_POLICY_COVERAGE_FAIL_DECISION")
    if cov_env is not None:
        coverage_fail = Decision(cov_env.strip().upper())
    else:
        coverage_fail = Decision(gp_dict.get("coverage_fail_decision", "ASK").upper())

    oracle_env = os.environ.get("GATE_POLICY_ORACLE_FAIL_DECISION")
    if oracle_env is not None:
        oracle_fail = Decision(oracle_env.strip().upper())
    else:
        oracle_fail = Decision(gp_dict.get("oracle_fail_decision", "BLOCK").upper())

    return GatePolicy(
        legacy_blocking=legacy_blocking,
        coverage_fail_decision=coverage_fail,
        oracle_fail_decision=oracle_fail,
    )
