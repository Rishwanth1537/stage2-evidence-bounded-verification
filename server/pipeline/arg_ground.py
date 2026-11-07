"""
Argument-level grounding: verify each (argument, value) of a planned tool call against the conversation that preceded it.

Verdicts per argument
    GROUNDED     the value (normalised) is supported by the context
    UNGROUNDED   a checkable value that the context does not support        -> the only verdict that can block a call
    UNCHECKABLE  booleans, empty values, and structures this module does not interpret (never block)

Matching is type-aware and deterministic:
    numbers   digits with separators/decimals normalised, spelled-out numbers up to 99 and simple multiples ("twelve",
              "forty five", "a hundred"), percentages, k/m suffixes
    strings   case-/space-/punctuation-insensitive containment, token-set containment, and fuzzy token match
              (difflib ratio >= FUZZY) to absorb typos, plural forms and minor re-spellings; light stemming (running/run)
    typed normalisers: ISO dates and timestamps against written dates and clock times ("2 pm" = T14:00), ISO-4217 currency
    codes against currency names (JPY = Japanese yen)
This replaces exact string comparison (as used by simple argument-grounding checks) with normalised matching, which is what
keeps the false-block rate low on real conversations where values are paraphrased or reformatted.

Limitations (documented, not hidden): no world knowledge ("MSFT" for "Microsoft" is UNGROUNDED), no unit conversion,
no multi-hop arithmetic ("500 miles" derived from two numbers in the context), English only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

FUZZY = 0.88

_ONES = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}
_NUM_TOKEN = re.compile(r"(?<![\w.])(?:(?<![\w])(-)(?=\d))?(\d[\d,]*(?:\.\d+)?)\s*(k|m|million|thousand|%)?", re.I)
_PUNCT = re.compile(r"[^\w\s]")
_WS = re.compile(r"\s+")

_ARG_GROUND_SKIPPED_NUMERIC: int = 0


@dataclass(frozen=True)
class GroundingConfig:
    """
    Configuration flags for typed normalizers in argument grounding.

    Defaults preserve existing behavior exactly.
    """
    spelled_numbers: bool = True
    numeric_formats: bool = True  # commas, exponents, percent, multiplier suffixes
    iso_dates: bool = True
    spoken_dates_times: bool = True
    currency_equivalence: bool = True
    stemming: bool = True
    fuzzy_match: bool = True
    fuzzy_threshold: float = 0.88
    token_set_containment: bool = True

    @classmethod
    def all_on(cls, fuzzy_threshold: float = 0.88) -> GroundingConfig:
        """All normalizers active (default behavior)."""
        return cls(fuzzy_threshold=fuzzy_threshold)

    @classmethod
    def all_off(cls, fuzzy_threshold: float = 0.88) -> GroundingConfig:
        """All normalizers disabled (exact string & digit match only)."""
        return cls(
            spelled_numbers=False,
            numeric_formats=False,
            iso_dates=False,
            spoken_dates_times=False,
            currency_equivalence=False,
            stemming=False,
            fuzzy_match=False,
            fuzzy_threshold=fuzzy_threshold,
            token_set_containment=False,
        )

    @classmethod
    def leave_one_out(cls, disabled_switch: str, fuzzy_threshold: float = 0.88) -> GroundingConfig:
        """All normalizers active except the specified disabled_switch."""
        switches = [
            "spelled_numbers", "numeric_formats", "iso_dates", "spoken_dates_times",
            "currency_equivalence", "stemming", "fuzzy_match", "token_set_containment"
        ]
        if disabled_switch not in switches:
            raise ValueError(f"Unknown switch: '{disabled_switch}'. Expected one of {switches}")
        kwargs = {s: True for s in switches}
        kwargs[disabled_switch] = False
        kwargs["fuzzy_threshold"] = fuzzy_threshold
        return cls(**kwargs)

    @classmethod
    def add_one_in(cls, enabled_switch: str, fuzzy_threshold: float = 0.88) -> GroundingConfig:
        """All normalizers disabled except the specified enabled_switch."""
        switches = [
            "spelled_numbers", "numeric_formats", "iso_dates", "spoken_dates_times",
            "currency_equivalence", "stemming", "fuzzy_match", "token_set_containment"
        ]
        if enabled_switch not in switches:
            raise ValueError(f"Unknown switch: '{enabled_switch}'. Expected one of {switches}")
        kwargs = {s: False for s in switches}
        kwargs[enabled_switch] = True
        kwargs["fuzzy_threshold"] = fuzzy_threshold
        return cls(**kwargs)


DEFAULT_GROUNDING_CONFIG = GroundingConfig()


@dataclass
class ArgVerdict:
    argument: str
    value: Any
    verdict: str          # GROUNDED | UNGROUNDED | UNCHECKABLE
    reason: str = ""
    score: float = 1.0    # match strength in [0, 1]; strings use the best fuzzy ratio, numbers and typed values are 0 or 1


class VerdictList(list):
    """
    Subclass of list for check_arguments results that preserves backward-compatible list
    behavior while exposing degraded mode flags.
    """
    def __init__(self, items=(), skipped_numeric_tokens: int = 0, degraded: bool = False, degraded_reasons: Optional[List[str]] = None):
        super().__init__(items)
        self.skipped_numeric_tokens = skipped_numeric_tokens
        self.degraded = degraded
        self.degraded_reasons = list(degraded_reasons or [])


def _norm_text(s: str) -> str:
    return _WS.sub(" ", _PUNCT.sub(" ", str(s).lower())).strip()


def _spelled_numbers(text: str) -> set:
    toks = _norm_text(text).replace("-", " ").split()
    out, i = set(), 0
    while i < len(toks):
        t = toks[i]
        if t in _ONES:
            out.add(float(_ONES[t]))
        elif t in _TENS:
            val = _TENS[t]
            if i + 1 < len(toks) and toks[i + 1] in _ONES and 0 < _ONES[toks[i + 1]] < 10:
                val += _ONES[toks[i + 1]]
            out.add(float(val))
        elif t in ("hundred", "thousand", "million"):
            mult = {"hundred": 100, "thousand": 1000, "million": 1_000_000}[t]
            base = float(_ONES.get(toks[i - 1], 1)) if i > 0 and toks[i - 1] in _ONES else 1.0
            out.add(base * mult)
        i += 1
    return out


def numbers_in_detailed(text: str, config: Optional[GroundingConfig] = None) -> Tuple[set, int]:
    """
    Extract numbers from text and return (numbers_set, skipped_unparseable_count).
    Unparseable numeric regex matches are skipped, but counted to surface verifier degradation.
    """
    cfg = config or DEFAULT_GROUNDING_CONFIG
    vals = set()
    skipped = 0
    if cfg.numeric_formats:
        for m in _NUM_TOKEN.finditer(text):
            try:
                v = float(m.group(2).replace(",", ""))
            except ValueError:
                skipped += 1
                continue
            suf = (m.group(3) or "").lower()
            if suf in ("k", "thousand"):
                vals.add(v * 1e3)
            elif suf in ("m", "million"):
                vals.add(v * 1e6)
            vals.add(v)
            if suf == "%":
                vals.add(v / 100.0)
            if m.group(1):                       # explicit minus sign: also admit the negative value (latitudes, deltas, temperatures)
                vals.update({-x for x in list(vals) if x > 0})
    else:
        # Exact numeric tokens only: pure digits / basic floats without commas, suffixes, or multipliers
        for m in re.finditer(r"(?<![\w.])(?:(?<![\w])(-)(?=\d))?(\d+(?:\.\d+)?)\b", text):
            try:
                v = float(m.group(2))
            except ValueError:
                skipped += 1
                continue
            vals.add(v)
            if m.group(1):
                vals.add(-v)

    if cfg.spelled_numbers:
        vals = vals | _spelled_numbers(text)

    return (vals, skipped)


def numbers_in(text: str, config: Optional[GroundingConfig] = None) -> set:
    global _ARG_GROUND_SKIPPED_NUMERIC
    vals, skipped = numbers_in_detailed(text, config=config)
    if skipped > 0:
        _ARG_GROUND_SKIPPED_NUMERIC += skipped
    return vals


def get_arg_ground_degraded_status(context: str = "") -> Tuple[bool, List[str]]:
    """Returns (degraded, reasons) for argument grounding."""
    skipped = 0
    if context:
        _, skipped = numbers_in_detailed(context)
    else:
        global _ARG_GROUND_SKIPPED_NUMERIC
        skipped = _ARG_GROUND_SKIPPED_NUMERIC
    if skipped > 0:
        return True, [f"unparseable numeric token(s) skipped: {skipped}"]
    return False, []


def _fuzzy_score(value_norm: str, context_norm: str, config: Optional[GroundingConfig] = None) -> float:
    """1.0 if the value is contained (or its tokens are all present); otherwise the best difflib ratio over context windows."""
    cfg = config or DEFAULT_GROUNDING_CONFIG
    if not value_norm or value_norm in context_norm:
        return 1.0
    vt, ct = value_norm.split(), context_norm.split()
    if cfg.token_set_containment and set(vt) <= set(ct):
        return 1.0
    if not cfg.fuzzy_match:
        return 0.0
    n, best = len(vt), 0.0
    sm = SequenceMatcher(None, "", value_norm)          # seq2 = the value; seq1 = each window (difflib caches seq2 statistics)
    for w in range(max(1, n - 1), n + 2):
        for i in range(0, max(1, len(ct) - w + 1)):
            sm.set_seq1(" ".join(ct[i:i + w]))
            if sm.real_quick_ratio() <= best or sm.quick_ratio() <= best:   # upper bounds: cannot beat the best so far
                continue
            best = max(best, sm.ratio())
            if best >= 1.0:
                return 1.0
    return best


_CURRENCY = {
    "usd": ["us dollar", "us dollars", "united states dollar", "dollar", "dollars", "usd", "bucks"],
    "eur": ["euro", "euros", "eur"], "gbp": ["pound", "pounds", "british pound", "british pounds", "sterling", "gbp"],
    "jpy": ["yen", "japanese yen", "jpy"], "inr": ["rupee", "rupees", "indian rupee", "indian rupees", "inr"],
    "cad": ["canadian dollar", "canadian dollars", "cad"], "aud": ["australian dollar", "australian dollars", "aud"],
    "chf": ["swiss franc", "swiss francs", "franc", "francs", "chf"], "cny": ["yuan", "renminbi", "chinese yuan", "cny", "rmb"],
    "mxn": ["mexican peso", "mexican pesos", "peso", "pesos", "mxn"], "krw": ["won", "korean won", "south korean won", "krw"],
    "brl": ["brazilian real", "brazilian reais", "real", "reais", "brl"], "rub": ["ruble", "rubles", "rouble", "russian ruble", "rub"],
    "sek": ["swedish krona", "krona", "sek"], "nok": ["norwegian krone", "krone", "nok"], "dkk": ["danish krone", "dkk"],
    "nzd": ["new zealand dollar", "nzd", "kiwi dollar"], "sgd": ["singapore dollar", "sgd"], "hkd": ["hong kong dollar", "hkd"],
    "zar": ["south african rand", "rand", "zar"], "try": ["turkish lira", "lira", "try"], "aed": ["dirham", "dirhams", "aed"],
}
_SUFFIXES = ("ing", "ed", "es", "s")


def _stem(w: str) -> str:
    for suf in _SUFFIXES:
        if len(w) > len(suf) + 2 and w.endswith(suf):
            w = w[: -len(suf)]
            break
    if len(w) > 3 and w[-1] == w[-2] and w[-1] not in "aeiou":
        w = w[:-1]
    return w


def _stems(text_norm: str) -> set:
    return {_stem(t) for t in text_norm.split()}


_ISO = re.compile(r"^\s*(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?\s*(?:Z|[+-]\d{2}:?\d{2})?\s*$")
_CTX_TIME = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)|\b(\d{1,2}):(\d{2})\b", re.I)
_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]


def _context_times(context: str, spoken: bool = True) -> set:
    out = set()
    if spoken:
        for m in _CTX_TIME.finditer(context):
            if m.group(3):
                h, mi = int(m.group(1)) % 12, int(m.group(2) or 0)
                if m.group(3).lower().startswith("p"):
                    h += 12
                out.add((h, mi))
            else:
                out.add((int(m.group(4)), int(m.group(5))))
    for m in re.finditer(r"T(\d{2}):(\d{2})", context):
        out.add((int(m.group(1)), int(m.group(2))))
    return out


def _date_in(context: str, y: int, mo: int, d: int, spoken: bool = True) -> bool:
    c = context.lower()
    forms = [f"{y:04d}-{mo:02d}-{d:02d}", f"{mo}/{d}/{y}", f"{mo:02d}/{d:02d}/{y}", f"{d}/{mo}/{y}"]
    if any(f in c for f in forms):
        return True
    if not spoken:
        return False
    mn = _MONTHS[mo - 1]
    pat = rf"({mn}|{mn[:3]})\.?\s+{d}(st|nd|rd|th)?,?\s+{y}|{d}(st|nd|rd|th)?\s+(of\s+)?({mn}|{mn[:3]})\.?,?\s+{y}"
    return re.search(pat, c) is not None


def _check_iso(argument: str, value: str, context: str, config: Optional[GroundingConfig] = None) -> Optional[ArgVerdict]:
    cfg = config or DEFAULT_GROUNDING_CONFIG
    if not cfg.iso_dates:
        return None
    m = _ISO.match(value)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not _date_in(context, y, mo, d, spoken=cfg.spoken_dates_times):
        return ArgVerdict(argument, value, "UNGROUNDED", f"date {y:04d}-{mo:02d}-{d:02d} not found in context", 0.0)
    if m.group(4) is not None:
        t = (int(m.group(4)), int(m.group(5)))
        if t != (0, 0) and t not in _context_times(context, spoken=cfg.spoken_dates_times):
            return ArgVerdict(argument, value, "UNGROUNDED", f"time {t[0]:02d}:{t[1]:02d} not found in context", 0.0)
    return ArgVerdict(argument, value, "GROUNDED", "")


def _check_currency(argument: str, value: str, context: str, config: Optional[GroundingConfig] = None) -> Optional[ArgVerdict]:
    cfg = config or DEFAULT_GROUNDING_CONFIG
    if not cfg.currency_equivalence:
        return None
    key = value.strip().lower()
    if key not in _CURRENCY:
        return None
    ctx = _norm_text(context)
    names = _CURRENCY[key]
    if any(re.search(rf"(?<!\w){re.escape(n)}(?!\w)", ctx) for n in names) or key in ctx.split():
        return ArgVerdict(argument, value, "GROUNDED", "")
    return ArgVerdict(argument, value, "UNGROUNDED", f"currency {value} not mentioned in context", 0.0)


def check_value(argument: str, value: Any, context: str, config: Optional[GroundingConfig] = None) -> ArgVerdict:
    cfg = config or DEFAULT_GROUNDING_CONFIG
    if isinstance(value, bool) or value is None:
        return ArgVerdict(argument, value, "UNCHECKABLE", "boolean or null value")
    if isinstance(value, (int, float)):
        nums = numbers_in(context, config=cfg)
        ok = float(value) in nums or any(abs(float(value) - x) < 1e-9 for x in nums)
        return ArgVerdict(argument, value, "GROUNDED" if ok else "UNGROUNDED", "" if ok else f"number {value} not found in context", 1.0 if ok else 0.0)
    if isinstance(value, str):
        if not value.strip():
            return ArgVerdict(argument, value, "UNCHECKABLE", "empty string")
        # a purely numeric string is a number
        if re.fullmatch(r"\s*[\d,]+(?:\.\d+)?\s*", value):
            if cfg.numeric_formats:
                return check_value(argument, float(value.replace(",", "")), context, config=cfg)
            else:
                if "," not in value:
                    return check_value(argument, float(value), context, config=cfg)
        for special in (_check_iso, _check_currency):
            v = special(argument, value, context, config=cfg)
            if v is not None:
                return v
        vn, cn = _norm_text(value), _norm_text(context)
        if cfg.stemming and bool(vn) and (_stems(vn) <= _stems(cn)):
            sc = 1.0
        else:
            sc = _fuzzy_score(vn, cn, config=cfg)
        ok = sc >= cfg.fuzzy_threshold
        return ArgVerdict(argument, value, "GROUNDED" if ok else "UNGROUNDED", "" if ok else f"'{value}' not found in context", round(sc, 4))
    if isinstance(value, (list, tuple)):
        verdicts = [check_value(argument, v, context, config=cfg) for v in value]
        bad = [v for v in verdicts if v.verdict == "UNGROUNDED"]
        if bad:
            return ArgVerdict(argument, value, "UNGROUNDED", bad[0].reason, min(v.score for v in bad))
        return ArgVerdict(argument, value, "GROUNDED" if verdicts else "UNCHECKABLE")
    return ArgVerdict(argument, value, "UNCHECKABLE", f"unsupported type {type(value).__name__}")


def check_arguments(arguments: Dict[str, Any], context: str, config: Optional[GroundingConfig] = None) -> List[ArgVerdict]:
    cfg = config or DEFAULT_GROUNDING_CONFIG
    _, skipped = numbers_in_detailed(context, config=cfg)
    verdicts = [check_value(k, v, context, config=cfg) for k, v in arguments.items()]
    degraded = skipped > 0
    reasons = [f"unparseable numeric token(s) skipped: {skipped}"] if degraded else []
    return VerdictList(verdicts, skipped_numeric_tokens=skipped, degraded=degraded, degraded_reasons=reasons)


def call_is_grounded(
    arguments: Dict[str, Any],
    context: str,
    schema: Dict[str, Any] | None = None,
    policy: str = "strict",
    config: Optional[GroundingConfig] = None,
) -> bool:
    """
    policy "strict":        every checkable argument must be grounded.
    policy "required_only": only arguments the tool schema marks as required can block a call; an ungrounded OPTIONAL argument
                            (usually a model-chosen default such as a size or a category) is reported but does not block.
                            Needs `schema` = {"required": [...], "optional": [...]}; falls back to "strict" without it.
    """
    verdicts = check_arguments(arguments, context, config=config)
    if policy == "required_only" and schema:
        optional = set(schema.get("optional", []))
        return not any(v.verdict == "UNGROUNDED" and v.argument not in optional for v in verdicts)
    return not any(v.verdict == "UNGROUNDED" for v in verdicts)


def call_score(arguments: Dict[str, Any], context: str, config: Optional[GroundingConfig] = None) -> float:
    """Call-level grounding score in [0, 1]: the weakest match among the checkable arguments (1.0 if none are checkable)."""
    scores = [v.score for v in check_arguments(arguments, context, config=config) if v.verdict != "UNCHECKABLE"]
    return min(scores) if scores else 1.0


def conformal_threshold(gold_scores, alpha: float) -> float:
    """
    Split-conformal threshold for 'block iff call_score < tau'.  With n calibration scores from genuine calls
    (exchangeable with deployment calls), choosing tau as the k-th smallest score with k = floor(alpha * (n + 1))
    gives P(a new genuine call is blocked) <= alpha (finite-sample, distribution-free).  Returns 0.0 (never block)
    when alpha * (n + 1) < 1 or when more than alpha of genuine calls already score 0, i.e. when the requested false-block
    rate cannot be met by this stage; callers should report that instead of pretending otherwise.
    """
    import math
    xs = sorted(gold_scores)
    k = math.floor(alpha * (len(xs) + 1))
    if k < 1:
        return 0.0
    return xs[k - 1]
