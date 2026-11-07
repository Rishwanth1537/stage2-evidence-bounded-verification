"""
Negation detection module.

Identifies negated predicates in a spaCy doc and returns their lemmas.
A predicate is considered negated when it has a direct `neg` dependency
child (e.g., "did not transfer", "never execute", "is not aligned").

Used by graph_builder to mark predicate nodes with a `negated=True`
attribute, which in turn raises the GED cost when comparing a negated
predicate against a non-negated one with the same lemma.
"""
from __future__ import annotations
from typing import Set
import spacy


def find_negated_predicates(doc: spacy.tokens.Doc) -> Set[str]:
    """
    Return the set of predicate lemmas that are negated in `doc`.

    A lemma is included if any of its dependency children has dep_ == "neg".

    Example::

        "Alice did not transfer $50 to Bob."
        → {"transfer"}   # "not" is a neg child of "transfer"

        "Alice transferred $50 to Bob."
        → set()          # no negation present
    """
    negated: Set[str] = set()
    for token in doc:
        if token.dep_ == "neg":
            # The head of a neg token is the negated predicate
            negated.add(token.head.lemma_)
    return negated
