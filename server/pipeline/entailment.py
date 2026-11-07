"""
Textual entailment classifier using DeBERTa-v3-base-mnli-fever-anli.
Used for sub-claim attribution: given a (premise, span) pair, returns
entailment probability to pinpoint which spans are not grounded.
"""
from __future__ import annotations

import functools
import re
from typing import List, Tuple

MODEL_NAME = "cross-encoder/nli-deberta-v3-base"
_WINDOW_WORDS = 180
_WINDOW_OVERLAP = 40


@functools.lru_cache(maxsize=1)
def _load_pipeline():
    from transformers import pipeline
    # Use native NLI cross-encoder instead of mapping zero-shot templates backwards
    return pipeline(
        "text-classification",
        model=MODEL_NAME,
        top_k=None,
        truncation=True,
    )


def _make_hypothesis(span: str) -> str:
    """
    Build a contextual NLI hypothesis for the given span.

    Design principles:
    - Numeric / currency / version spans use a precise entailment claim
      so DeBERTa must verify the *exact* value, not just its existence.
    - Named entities (short, 1–2 tokens) get a presence claim.
    - Longer spans use a paraphrase entailment frame.

    The exact-value framing is critical: "The text states that the exact
    amount is $500." will score near-zero entailment against a premise
    that says "$50", whereas the weaker "The context contains the value
    $500." was too easy for the model to confirm approximately.
    """
    stripped = span.strip()
    # Pure numeric / currency / version-looking spans → exact-value claim
    if re.match(r"^[\$€£¥]?[\d,]+(\.\d+)?(%|[kKmMbB])?$", stripped) or \
       re.match(r"^v?\d+\.\d+(\.\d+)*$", stripped):
        return f"The text states that the exact value is {stripped}."
    # Date/time-like spans (heuristic: contains digits or weekday names)
    _DATE_WORDS = {"monday", "tuesday", "wednesday", "thursday", "friday",
                   "saturday", "sunday", "january", "february", "march",
                   "april", "may", "june", "july", "august", "september",
                   "october", "november", "december", "am", "pm"}
    lower = stripped.lower()
    if any(w in lower for w in _DATE_WORDS) or re.search(r"\d", stripped):
        return f"The text explicitly states the time or date as {stripped}."
    # Short spans (1–2 tokens) — presence claim
    if len(stripped.split()) <= 2:  # noqa: PLR2004
        return f"The text explicitly mentions {stripped}."
    # Medium / long spans — paraphrase entailment
    return f"Specifically, {stripped}."


def _premise_windows(premise: str) -> List[str]:
    """Split long premises into overlapping windows that fit the NLI model."""
    words = premise.split()
    if len(words) <= _WINDOW_WORDS:
        return [premise]

    step = _WINDOW_WORDS - _WINDOW_OVERLAP
    return [
        " ".join(words[start:start + _WINDOW_WORDS])
        for start in range(0, len(words), step)
        if words[start:start + _WINDOW_WORDS]
    ]


def score_spans(
    premise: str, spans: List[str]
) -> List[Tuple[str, float]]:
    """
    For each span in `spans`, returns (span, entailment_score).
    Score close to 1.0 → well-grounded; close to 0.0 → likely hallucinated.

    Uses a batched inference call for efficiency (single forward pass for
    all spans instead of N separate calls).
    """
    classifier = _load_pipeline()

    # Filter empty spans before batching
    valid = [(i, sp) for i, sp in enumerate(spans) if sp.strip()]
    if not valid:
        return []

    windows = _premise_windows(premise)
    inputs = [
        {"text": window, "text_pair": _make_hypothesis(sp)}
        for window in windows
        for _, sp in valid
    ]

    # Score all premise windows in one pass and keep the strongest evidence.
    batch_scores = classifier(inputs)
    best_scores = {sp: 0.0 for _, sp in valid}

    for index, scores in enumerate(batch_scores):
        # Handle nested list format some pipeline versions return
        if isinstance(scores, list) and scores and isinstance(scores[0], list):
            scores = scores[0]
        entail_score = next(
            (x["score"] for x in scores if x["label"].lower() == "entailment"),
            0.0,
        )
        sp = valid[index % len(valid)][1]
        best_scores[sp] = max(best_scores[sp], entail_score)

    results: List[Tuple[str, float]] = []
    for _, sp in valid:
        entail_score = best_scores[sp]
        results.append((sp, entail_score))
    return results


def score_claim(premise: str, claim: str) -> float:
    """
    Whole-claim entailment probability WITHOUT the span hypothesis template, maximised over
    overlapping premise windows.  This is the scorer used by the 'grounded' verification mode.
    """
    if not claim.strip() or not premise.strip():
        return 0.0
    classifier = _load_pipeline()
    inputs = [{"text": w, "text_pair": claim.strip()} for w in _premise_windows(premise)]
    best = 0.0
    for scores in classifier(inputs):
        if isinstance(scores, list) and scores and isinstance(scores[0], list):
            scores = scores[0]
        best = max(best, next((x["score"] for x in scores if x["label"].lower() == "entailment"), 0.0))
    return best
