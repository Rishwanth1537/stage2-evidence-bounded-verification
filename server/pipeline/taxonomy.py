"""
Typed hallucination taxonomy classifier.

Every detected mismatch is assigned exactly one of:
  schema  — missing/extraneous field relative to a declared schema
  format  — value present but wrong type/structure
  content — semantically incorrect claim not grounded in premise
"""
from __future__ import annotations
from typing import List, Optional
from ..models.schemas import HallucinationType, MismatchedSpan


def classify_span(
    span: str,
    issue: str,
    is_missing_field: bool = False,
    is_type_mismatch: bool = False,
) -> HallucinationType:
    """
    Classify a single mismatch.
    Priority: schema > format > content (fallback).
    """
    if is_missing_field:
        return HallucinationType.SCHEMA
    if is_type_mismatch:
        return HallucinationType.FORMAT
    return HallucinationType.CONTENT


def classify_all(
    spans: List[str],
    issues: List[str],
    missing_flags: Optional[List[bool]] = None,
    type_mismatch_flags: Optional[List[bool]] = None,
) -> List[MismatchedSpan]:
    """
    Apply classify_span to every (span, issue) pair.
    Guarantees every output has a non-None hallucination_type.
    """
    n = len(spans)
    missing = missing_flags or [False] * n
    type_mm = type_mismatch_flags or [False] * n

    result: List[MismatchedSpan] = []
    for span, issue, miss, tmm in zip(spans, issues, missing, type_mm):
        htype = classify_span(span, issue, is_missing_field=miss, is_type_mismatch=tmm)
        result.append(MismatchedSpan(span=span, issue=issue, hallucination_type=htype))
    return result
