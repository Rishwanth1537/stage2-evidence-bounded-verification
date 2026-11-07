"""
verify_argument_grounding: argument-level grounding of a planned tool call against its context (deterministic, no model).

Decision: block iff the call-level score (the weakest match among checkable arguments) is below tau, optionally ignoring
ungrounded OPTIONAL arguments (policy "required_only").  tau can be calibrated for a target false-block rate with
server.pipeline.arg_ground.conformal_threshold; see benchmarks/eval_argground.py for the evaluation.
"""
from __future__ import annotations

from typing import List

from .. import session as session_module
from ..models.schemas import (
    ArgumentGroundingRequest, ArgumentGroundingResponse, ArgumentVerdictModel, HallucinationType, MismatchedSpan,
)
from ..pipeline.arg_ground import check_arguments


def run_argument_grounding(req: ArgumentGroundingRequest) -> ArgumentGroundingResponse:
    verdicts = check_arguments(req.arguments, req.context)
    optional = set((req.schema_hint or {}).get("optional", [])) if req.policy == "required_only" else set()
    effective = [v for v in verdicts if v.verdict != "UNCHECKABLE" and v.argument not in optional]
    call_score = min((v.score for v in effective), default=1.0)
    is_grounded = call_score >= req.tau
    mismatched: List[MismatchedSpan] = []
    if not is_grounded:
        mismatched = [
            MismatchedSpan(span=f"{v.argument}={v.value!r}", issue=v.reason or "value not supported by the context",
                           hallucination_type=HallucinationType.CONTENT)
            for v in effective if v.score < req.tau
        ]
    if req.session_id:
        session_module.tracker.record(req.session_id, call_score)
    if is_grounded:
        feedback = "All checkable argument values are supported by the context."
    else:
        feedback = ("These argument values are not supported by the context; confirm or correct them before executing:\n"
                    + "\n".join(f"- {m.span}: {m.issue}" for m in mismatched))
    return ArgumentGroundingResponse(
        is_grounded=is_grounded, call_score=round(call_score, 4), tau=req.tau,
        per_argument=[ArgumentVerdictModel(argument=v.argument, value=v.value, verdict=v.verdict, score=round(v.score, 4), reason=v.reason)
                      for v in verdicts],
        mismatched_spans=mismatched, feedback=feedback)
