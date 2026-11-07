"""
Session-level safety drift tracker.

Maintains a per-session deque of consistency scores (in-memory only).
Thread-safe via a single Lock.

G6 fix: Sessions now carry a last-accessed timestamp and are cleaned up
automatically when the accumulated count exceeds MAX_SESSIONS (LRU eviction)
or when clear_expired() is called explicitly.  This prevents unbounded
memory growth in long-lived servers serving many short-lived agent sessions.
"""
from __future__ import annotations
import threading
import statistics
import time
from collections import deque, OrderedDict
from typing import Dict, Optional, Tuple

# --- Configuration constants -----------------------------------------------
_DEFAULT_WINDOW = 5
_DEFAULT_DRIFT_THRESHOLD = 0.60

# Max number of concurrent in-memory sessions before LRU eviction kicks in.
MAX_SESSIONS = 10_000

# Sessions not accessed within this many seconds are considered expired.
SESSION_TTL_SECONDS = 3600  # 1 hour
# ---------------------------------------------------------------------------

# _sessions maps  session_id → (deque[float], last_access_timestamp)
_sessions: OrderedDict[str, Tuple[deque, float]] = OrderedDict()
_lock = threading.Lock()


def _touch(session_id: str) -> None:
    """Update the last-access timestamp for an existing session (caller holds lock)."""
    if session_id in _sessions:
        data, _ = _sessions[session_id]
        _sessions[session_id] = (data, time.monotonic())
        _sessions.move_to_end(session_id)  # LRU: most-recent at end


def record(session_id: str, score: float, window: int = _DEFAULT_WINDOW) -> None:
    """Append a consistency score to the session trajectory."""
    with _lock:
        if session_id not in _sessions:
            # Evict oldest session when at capacity
            while len(_sessions) >= MAX_SESSIONS:
                _sessions.popitem(last=False)  # remove LRU (front)
            _sessions[session_id] = (deque(maxlen=window), time.monotonic())
        data, _ = _sessions[session_id]
        data.append(score)
        _touch(session_id)


def get_rolling_mean(session_id: str, window: int = _DEFAULT_WINDOW) -> Optional[float]:
    """
    Return arithmetic mean of the last `window` scores for this session,
    or None if the session does not exist.
    """
    with _lock:
        entry = _sessions.get(session_id)
        if entry is None:
            return None
        data, _ = entry
        _touch(session_id)
        last = list(data)[-window:]
    if not last:
        return None
    return statistics.mean(last)


def is_drifting(
    session_id: str,
    drift_threshold: float = _DEFAULT_DRIFT_THRESHOLD,
    window: int = _DEFAULT_WINDOW,
) -> bool:
    """
    Return True iff the rolling mean is STRICTLY below drift_threshold.
    Returns False if the session has no recorded scores.
    """
    mean = get_rolling_mean(session_id, window)
    if mean is None:
        return False
    return mean < drift_threshold


def clear_session(session_id: str) -> None:
    """Remove a session (test utility / explicit cleanup)."""
    with _lock:
        _sessions.pop(session_id, None)


def clear_expired(ttl: float = SESSION_TTL_SECONDS) -> int:
    """
    Remove all sessions not accessed within `ttl` seconds.
    Returns the number of sessions removed.
    Intended to be called periodically (e.g., via a background thread or
    a scheduled task at the application level).
    """
    cutoff = time.monotonic() - ttl
    removed = 0
    with _lock:
        expired = [sid for sid, (_, ts) in _sessions.items() if ts < cutoff]
        for sid in expired:
            del _sessions[sid]
            removed += 1
    return removed


def session_count() -> int:
    """Return current number of tracked sessions (useful for metrics/health checks)."""
    with _lock:
        return len(_sessions)
