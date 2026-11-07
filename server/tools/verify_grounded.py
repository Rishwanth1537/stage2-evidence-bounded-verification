"""
'Grounded' verification mode for verify_logic_chain.

Decision rule (all fixed, nothing learned):
    consistent  iff  whole-claim NLI entailment >= ENTAILMENT_THRESHOLD
                 and every number-like token in the hypothesis also occurs in the premise
                 and (when a user_query is given) no query constraint is missing from the hypothesis.

Rationale: in our ablations (benchmarks/ablation_local.py, benchmarks/eval_grounded.py) whole-claim NLI was far stronger than the
graph-edit-distance stage, but it can accept near-identical numbers; the deterministic value check covers that gap and names
the offending token.  The graph stage is not used in this mode (ged fields are returned as 0.0).

Known limitations: action-plan hypotheses ("The agent will download X as requested") are often judged not entailed by
request-style premises, so such phrasing can be flagged; spelled-out numbers and unit conversions are not handled.
"""
from __future__ import annotations

from typing import List, Optional

from .. import session as session_module
from ..config import ENTAILMENT_THRESHOLD
from ..models.schemas import HallucinationType, MismatchedSpan, VerifyResponse
from ..pipeline import entailment
from ..pipeline.constraints import compute_constraint_score, extract_constraints, get_constraints_degraded_status
from ..pipeline.value_check import unmatched_values


def run_grounded_verification(
    hypothesis: str,
    premise: str,
    session_id: Optional[str] = None,
    user_query: Optional[str] = None,
    entailment_threshold: float = ENTAILMENT_THRESHOLD,
) -> VerifyResponse:
    ent = entailment.score_claim(premise, hypothesis)
    bad_values = unmatched_values(hypothesis, premise)

    mismatched: List[MismatchedSpan] = []
    for v in bad_values:
        mismatched.append(MismatchedSpan(
            span=v,
            issue=f"Value '{v}' appears in the plan but not in the source context.",
            hallucination_type=HallucinationType.CONTENT,
        ))
    if ent < entailment_threshold and not bad_values:
        shown = hypothesis if len(hypothesis) <= 120 else hypothesis[:117] + "..."
        mismatched.append(MismatchedSpan(
            span=shown,
            issue=f"Claim is not entailed by the source context (entailment {ent:.2f} < {entailment_threshold:.2f}).",
            hallucination_type=HallucinationType.CONTENT,
        ))

    constraint_score: Optional[float] = None
    degraded = False
    degraded_reasons: List[str] = []

    if user_query:
        constraints = extract_constraints(user_query)
        score, missing = compute_constraint_score(constraints, hypothesis)
        constraint_score = round(score, 4)
        for c in missing:
            mismatched.append(MismatchedSpan(
                span=c,
                issue=f"Constraint '{c}' from user query is absent from the hypothesis.",
                hallucination_type=HallucinationType.CONTENT,
            ))
        c_deg, c_reasons = get_constraints_degraded_status()
        if c_deg:
            degraded = True
            degraded_reasons.extend(c_reasons)

    is_consistent = not mismatched and ent >= entailment_threshold
    factual_score = 0.0 if bad_values else round(float(ent), 4)

    drift_alert: Optional[bool] = None
    session_mean: Optional[float] = None
    if session_id:
        session_module.tracker.record(session_id, factual_score)
        mean = session_module.tracker.get_rolling_mean(session_id)
        drift_alert = session_module.tracker.is_drifting(session_id)
        session_mean = round(mean, 4) if mean is not None else None

    if mismatched:
        lines = [f'- "{m.span}" [{m.hallucination_type}]: {m.issue}' for m in mismatched]
        feedback = ("The following parts lack grounding in the provided context:\n" + "\n".join(lines)
                    + "\nRevise these before executing the planned action.")
    else:
        feedback = "The claim is entailed by the provided context and all values match."

    return VerifyResponse(
        factual_consistency_score=factual_score,
        is_consistent=is_consistent,
        mismatched_spans=mismatched,
        feedback=feedback,
        ged_raw=0.0,
        ged_normalised=0.0,
        constraint_score=constraint_score,
        drift_alert=drift_alert,
        session_mean_score=session_mean,
        degraded=degraded,
        degraded_reasons=degraded_reasons,
    )
