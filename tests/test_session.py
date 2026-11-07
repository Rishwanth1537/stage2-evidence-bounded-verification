"""Unit tests for session tracker."""
import pytest
import statistics
from server.session.tracker import record, get_rolling_mean, is_drifting, clear_session


def setup_function():
    for sid in ["test_mean", "test_drift", "test_single", "test_window"]:
        clear_session(sid)


def test_no_session_returns_none():
    assert get_rolling_mean("nonexistent_session_xyz") is None


def test_single_score_recorded():
    record("test_single", 0.8)
    assert get_rolling_mean("test_single") == pytest.approx(0.8)


def test_rolling_mean_arithmetic():
    scores = [0.9, 0.8, 0.7, 0.6, 0.5]
    for s in scores:
        record("test_mean", s)
    expected = statistics.mean(scores[-5:])
    assert get_rolling_mean("test_mean") == pytest.approx(expected)


def test_window_truncation():
    for i in range(7):
        record("test_window", float(i) / 10)
    # deque maxlen=5, so only last 5 are kept
    mean = get_rolling_mean("test_window")
    expected = statistics.mean([0.2, 0.3, 0.4, 0.5, 0.6])
    assert mean == pytest.approx(expected)


def test_drift_alert_below_threshold():
    for s in [0.3, 0.3, 0.3, 0.3, 0.3]:
        record("test_drift", s)
    assert is_drifting("test_drift", drift_threshold=0.60) is True


def test_no_drift_above_threshold():
    clear_session("test_nodrift")
    for s in [0.9, 0.9, 0.9]:
        record("test_nodrift", s)
    assert is_drifting("test_nodrift", drift_threshold=0.60) is False


def test_no_drift_at_exact_threshold():
    clear_session("test_exact")
    for s in [0.60, 0.60, 0.60]:
        record("test_exact", s)
    # strictly below — equal should NOT trigger
    assert is_drifting("test_exact", drift_threshold=0.60) is False


def test_empty_session_not_drifting():
    assert is_drifting("empty_session_xyz") is False
