"""
Deterministic value check: every number-like token in the hypothesis must also occur in the premise.

Why: whole-claim NLI is strong on meaning (negation, role swaps, entity swaps) but can accept near-identical numbers
("$3225" vs "$3200" scored 0.998 entailment in our ablation). A literal comparison of the value tokens catches exactly
that failure, is deterministic, and names the offending span.

Token classes (all normalised before comparison): money / plain numbers with thousands separators, decimals, percentages,
versions (v2.4.1), clock times (3 PM, 11:30 AM), and ordinal-free integers inside identifiers (order #881 -> 881).
Not handled (documented limitation): spelled-out numbers ("fifty"), unit conversion, ranges, relative dates.
"""
from __future__ import annotations

import re
from typing import List

_VERSION = r"v?\d+\.\d+(?:\.\d+)+"
_TIME = r"\d{1,2}:\d{2}\s?(?:[AaPp][Mm])?|\d{1,2}\s?[AaPp][Mm]\b"
_NUMBER = r"\d[\d,]*(?:\.\d+)?"
_TOKEN_RE = re.compile(rf"({_VERSION})|({_TIME})|({_NUMBER})")


def _norm(tok: str) -> str:
    t = tok.strip().lower().replace(" ", "")
    if re.fullmatch(_VERSION, t):
        return t.lstrip("v")
    t = t.replace(",", "")
    if re.fullmatch(r"\d+\.0+", t):
        t = t.split(".")[0]
    return t


def value_tokens(text: str) -> List[str]:
    """Normalised value tokens in order of appearance (duplicates kept)."""
    out: List[str] = []
    for m in _TOKEN_RE.finditer(text):
        raw = next(g for g in m.groups() if g)
        out.append(_norm(raw))
    return out


def unmatched_values(hypothesis: str, premise: str) -> List[str]:
    """Value tokens present in the hypothesis but absent from the premise (surface form from the hypothesis)."""
    prem = set(value_tokens(premise))
    missing: List[str] = []
    for m in _TOKEN_RE.finditer(hypothesis):
        raw = next(g for g in m.groups() if g)
        if _norm(raw) not in prem:
            missing.append(raw.strip())
    # de-duplicate, keep order
    seen, uniq = set(), []
    for x in missing:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def value_veto(hypothesis: str, premise: str) -> bool:
    """True if the hypothesis contains at least one value token that the premise does not."""
    return bool(unmatched_values(hypothesis, premise))
