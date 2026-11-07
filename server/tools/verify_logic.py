"""
Core logic for the verify_logic_chain MCP tool.
Orchestrates the full pipeline: SRL → graph → GED → entailment → taxonomy → constraints → session.
"""
from __future__ import annotations
from typing import List, Optional

from ..pipeline.graph_builder import build_semantic_graph
from ..pipeline.ged import compute_ged, get_ged_degraded_status
from ..pipeline.entailment import score_spans
from ..pipeline.srl import extract_frames, _VALUE_ENT_LABELS, get_srl_degraded_status
from ..pipeline.dep_parser import get_dep_parser_degraded_status
from ..pipeline.taxonomy import classify_all
from ..pipeline.constraints import extract_constraints, compute_constraint_score, get_constraints_degraded_status
from ..models.schemas import HallucinationType, MismatchedSpan, VerifyResponse
from .. import session as session_module
from ..config import GED_THRESHOLD, ENTAILMENT_THRESHOLD

# Common function-word predicates that have no claim-bearing content and
# should not be sent to DeBERTa for entailment checking.  These appear as
# SRL predicates in nearly every sentence and will always look "ungrounded"
# against a short premise such as "Tool schema requires: timestamp (integer).".
_STOP_PREDICATES = frozenset({
    "be", "is", "are", "was", "were", "have", "has", "had",
    "do", "does", "did", "get", "got", "use", "make", "take",
    "go", "come", "see", "know", "think", "say", "tell", "give",
    "let", "put", "set", "run", "call", "send", "pass", "provide",
    "will", "would", "could", "should", "may", "might",
})


def _extract_argument_spans(frames: list) -> List[str]:
    """
    Extract argument spans from SRL frames, filtering out stop-word predicates.

    Only spans that carry genuine semantic content are sent to DeBERTa:
    - Argument spans (entity/value text extracted by NER) — always included
    - Predicate spans — only if they are not generic function words
    """
    spans = []
    for frame in frames:
        pred = frame["predicate"]
        # Only include predicate text if it's a content-bearing verb
        if pred.lower() not in _STOP_PREDICATES:
            spans.append(pred)
        # Always include argument spans (NER entities, values)
        spans.extend(frame["arguments"].values())
    return list(set(spans))


def run_verification(
    hypothesis: str,
    premise: str,
    threshold: float = GED_THRESHOLD,
    session_id: Optional[str] = None,
    user_query: Optional[str] = None,
) -> VerifyResponse:
    # 1. Build semantic graphs
    G_hyp = build_semantic_graph(hypothesis)
    G_prem = build_semantic_graph(premise)

    # 2. GED alignment
    raw_ged, norm_ged = compute_ged(G_hyp, G_prem)
    factual_score = round(max(0.0, 1.0 - norm_ged), 4)
    is_consistent = norm_ged <= threshold

    # 3. Span-level entailment
    hyp_frames = extract_frames(hypothesis)
    argument_spans = _extract_argument_spans(hyp_frames)
    span_scores = score_spans(premise, argument_spans)

    low_spans = [s for s, sc in span_scores if sc < ENTAILMENT_THRESHOLD]
    low_issues = [
        f"Entailment score {sc:.2f} — span not supported by premise."
        for s, sc in span_scores if sc < ENTAILMENT_THRESHOLD
    ]

    # 4. Taxonomy classification
    mismatched: List[MismatchedSpan] = classify_all(low_spans, low_issues)

    # 5. Constraint score (optional)
    constraint_score: Optional[float] = None
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

    # 6. Session drift tracking (optional)
    drift_alert: Optional[bool] = None
    session_mean: Optional[float] = None
    if session_id:
        session_module.tracker.record(session_id, factual_score)
        session_mean_raw = session_module.tracker.get_rolling_mean(session_id)
        drift_alert = session_module.tracker.is_drifting(session_id)
        session_mean = round(session_mean_raw, 4) if session_mean_raw is not None else None

    # 7. Collect degraded mode status
    degraded_reasons: List[str] = []
    srl_deg, srl_reasons = get_srl_degraded_status()
    if srl_deg:
        degraded_reasons.extend(srl_reasons)

    dep_deg, dep_reasons = get_dep_parser_degraded_status()
    if dep_deg:
        degraded_reasons.extend(dep_reasons)

    # GED degradation
    if hasattr(raw_ged, "degraded") and raw_ged.degraded:
        degraded_reasons.extend(raw_ged.degraded_reasons)
    else:
        ged_deg, ged_reasons = get_ged_degraded_status()
        if ged_deg:
            degraded_reasons.extend(ged_reasons)

    if user_query:
        c_deg, c_reasons = get_constraints_degraded_status()
        if c_deg:
            degraded_reasons.extend(c_reasons)

    # Deduplicate preserving order
    seen_reasons = set()
    deduped_reasons = []
    for r in degraded_reasons:
        if r not in seen_reasons:
            seen_reasons.add(r)
            deduped_reasons.append(r)
    degraded = len(deduped_reasons) > 0

    # 8. Feedback & Final consistency verification
    if mismatched:
        is_consistent = False
        lines = [f'- "{m.span}" [{m.hallucination_type}]: {m.issue}' for m in mismatched]
        feedback = (
            "The following spans lack grounding in the provided context:\n"
            + "\n".join(lines)
            + "\nRevise these before executing the planned action."
        )
    else:
        feedback = "Reasoning chain is structurally consistent with the provided context."

    return VerifyResponse(
        factual_consistency_score=factual_score,
        is_consistent=is_consistent,
        mismatched_spans=mismatched,
        feedback=feedback,
        ged_raw=float(raw_ged),
        ged_normalised=round(float(norm_ged), 4),
        constraint_score=constraint_score,
        drift_alert=drift_alert,
        session_mean_score=session_mean,
        degraded=degraded,
        degraded_reasons=deduped_reasons,
    )
