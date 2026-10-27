"""Failed sign-ins per client address, in memory (auth design, section 5).

Per-account lockout cannot see one address trying many accounts; this can. Also refuses a flooding
address before any password hashing. Counts are per API process: N workers = real limit up to N x
setting. Bounded: when too many addresses tracked, least recently active dropped.
"""

import math
import threading
import time
from collections import OrderedDict, deque

from analekh.config import get_settings

_failures: OrderedDict[str, deque[float]] = OrderedDict()
_lock = threading.Lock()


def _prune(hits: deque[float], now: float, window: float) -> None:
    while hits and now - hits[0] >= window:
        hits.popleft()


def clear() -> None:
    with _lock:
        _failures.clear()


def tracked() -> int:
    with _lock:
        return len(_failures)


def record_failure(ip: str) -> None:
    cfg = get_settings()
    now = time.monotonic()
    window = cfg.login_ip_window_minutes * 60
    with _lock:
        hits = _failures.pop(ip, None) or deque()
        _prune(hits, now, window)
        hits.append(now)
        _failures[ip] = hits  # most recently active last
        while len(_failures) > cfg.login_ip_max_tracked:
            _failures.popitem(last=False)


def retry_after(ip: str) -> int | None:
    """Seconds this address must wait, or None when it may try."""
    cfg = get_settings()
    now = time.monotonic()
    window = cfg.login_ip_window_minutes * 60
    with _lock:
        hits = _failures.get(ip)
        if not hits:
            return None
        _prune(hits, now, window)
        if len(hits) < cfg.login_ip_max_failures:
            return None
        return max(1, math.ceil(window - (now - hits[0])))
