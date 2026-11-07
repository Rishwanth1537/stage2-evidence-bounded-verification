"""
Constraint extractor for intent preservation scoring.

Extracts named entities, numeric values, and temporal expressions
from a user query, then checks which are preserved in the hypothesis.
"""
from __future__ import annotations
import re
import functools
from typing import List, Tuple

_NUMERIC_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
_TEMPORAL_RE = re.compile(
    r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december"
    r"|\d{4}|yesterday|today|tomorrow|last\s+\w+|next\s+\w+|\d+\s+(?:days?|weeks?|months?|years?)\s+ago)\b",
    re.IGNORECASE,
)

_SPACY_DEGRADED: bool = False
_SPACY_DEGRADED_REASON: str = ""


@functools.lru_cache(maxsize=1)
def _load_nlp():
    global _SPACY_DEGRADED, _SPACY_DEGRADED_REASON
    import spacy
    # Mirror srl.py: fall back to sm model if trf not available
    try:
        nlp = spacy.load("en_core_web_trf")
        _SPACY_DEGRADED = False
        _SPACY_DEGRADED_REASON = ""
        return nlp
    except OSError:
        nlp = spacy.load("en_core_web_sm")
        _SPACY_DEGRADED = True
        _SPACY_DEGRADED_REASON = "spaCy model downgraded to en_core_web_sm (en_core_web_trf unavailable)"
        return nlp


def get_constraints_degraded_status() -> Tuple[bool, List[str]]:
    """Returns (degraded, reasons) for the constraints extractor."""
    _load_nlp()
    return (_SPACY_DEGRADED, [_SPACY_DEGRADED_REASON] if _SPACY_DEGRADED else [])


def extract_constraints(user_query: str) -> List[str]:
    """
    Extract named entities, numeric values, and temporal expressions
    from `user_query`. Returns a deduplicated list of constraint strings.
    """
    nlp = _load_nlp()
    doc = nlp(user_query)

    constraints: List[str] = []

    # Named entities
    for ent in doc.ents:
        constraints.append(ent.text.strip())

    # Numeric values not already captured by NER
    for match in _NUMERIC_RE.finditer(user_query):
        val = match.group()
        if val not in constraints:
            constraints.append(val)

    # Temporal expressions
    for match in _TEMPORAL_RE.finditer(user_query):
        val = match.group()
        if val not in constraints:
            constraints.append(val)

    # Deduplicate preserving order
    seen, deduped = set(), []
    for c in constraints:
        key = c.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(c)
    return deduped


def compute_constraint_score(
    constraints: List[str], hypothesis: str
) -> Tuple[float, List[str]]:
    """
    Returns (score, missing_constraints).
    score = preserved / total; 1.0 when total == 0 (vacuous truth).
    """
    total = len(constraints)
    if total == 0:
        return 1.0, []

    hyp_lower = hypothesis.lower()
    missing: List[str] = []
    for c in constraints:
        if c.lower() not in hyp_lower:
            missing.append(c)

    preserved = total - len(missing)
    return preserved / total, missing
