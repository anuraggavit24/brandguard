"""Simple rate limits kept in memory (one server process, as on Render).

hit(key, limit, window_seconds) records one attempt and says whether it is allowed. Limits reset when the
server restarts, which is acceptable here; limits that must survive a restart (uploads, invites) are counted
from the database instead, in main.py.
"""
import threading
import time

_hits = {}
_lock = threading.Lock()


def hit(key, limit, window):
    """Returns (allowed, seconds_until_next_allowed)."""
    now = time.time()
    with _lock:
        ts = [t for t in _hits.get(key, []) if now - t < window]
        if len(ts) >= limit:
            _hits[key] = ts
            return False, int(window - (now - ts[0])) + 1
        ts.append(now)
        _hits[key] = ts
        return True, 0


def reset():
    with _lock:
        _hits.clear()


def wait_text(seconds):
    m = max(1, round(seconds / 60))
    return f"{m} minute{'s' if m != 1 else ''}" if seconds >= 60 else f"{max(1, seconds)} seconds"
