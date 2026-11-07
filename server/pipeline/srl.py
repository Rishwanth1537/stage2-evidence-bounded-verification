"""
SRL decomposition using HuggingFace token-classification pipeline
with the `dslim/bert-base-NER` model as a lightweight stand-in for
predicate-argument extraction.

We use a two-step approach:
  1. NER identifies entity spans (ARG-equivalent nodes)
  2. spaCy dependency parse identifies the governing verb (predicate)
     for each entity via the shortest path to a VERB token

This avoids the heavy AllenNLP dependency while preserving the
predicate → argument graph structure the rest of the pipeline expects.

spaCy's built-in NER is also used to extract value spans (MONEY,
CARDINAL, DATE, TIME, PERCENT, ORDINAL, QUANTITY) that BERT-NER
misses — these are essential for detecting numeric and temporal
hallucinations (e.g. "$50 vs $500", "v2.4.0 vs v2.4.1").
"""
from __future__ import annotations
import functools
from typing import List, Dict


@functools.lru_cache(maxsize=1)
def _load_ner():
    from transformers import pipeline
    return pipeline(
        "token-classification",
        model="dslim/bert-base-NER",
        aggregation_strategy="simple",
    )


@functools.lru_cache(maxsize=1)
def _load_nlp():
    import spacy
    # fall back to sm model if trf not available
    try:
        return spacy.load("en_core_web_trf")
    except OSError:
        return spacy.load("en_core_web_sm")


def _find_governing_verb(token, max_depth: int = 5) -> str:
    """Walk up the dependency tree to find the nearest VERB ancestor."""
    current = token
    for _ in range(max_depth):
        if current.pos_ == "VERB":
            return current.lemma_
        if current.dep_ == "ROOT":
            return current.lemma_
        current = current.head
    return current.lemma_


# spaCy entity labels that represent concrete values which must be
# visible to the semantic graph for numeric/temporal hallucination detection.
_VALUE_ENT_LABELS = frozenset({
    "MONEY", "CARDINAL", "ORDINAL", "PERCENT",
    "QUANTITY", "DATE", "TIME",
})


def _extract_value_spans(doc) -> Dict[str, Dict[str, str]]:
    """
    Pull spaCy NER value entities (MONEY, CARDINAL, DATE, TIME, …) and
    group them by their governing predicate.

    L4 fix: Multiple spans with the same role under the same predicate
    (e.g., "$50" and "$200" both tagged MONEY) are now preserved with a
    counter suffix (MONEY, MONEY_2, MONEY_3, …) instead of silently
    dropping all but the first.

    Returns a mapping: predicate_lemma → {role_label: span_text}
    """
    pred_to_args: Dict[str, Dict[str, str]] = {}
    for ent in doc.ents:
        if ent.label_ not in _VALUE_ENT_LABELS:
            continue
        span_text = ent.text.strip()
        base_role = ent.label_          # e.g. MONEY, DATE, CARDINAL
        predicate = _find_governing_verb(ent.root)
        if predicate not in pred_to_args:
            pred_to_args[predicate] = {}

        # Disambiguate duplicate roles under the same predicate
        role = base_role
        counter = 2
        while role in pred_to_args[predicate]:
            role = f"{base_role}_{counter}"
            counter += 1
        pred_to_args[predicate][role] = span_text
    return pred_to_args


@functools.lru_cache(maxsize=512)
def extract_frames(text: str) -> List[Dict]:
    """
    Returns a list of SRL-style frames:
        [{"predicate": str, "arguments": {role_label: span_text}}, ...]

    Uses NER entity spans as arguments and dependency parsing to
    identify the governing predicate for each entity.

    Two sources of entities are merged:
      1. BERT-NER (PER, ORG, LOC, MISC) — named entities
      2. spaCy NER value spans (MONEY, CARDINAL, DATE, TIME, …) —
         numeric/temporal values critical for hallucination detection
    """
    if not text.strip():
        return []

    ner = _load_ner()
    nlp = _load_nlp()

    doc = nlp(text)
    ner_results = ner(text)

    # Build token offset → spaCy token index map
    char_to_token: Dict[int, int] = {}
    for tok in doc:
        for i in range(tok.idx, tok.idx + len(tok.text)):
            char_to_token[i] = tok.i

    # ── Source 1: BERT-NER entities (PER, ORG, LOC, MISC) ────────────────────
    pred_to_args: Dict[str, Dict[str, str]] = {}

    for ent in ner_results:
        span_text = ent["word"].replace("##", "").strip()
        role = ent["entity_group"]  # e.g. PER, ORG, LOC, MISC
        start_char = ent["start"]

        # Find the spaCy token for this entity's start char
        tok_idx = char_to_token.get(start_char)
        if tok_idx is None:
            # Fallback: find nearest mapped char
            for offset in range(start_char, start_char + 10):
                if offset in char_to_token:
                    tok_idx = char_to_token[offset]
                    break

        if tok_idx is not None:
            spacy_token = doc[tok_idx]
            predicate = _find_governing_verb(spacy_token)
        else:
            predicate = "unknown"

        if predicate not in pred_to_args:
            pred_to_args[predicate] = {}
        # Deduplicate by role — keep first occurrence
        if role not in pred_to_args[predicate]:
            pred_to_args[predicate][role] = span_text

    # ── Source 2: spaCy value spans (MONEY, CARDINAL, DATE, TIME, …) ─────────
    for predicate, value_args in _extract_value_spans(doc).items():
        if predicate not in pred_to_args:
            pred_to_args[predicate] = {}
        for role, span_text in value_args.items():
            # Value spans take priority — they must not be silently dropped
            pred_to_args[predicate][role] = span_text

    # Also add ROOT verb as a frame even if no entities governed by it
    for tok in doc:
        if tok.dep_ == "ROOT" and tok.pos_ == "VERB":
            if tok.lemma_ not in pred_to_args:
                pred_to_args[tok.lemma_] = {}

    return [
        {"predicate": pred, "arguments": args}
        for pred, args in pred_to_args.items()
    ]
