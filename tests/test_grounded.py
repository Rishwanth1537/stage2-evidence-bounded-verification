"""Tests for the 'grounded' verification mode and the deterministic value check (NLI model is mocked)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from server.pipeline.value_check import unmatched_values, value_tokens, value_veto
from server.proxy.interceptor import InterceptingToolProxy, RiskLevel
from server.tools.verify_grounded import run_grounded_verification


def _ent(score):
    return patch("server.tools.verify_grounded.entailment.score_claim", return_value=score)


def test_value_tokens_normalise_commas_decimals_versions_and_times():
    assert value_tokens("pay $1,200 at 3 PM for v2.4.1") == ["1200", "3pm", "2.4.1"]
    assert value_tokens("5.0 units") == ["5"]


def test_unmatched_values_detects_changed_numbers():
    assert unmatched_values("sent $3225", "transferred $3200") == ["3225"]
    assert unmatched_values("version 2.4.1", "version 2.4.0") == ["2.4.1"]
    assert unmatched_values("15 degrees", "15 degrees today, 7 yesterday") == []
    assert not value_veto("no digits here", "or here 42")


def test_grounded_passes_when_entailed_and_values_match():
    with _ent(0.95):
        r = run_grounded_verification("On Monday Alice sent $50 to Bob.", "Alice transferred $50 to Bob on Monday.")
    assert r.is_consistent and r.mismatched_spans == [] and r.factual_consistency_score == 0.95


def test_grounded_blocks_value_mutation_even_if_nli_accepts():
    with _ent(0.998):
        r = run_grounded_verification("Alice sent $500 to Bob.", "Alice transferred $50 to Bob.")
    assert not r.is_consistent
    assert [m.span for m in r.mismatched_spans] == ["500"]
    assert r.factual_consistency_score == 0.0


def test_grounded_blocks_low_entailment_without_values():
    with _ent(0.01):
        r = run_grounded_verification("Alice did not pay Bob.", "Alice paid Bob.")
    assert not r.is_consistent and len(r.mismatched_spans) == 1
    assert "not entailed" in r.mismatched_spans[0].issue


def test_grounded_reports_missing_user_constraints():
    with _ent(0.9):
        r = run_grounded_verification("Alice sent money to Bob.", "Alice sent money to Bob.", user_query="Send 50 to Bob")
    assert not r.is_consistent
    assert any("Constraint" in m.issue for m in r.mismatched_spans)


def test_proxy_uses_grounded_mode_when_requested():
    called = []
    def tool(**kw):
        called.append(kw); return "ok"
    proxy = InterceptingToolProxy(tool_fn=tool, risk_level=RiskLevel.HIGH, logic_mode="grounded")
    with _ent(0.99):
        blocked = proxy.call({"x": 1}, reasoning_context="Pay $500.", source_context="Pay $50.")
        passed = proxy.call({"x": 1}, reasoning_context="Pay $50.", source_context="Pay $50.")
    assert blocked.blocked and not called[:0]
    assert not passed.blocked and len(called) == 1
