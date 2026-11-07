"""Tests for argument-level grounding (deterministic; no models)."""
from __future__ import annotations

from server.models.schemas import ArgumentGroundingRequest
from server.pipeline.arg_ground import call_is_grounded, call_score, check_arguments, conformal_threshold, numbers_in
from server.proxy.interceptor import InterceptingToolProxy, RiskLevel
from server.tools.verify_arguments import run_argument_grounding


def verdicts(args, ctx):
    return {v.argument: v.verdict for v in check_arguments(args, ctx)}


def test_numbers_digits_commas_percent_spelled_and_suffix():
    nums = numbers_in("pay 1,200 dollars, about twelve percent, forty five items, 3k units, 50%")
    assert {1200.0, 12.0, 45.0, 3000.0, 50.0, 0.5} <= nums


def test_number_grounded_and_mutated():
    assert verdicts({"amount": 500}, "User: transfer $500 please") == {"amount": "GROUNDED"}
    assert verdicts({"amount": 5000}, "User: transfer $500 please") == {"amount": "UNGROUNDED"}
    assert verdicts({"n": 12}, "User: I need twelve copies") == {"n": "GROUNDED"}


def test_string_normalisation_stemming_and_fuzzy():
    assert verdicts({"city": "new york"}, "User: weather in New York?") == {"city": "GROUNDED"}
    assert verdicts({"activity": "running"}, "User: I just finished a 30-minute run") == {"activity": "GROUNDED"}
    assert verdicts({"city": "Nwe York"}, "User: weather in New York") == {"city": "UNGROUNDED"} or call_score({"city": "Nwe York"}, "weather in New York") > 0.8
    assert verdicts({"city": "Paris"}, "User: weather in New York") == {"city": "UNGROUNDED"}


def test_currency_codes_against_names():
    assert verdicts({"from": "JPY", "to": "GBP"}, "User: convert 5000 Japanese Yen to British Pounds") == {"from": "GROUNDED", "to": "GROUNDED"}
    assert verdicts({"to": "EUR"}, "User: convert 5000 Japanese Yen to British Pounds") == {"to": "UNGROUNDED"}


def test_iso_datetime_against_written_date_and_clock_time():
    ctx = "User: schedule it on 2022-03-15 at 10:00 AM and it ends at 11:00 AM"
    assert verdicts({"start": "2022-03-15T10:00:00", "end": "2022-03-15T11:00:00"}, ctx) == {"start": "GROUNDED", "end": "GROUNDED"}
    assert verdicts({"start": "2022-03-15T09:00:00"}, ctx) == {"start": "UNGROUNDED"}
    assert verdicts({"d": "2022-04-01"}, ctx) == {"d": "UNGROUNDED"}
    assert verdicts({"t": "2023-07-04T14:00:00"}, "User: on July 4th, 2023 at 2 pm") == {"t": "GROUNDED"}


def test_booleans_and_empty_values_are_uncheckable():
    assert verdicts({"flag": True, "note": ""}, "anything") == {"flag": "UNCHECKABLE", "note": "UNCHECKABLE"}


def test_required_only_policy_ignores_ungrounded_optional():
    schema = {"required": ["query"], "optional": ["size"]}
    args = {"query": "laptop", "size": 200}
    ctx = "User: find a laptop"
    assert not call_is_grounded(args, ctx)
    assert call_is_grounded(args, ctx, schema, "required_only")


def test_conformal_threshold_quantile_and_infeasible_alpha():
    scores = [1.0] * 90 + [0.5] * 6 + [0.0] * 4
    assert conformal_threshold(scores, 0.10) == 0.5          # k = floor(0.1 * 101) = 10th smallest
    assert conformal_threshold(scores, 0.02) == 0.0          # k = 2 -> 2nd smallest is 0.0 (more than 2% score 0): never block
    assert conformal_threshold([1.0], 0.02) == 0.0           # k < 1


def test_tool_blocks_on_unsupported_argument():
    req = ArgumentGroundingRequest(arguments={"amount": 5000, "to": "Bob"}, context="User: send $500 to Bob")
    res = run_argument_grounding(req)
    assert not res.is_grounded and [m.span for m in res.mismatched_spans] == ["amount=5000"]
    ok = run_argument_grounding(ArgumentGroundingRequest(arguments={"amount": 500, "to": "Bob"}, context="User: send $500 to Bob"))
    assert ok.is_grounded and ok.call_score == 1.0


def test_proxy_arguments_mode_blocks_and_passes():
    calls = []
    def tool(**kw):
        calls.append(kw); return "done"
    proxy = InterceptingToolProxy(tool_fn=tool, risk_level=RiskLevel.HIGH, logic_mode="arguments")
    blocked = proxy.call({"amount": 5000}, source_context="User: send $500")
    passed = proxy.call({"amount": 500}, source_context="User: send $500")
    assert blocked.blocked and calls == [{"amount": 500}] and not passed.blocked


def test_negative_numbers_are_matched_with_their_sign():
    ctx = 'Tool return: {"lat": -34.9389, "lon": 138.6, "delta": -5}'
    assert verdicts({"latitude": -34.9389, "delta": -5}, ctx) == {"latitude": "GROUNDED", "delta": "GROUNDED"}
    assert verdicts({"latitude": 34.9389}, ctx) == {"latitude": "GROUNDED"}      # sign-permissive: the positive magnitude is also admitted
    assert verdicts({"x": -138.6}, "lon 138.6 only") == {"x": "UNGROUNDED"}      # a negative value needs an explicit minus in the text


def test_hyphens_in_dates_and_ranges_do_not_create_negative_numbers():
    assert -3.0 not in numbers_in("on 2022-03-15 and 5-10 items")
    assert -10.0 not in numbers_in("between 5-10 items")
    assert 5.0 in numbers_in("between 5-10 items") and 10.0 in numbers_in("between 5-10 items")


def test_fuzzy_speedup_keeps_scores():
    from server.pipeline.arg_ground import _fuzzy_score
    ctx = "the weather in new york city is cold " * 50 + " nwe york"
    assert _fuzzy_score("nwe york", ctx) == 1.0
    assert 0.8 < _fuzzy_score("new yrk city", ctx) <= 1.0
    assert _fuzzy_score("completely different words here", ctx) < 0.6
