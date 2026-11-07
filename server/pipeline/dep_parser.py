"""
Dependency parsing via spaCy.

Returns (head_token, dep_label, child_token) triples for edge construction.

Role-swap fix (L3):
    Syntactic dependency labels are mapped to semantic role labels before
    being added to the graph, so that "Alice paid Bob" and "Bob paid Alice"
    produce structurally *different* graphs:

        nsubj  → AGENT    (the doer of the action)
        dobj   → PATIENT  (the recipient of the action)
        iobj   → RECIPIENT
        nsubjpass → PATIENT  (passive subject is also a patient)

    Any dep label not in the map is kept as-is, preserving full coverage.

Content-addressed cache:
    `extract_dep_triples` memoises on raw text so that benchmark runs
    processing the same premise or hypothesis text multiple times (e.g.
    during threshold-sweep) incur only one spaCy forward pass.
"""
from __future__ import annotations

import functools
from typing import List, Tuple

# ── Semantic role mapping (syntactic dep → semantic role) ──────────────────
# Keeps the graph role-sensitive so swapping agent ↔ patient changes topology.
_DEP_TO_ROLE: dict = {
    "nsubj":     "AGENT",
    "nsubjpass": "PATIENT",
    "dobj":      "PATIENT",
    "iobj":      "RECIPIENT",
    "pobj":      "OBLIQUE",   # prepositional object
}

_SPACY_DEGRADED: bool = False
_SPACY_DEGRADED_REASON: str = ""


@functools.lru_cache(maxsize=1)
def _load_nlp():
    global _SPACY_DEGRADED, _SPACY_DEGRADED_REASON
    import spacy
    # Fall back to sm model if trf not available
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


def get_dep_parser_degraded_status() -> Tuple[bool, List[str]]:
    """Returns (degraded, reasons) for the dependency parser."""
    _load_nlp()
    return (_SPACY_DEGRADED, [_SPACY_DEGRADED_REASON] if _SPACY_DEGRADED else [])


DepTriple = Tuple[str, str, str]  # (head_lemma, semantic_role, child_lemma)

# Content-addressed cache: text → list of triples
@functools.lru_cache(maxsize=512)
def extract_dep_triples(text: str) -> List[DepTriple]:
    """
    Parse `text` and return a list of (head_lemma, role_label, child_lemma)
    triples for every non-ROOT dependency edge.

    Dependency labels are mapped to semantic roles where applicable
    (nsubj→AGENT, dobj→PATIENT, iobj→RECIPIENT) so that role-swapped
    sentences produce different graph topologies.

    Results are memoised by text content to avoid redundant spaCy parses
    in benchmark/threshold-sweep runs.

    Example::

        "Alice paid Bob."
        → [("pay", "AGENT", "Alice"), ("pay", "PATIENT", "Bob"), ...]

        "Bob paid Alice."
        → [("pay", "AGENT", "Bob"), ("pay", "PATIENT", "Alice"), ...]
    """
    nlp = _load_nlp()
    doc = nlp(text)
    triples: List[DepTriple] = []
    for token in doc:
        if token.dep_ == "ROOT":
            continue
        role = _DEP_TO_ROLE.get(token.dep_, token.dep_)
        triples.append((token.head.lemma_, role, token.lemma_))
    return triples
