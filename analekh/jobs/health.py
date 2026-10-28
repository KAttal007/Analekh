"""Is the background job queue reachable? Celery's .delay() keeps retrying the broker when Redis
is down, so the web app's Analyse button would wait without end. A quick connection test answers
at once instead (design doc 19.1: Analyse and Refresh run as background jobs)."""

import socket
import time
from urllib.parse import urlparse

from analekh.config import get_settings

TIMEOUT_SECONDS = 0.4
NOT_RUNNING = "Background jobs aren't running on this machine: they need Redis and a Celery worker, which come with hosting. Nothing was queued."


UP_FOR_SECONDS = 15.0  # how long "up" is trusted
DOWN_FOR_SECONDS = 5.0  # a down answer is rechecked sooner, so a started worker shows quickly
_cache: tuple[float, bool] | None = None  # (checked at, answer)


def _probe(timeout: float) -> bool:
    url = urlparse(get_settings().redis_url)
    try:
        with socket.create_connection((url.hostname or "localhost", url.port or 6379), timeout):
            return True
    except OSError:
        return False


def queue_available(timeout: float = TIMEOUT_SECONDS, *, fresh: bool = False) -> bool:
    """Cached for a few seconds: a failed name lookup (REDIS_URL pointing at a Docker hostname)
    takes 2-3 s on Windows whatever the timeout, and every company page asks. ``fresh`` skips the
    cache, for the moment a job is actually queued."""
    global _cache
    now = time.monotonic()
    if not fresh and _cache is not None:
        checked, answer = _cache
        if now - checked < (UP_FOR_SECONDS if answer else DOWN_FOR_SECONDS):
            return answer
    answer = _probe(timeout)
    _cache = (now, answer)
    return answer
