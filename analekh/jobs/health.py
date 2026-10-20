"""Is the background job queue reachable? Celery's .delay() keeps retrying the broker when Redis
is down, so the web app's Analyse button would wait without end. A quick connection test answers
at once instead (design doc 19.1: Analyse and Refresh run as background jobs)."""

import socket
from urllib.parse import urlparse

from analekh.config import get_settings

TIMEOUT_SECONDS = 0.4
NOT_RUNNING = (
    "Background jobs aren't running on this machine: they need Redis and a Celery worker, "
    "which come with hosting. Nothing was queued."
)


def queue_available(timeout: float = TIMEOUT_SECONDS) -> bool:
    url = urlparse(get_settings().redis_url)
    try:
        with socket.create_connection((url.hostname or "localhost", url.port or 6379), timeout):
            return True
    except OSError:
        return False
