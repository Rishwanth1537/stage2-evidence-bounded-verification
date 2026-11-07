"""
verify_argument_grounding: argument-level grounding of a planned tool call against its context (deterministic, no model).

Decision: evaluated via GatePolicy (Prompt 4):
- COVERAGE_BOUNDED checks on ungrounded values trigger ASK by default (or WARN / BLOCK if configured).
- Legacy blocking reproduces old behavior (blocking on UNGROUNDED) when legacy_blocking=True.
- tau can be calibrated for a target false-block rate with server.pipeline.arg_ground.conformal_threshold.
"""
from __future__ import annotations

from typing import List

from .. import session as session_module
from ..models.schemas import (
    ArgumentGroundingRequest,
    ArgumentGroundingResponse,
    ArgumentVerdictModel,
    CheckOutcome,
    CheckResult,
    CheckTier,
    Decision,
    HallucinationType,
    MismatchedSpan,
)
from ..pipeline.arg_ground import check_arguments
from ..proxy.gate_policy import load_gate_policy


def run_argument_grounding(req: ArgumentGroundingRequest) -> ArgumentGroundingResponse:
    verdicts = check_arguments(req.arguments, req.context)
    optional = set((req.schema_hint or {}).get("optional", [])) if req.policy == "required_only" else set()
    effective = [v for v in verdicts if v.verdict != "UNCHECKABLE" and v.argument not in optional]
    call_score = min((v.score for v in effective), default=1.0)
    is_grounded = call_score >= req.tau
    mismatched: List[MismatchedSpan] = []
    check_results: List[CheckResult] = []

    # Map each verdict to a CheckResult (Prompt 4 classification)
    for v in verdicts:
        if v.verdict == "UNCHECKABLE":
            check_results.append(CheckResult(
                check_id=f"arg_ground:{v.argument}",
                tier=CheckTier.UNCHECKABLE,
                outcome=CheckOutcome.ABSTAIN,
                evidence_tier="E1",
                arg_path=v.argument,
                reason=v.reason or "boolean, null, or empty string",
                details={"value": v.value, "score": v.score},
            ))
        elif v.verdict == "GROUNDED":
            check_results.append(CheckResult(
                check_id=f"arg_ground:{v.argument}",
                tier=CheckTier.COVERAGE_BOUNDED,
                outcome=CheckOutcome.PASS,
                evidence_tier="E1",
                arg_path=v.argument,
                reason="Value is supported by context.",
                details={"value": v.value, "score": v.score},
            ))
        else:  # UNGROUNDED
            # If ignored under required_only policy, outcome is ABSTAIN
            if req.policy == "required_only" and v.argument in optional:
                check_results.append(CheckResult(
                    check_id=f"arg_ground:{v.argument}",
                    tier=CheckTier.COVERAGE_BOUNDED,
                    outcome=CheckOutcome.ABSTAIN,
                    evidence_tier="E1",
                    arg_path=v.argument,
                    reason=f"Optional argument {v.argument} ignored under required_only policy.",
                    details={"value": v.value, "score": v.score},
                ))
            else:
                reason_str = v.reason or f"Argument '{v.argument}' value {v.value!r} not found in context."
                check_results.append(CheckResult(
                    check_id=f"arg_ground:{v.argument}",
                    tier=CheckTier.COVERAGE_BOUNDED,
                    outcome=CheckOutcome.FAIL,
                    evidence_tier="E1",
                    arg_path=v.argument,
                    reason=reason_str,
                    details={"value": v.value, "score": v.score},
                ))

    if not is_grounded:
        mismatched = [
            MismatchedSpan(
                span=f"{v.argument}={v.value!r}",
                issue=v.reason or "value not supported by the context",
                hallucination_type=HallucinationType.CONTENT,
            )
            for v in effective if v.score < req.tau
        ]

    if req.session_id:
        session_module.tracker.record(req.session_id, call_score)

    if is_grounded:
        feedback = "All checkable argument values are supported by the context."
    else:
        feedback = (
            "These argument values are not supported by the context; confirm or correct them before executing:\n"
            + "\n".join(f"- {m.span}: {m.issue}" for m in mismatched)
        )

    degraded = getattr(verdicts, "degraded", False)
    degraded_reasons = list(getattr(verdicts, "degraded_reasons", []))

    # Evaluate decision using GatePolicy
    policy = load_gate_policy()
    decision, _, _ = policy.evaluate(check_results, agent_args=req.arguments)

    return ArgumentGroundingResponse(
        is_grounded=is_grounded,
        call_score=round(call_score, 4),
        tau=req.tau,
        per_argument=[
            ArgumentVerdictModel(
                argument=v.argument,
                value=v.value,
                verdict=v.verdict,
                score=round(v.score, 4),
                reason=v.reason,
            )
            for v in verdicts
        ],
        mismatched_spans=mismatched,
        feedback=feedback,
        degraded=degraded,
        degraded_reasons=degraded_reasons,
        decision=decision,
        check_results=check_results,
    )
