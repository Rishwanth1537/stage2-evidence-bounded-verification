"""
Unit and regression tests for GroundingConfig (Prompt 5).

Verifies:
- Default GroundingConfig() produces byte-identical outputs to legacy behavior
  on a comprehensive fixed fixture set.
- Each normalizer switch independently enables and disables its specific normalization logic:
    * spelled_numbers
    * numeric_formats (commas, exponents, percent, multiplier suffixes)
    * iso_dates
    * spoken_dates_times
    * currency_equivalence
    * stemming
    * fuzzy_match (+ fuzzy_threshold)
    * token_set_containment
- all_off() enforces exact matching only.
"""
from __future__ import annotations

import pytest

from server.pipeline.arg_ground import (
    GroundingConfig,
    check_arguments,
    check_value,
)


FIXED_FIXTURES = [
    # 1. Spelled numbers
    ("qty", 12, "Please order twelve units.", "GROUNDED"),
    ("count", 45, "There were forty five attendees.", "GROUNDED"),
    # 2. Formatted numbers (commas, percentages, multipliers)
    ("amount", 1250.0, "The total cost is 1,250.00 dollars.", "GROUNDED"),
    ("rate", 0.05, "The discount rate is 5% off.", "GROUNDED"),
    ("users", 50000.0, "We have over 50k active users.", "GROUNDED"),
    ("negative_temp", -15.0, "Temperature dropped to -15 degrees.", "GROUNDED"),
    # 3. ISO dates & spoken dates
    ("date", "2024-05-12", "The meeting is on May 12th, 2024.", "GROUNDED"),
    # 4. ISO timestamp & spoken times
    ("time", "2024-05-12T14:30:00", "The meeting is on May 12th, 2024 at 2:30 pm.", "GROUNDED"),
    # 5. Currency equivalence
    ("currency", "usd", "The price is fifty dollars only.", "GROUNDED"),
    ("curr_eur", "eur", "Payment made in euros.", "GROUNDED"),
    # 6. Stemming
    ("action", "connecting", "We will connect to the server.", "GROUNDED"),
    # 7. Fuzzy matching (typo absorption)
    ("company", "amazonn", "Ship via amazon prime.", "GROUNDED"),
    # 8. Token-set containment
    ("items", "apples bananas", "The cart contains bananas and apples.", "GROUNDED"),
    # 9. Booleans, nulls, uncheckables
    ("active", True, "Any context here.", "UNCHECKABLE"),
    ("notes", None, "Any context here.", "UNCHECKABLE"),
    ("blank", "", "Any context here.", "UNCHECKABLE"),
    # 10. Ungrounded values (must remain UNGROUNDED)
    ("price", 999.0, "Approved price is 50 dollars.", "UNGROUNDED"),
    ("target", "Microsoft", "Ship via amazon prime.", "UNGROUNDED"),
]


def test_default_config_reproduces_legacy_behavior_identically():
    """Default GroundingConfig produces identical verdicts, reasons, and scores to config=None."""
    for arg, val, ctx, expected_verdict in FIXED_FIXTURES:
        v_none = check_value(arg, val, ctx, config=None)
        v_default = check_value(arg, val, ctx, config=GroundingConfig())
        v_all_on = check_value(arg, val, ctx, config=GroundingConfig.all_on())

        assert v_none.verdict == expected_verdict
        assert v_default.verdict == v_none.verdict
        assert v_default.score == v_none.score
        assert v_default.reason == v_none.reason

        assert v_all_on.verdict == v_none.verdict
        assert v_all_on.score == v_none.score
        assert v_all_on.reason == v_none.reason


def test_spelled_numbers_switch():
    ctx = "We need twelve items."
    v_on = check_value("count", 12, ctx, config=GroundingConfig(spelled_numbers=True))
    assert v_on.verdict == "GROUNDED"

    v_off = check_value("count", 12, ctx, config=GroundingConfig(spelled_numbers=False))
    assert v_off.verdict == "UNGROUNDED"


def test_numeric_formats_switch():
    # Comma separation
    ctx_comma = "Approved transfer of 1,500 dollars."
    v_on = check_value("amount", 1500.0, ctx_comma, config=GroundingConfig(numeric_formats=True))
    assert v_on.verdict == "GROUNDED"

    v_off = check_value("amount", 1500.0, ctx_comma, config=GroundingConfig(numeric_formats=False))
    assert v_off.verdict == "UNGROUNDED"

    # Multiplier suffix (50k)
    ctx_k = "We reached 50k users."
    v_k_on = check_value("users", 50000.0, ctx_k, config=GroundingConfig(numeric_formats=True))
    assert v_k_on.verdict == "GROUNDED"

    v_k_off = check_value("users", 50000.0, ctx_k, config=GroundingConfig(numeric_formats=False))
    assert v_k_off.verdict == "UNGROUNDED"

    # Percentage
    ctx_pct = "Discount rate is 10%."
    v_pct_on = check_value("rate", 0.10, ctx_pct, config=GroundingConfig(numeric_formats=True))
    assert v_pct_on.verdict == "GROUNDED"

    v_pct_off = check_value("rate", 0.10, ctx_pct, config=GroundingConfig(numeric_formats=False))
    assert v_pct_off.verdict == "UNGROUNDED"


def test_iso_dates_switch():
    ctx = "Scheduled on 2024-08-15."
    v_on = check_value("date", "2024-08-15", ctx, config=GroundingConfig(iso_dates=True))
    assert v_on.verdict == "GROUNDED"

    # When ISO dates switch is off, it falls back to raw string containment
    # "2024-08-15" exists in ctx so it matches via string containment
    # But if date format differs:
    ctx_spoken = "Scheduled on August 15, 2024."
    v_iso_on = check_value("date", "2024-08-15", ctx_spoken, config=GroundingConfig(iso_dates=True))
    assert v_iso_on.verdict == "GROUNDED"

    v_iso_off = check_value("date", "2024-08-15", ctx_spoken, config=GroundingConfig(iso_dates=False))
    assert v_iso_off.verdict == "UNGROUNDED"


def test_spoken_dates_times_switch():
    ctx_spoken = "The party is on August 15th, 2024 at 3 pm."
    # Spoken on: matches spoken date and 3 pm -> 15:00
    v_on = check_value("date", "2024-08-15T15:00:00", ctx_spoken, config=GroundingConfig(spoken_dates_times=True))
    assert v_on.verdict == "GROUNDED"

    # Spoken off: only numeric ISO / slash dates and 24h T times match
    v_off = check_value("date", "2024-08-15T15:00:00", ctx_spoken, config=GroundingConfig(spoken_dates_times=False))
    assert v_off.verdict == "UNGROUNDED"

    # But numeric ISO timestamp matches even when spoken_dates_times is False
    ctx_iso = "The party is on 2024-08-15T15:00:00."
    v_iso = check_value("date", "2024-08-15T15:00:00", ctx_iso, config=GroundingConfig(spoken_dates_times=False))
    assert v_iso.verdict == "GROUNDED"


def test_currency_equivalence_switch():
    ctx = "Please send fifty dollars to Alice."
    v_on = check_value("currency", "usd", ctx, config=GroundingConfig(currency_equivalence=True))
    assert v_on.verdict == "GROUNDED"

    v_off = check_value("currency", "usd", ctx, config=GroundingConfig(currency_equivalence=False))
    assert v_off.verdict == "UNGROUNDED"


def test_stemming_switch():
    ctx = "The system will connect automatically."
    # "connecting" stems to "connect"
    v_on = check_value("action", "connecting", ctx, config=GroundingConfig(stemming=True, fuzzy_match=False))
    assert v_on.verdict == "GROUNDED"

    v_off = check_value("action", "connecting", ctx, config=GroundingConfig(stemming=False, fuzzy_match=False))
    assert v_off.verdict == "UNGROUNDED"


def test_fuzzy_match_switch():
    ctx = "Partner with microsoft today."
    # "microzoft" has difflib ratio (16/18 = 0.8889) >= 0.88 with "microsoft" and is not a substring
    v_on = check_value("company", "microzoft", ctx, config=GroundingConfig(fuzzy_match=True, stemming=False, fuzzy_threshold=0.88))
    assert v_on.verdict == "GROUNDED"

    v_off = check_value("company", "microzoft", ctx, config=GroundingConfig(fuzzy_match=False, stemming=False))
    assert v_off.verdict == "UNGROUNDED"


def test_token_set_containment_switch():
    ctx = "Order consists of red and blue items."
    # Tokens "blue red" are a subset of ctx tokens but out of order and not stemmed
    v_on = check_value(
        "colors", "blue red", ctx,
        config=GroundingConfig(token_set_containment=True, stemming=False, fuzzy_match=False)
    )
    assert v_on.verdict == "GROUNDED"

    v_off = check_value(
        "colors", "blue red", ctx,
        config=GroundingConfig(token_set_containment=False, stemming=False, fuzzy_match=False)
    )
    assert v_off.verdict == "UNGROUNDED"


def test_all_off_exact_match_only():
    """all_off() disables all normalizers, requiring exact string / digit representation."""
    all_off_cfg = GroundingConfig.all_off()

    # Exact string match passes
    assert check_value("name", "Bob", "Hello Bob", config=all_off_cfg).verdict == "GROUNDED"
    # Exact number match passes
    assert check_value("amount", 50.0, "Cost is 50.0 dollars", config=all_off_cfg).verdict == "GROUNDED"

    # Normalized forms all fail under all_off:
    assert check_value("count", 12, "twelve items", config=all_off_cfg).verdict == "UNGROUNDED"
    assert check_value("amount", 1000.0, "1,000 dollars", config=all_off_cfg).verdict == "UNGROUNDED"
    assert check_value("curr", "usd", "50 dollars", config=all_off_cfg).verdict == "UNGROUNDED"
    assert check_value("action", "connecting", "connect now", config=all_off_cfg).verdict == "UNGROUNDED"
    assert check_value("carrier", "amazonn", "amazon", config=all_off_cfg).verdict == "UNGROUNDED"
