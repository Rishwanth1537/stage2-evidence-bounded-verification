"""
Semantic graph construction from SRL frames + dependency triples.

Nodes  = entity/concept lemmas (kind="predicate" | "argument" | "token")
Edges  = labelled semantic relations (SRL arg roles + semantic dep roles)

Negation support:
    Predicate nodes carry a boolean `negated` attribute.  When a predicate
    is negated (e.g. "did not transfer"), its node is tagged `negated=True`.
    The GED cost model treats a negated-vs-non-negated predicate pair as
    maximally different (cost 1.0) even when they share the same lemma,
    preventing "Alice did NOT transfer $50" from matching "Alice transferred $50".

Role-swap support (via dep_parser):
    dep_parser.extract_dep_triples now maps nsubj→AGENT, dobj→PATIENT, etc.
    so that "Alice paid Bob" and "Bob paid Alice" produce graphs where
    Alice and Bob are connected to the predicate via *different* edge labels,
    making the two graphs topologically distinguishable to GED.

Content cache:
    Both SRL frame extraction and dep parsing are memoised on text content,
    so repeated calls with the same string (common in benchmark sweeps) are
    served from cache without a model forward pass.
"""
from __future__ import annotations

import functools
from typing import List, Dict

import networkx as nx

from .srl import extract_frames
from .dep_parser import extract_dep_triples
from .negation import find_negated_predicates


# Content-addressed graph cache — avoids rebuilding the same graph repeatedly
# in benchmark / threshold-sweep runs (same premise appears for many records).
@functools.lru_cache(maxsize=512)
def build_semantic_graph(text: str) -> nx.DiGraph:
    """
    Build a directed NetworkX DiGraph from `text`.

    Construction pipeline
    ─────────────────────
    1. SRL frame extraction  → predicate → argument edges (SRL arg roles)
    2. Dependency triples    → token → token edges (semantic dep roles)
    3. Negation detection    → mark negated predicates with ``negated=True``

    Node attributes
    ───────────────
    - ``kind``    : "predicate" | "argument" | "token"
    - ``negated`` : True if the predicate is negated; absent/False otherwise

    Edge attributes
    ───────────────
    - ``label`` : SRL role (e.g. "ARG0", "MONEY") or semantic dep
                  (e.g. "AGENT", "PATIENT", "nmod") from dep_parser

    Example
    ───────
    "Alice did not transfer $50 to Bob."
    Predicate node: ``transfer`` with ``negated=True``
    Edges: transfer→Alice (AGENT), transfer→$50 (MONEY), transfer→Bob (OBLIQUE)
    """
    G = nx.DiGraph()

    # ── 1. spaCy parse (shared by SRL + negation — parse text once) ─────────
    from .srl import _load_nlp  # reuse the cached spaCy model
    nlp = _load_nlp()
    doc = nlp(text)

    # ── 2. Negation: find which predicate lemmas are negated ─────────────────
    negated_predicates = find_negated_predicates(doc)

    # ── 3. SRL edges ─────────────────────────────────────────────────────────
    for frame in extract_frames(text):
        pred = frame["predicate"]
        is_negated = pred in negated_predicates
        G.add_node(pred, kind="predicate", negated=is_negated)
        for role, span in frame["arguments"].items():
            G.add_node(span, kind="argument")
            G.add_edge(pred, span, label=role)

    # ── 4. Dependency edges (with semantic role mapping) ─────────────────────
    for head, role_label, child in extract_dep_triples(text):
        if not G.has_node(head):
            G.add_node(head, kind="token")
        if not G.has_node(child):
            G.add_node(child, kind="token")
        G.add_edge(head, child, label=role_label)

    return G
