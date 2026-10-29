"""Polite HTTP client: descriptive User-Agent, timeouts, rate limit, exponential backoff (9.2-9.3).

Design rule (section 3.2): only published RSS feeds, equity list CSVs and files feeds link to,
plus NSE Indices' constituent CSVs (added 2026-10-13, sectors), the integrated-filing lookup on
www.nseindia.com (added 2026-10-14: results feed stopped carrying filings) and its corporate
financial-results list (added 2026-10-15, results history before integrated filings, XBRL back to
2018). Both owner-approved, queried per company. No other NSE page or JSON endpoint, no crawling:
host and path allow-lists enforce it.
"""

import re
import threading
import time
from dataclasses import dataclass

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from analekh.config import get_settings

ALLOWED_HOSTS = {
    "nsearchives.nseindia.com",
    "archives.nseindia.com",
    "niftyindices.com",
    "www.niftyindices.com",
    "www.nseindia.com",
    "sebi.gov.in",
    "www.sebi.gov.in",
}
SEBI_PATHS = (
    "/sebiweb/home/HomeAction.do",
    "/filings/public-issues/",
    "/sebi_data/attachdocs/",
)
ALLOWED_PATHS = {
    "niftyindices.com": ("/IndexConstituent/",),
    "www.niftyindices.com": ("/IndexConstituent/",),
    "www.nseindia.com": (
        "/",
        "/api/integrated-filing-results",
        "/api/corporates-financial-results",
    ),
    "sebi.gov.in": SEBI_PATHS,
    "www.sebi.gov.in": SEBI_PATHS,
}


def path_allowed(host: str, path: str) -> bool:
    rules = ALLOWED_PATHS.get(host)
    if rules is None:
        return True
    return any(path == rule if rule == "/" else path.startswith(rule) for rule in rules)


RETRY_STATUSES = {429, 500, 502, 503, 504}

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_CONTACT = re.compile(r"\s*\([^)]*(?:@|https?://)[^)]*\)|\s*(?:https?://\S+|[\w.+-]+@\S+)")


def identity_headers(user_agent: str, contact_email: str | None = None) -> dict[str, str]:
    """User-Agent and From headers. NSE's CDN never answers a request whose User-Agent holds an
    email address or a URL (seen 2026-10-14; it stalls instead of refusing), so any contact found
    there moves to the From header, which is where HTTP puts the requester's email."""
    contact = contact_email or next(iter(_EMAIL.findall(user_agent)), None)
    headers = {"User-Agent": _CONTACT.sub("", user_agent).strip() or "Analekh"}
    if contact:
        headers["From"] = contact
    return headers


class DisallowedHostError(ValueError):
    pass


@dataclass
class FetchResult:
    status: int
    content: bytes
    etag: str | None
    last_modified: str | None

    @property
    def not_modified(self) -> bool:
        return self.status == 304


class RateLimiter:
    def __init__(self, per_second: float) -> None:
        self.interval = 1.0 / per_second if per_second > 0 else 0.0
        self._next = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delay = self._next - now
            self._next = max(now, self._next) + self.interval
        if delay > 0:
            time.sleep(delay)


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in RETRY_STATUSES


BLOCKED_STATUSES = {401, 403, 429}


def refused(exc: BaseException) -> bool:
    """A sign that NSE is blocking or throttling us, as opposed to one bad file."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in BLOCKED_STATUSES
    return isinstance(exc, httpx.TransportError)  # incl. timeouts


class PoliteClient:
    def __init__(
        self,
        extra_allowed_hosts: set[str] | None = None,
        transport: httpx.BaseTransport | None = None,
        max_attempts: int | None = None,
        backoff_base: float = 2.0,
        rate_per_second: float | None = None,
    ) -> None:
        s = get_settings()
        self.allowed = ALLOWED_HOSTS | (extra_allowed_hosts or set())
        self.limiter = RateLimiter(rate_per_second or s.download_rate_per_second)
        self.client = httpx.Client(
            headers={**identity_headers(s.user_agent, s.contact_email), "Accept": "*/*"},
            timeout=s.http_timeout_seconds,
            follow_redirects=True,
            max_redirects=s.http_max_redirects,
            transport=transport,
            event_hooks={"request": [lambda request: self._check(request.url)]},  # every hop
        )
        self._get = retry(
            retry=retry_if_exception(_retryable),
            stop=stop_after_attempt(max_attempts or s.http_max_attempts),
            wait=wait_exponential(multiplier=backoff_base, max=60),
            reraise=True,
        )(self._get_once)

    def get(
        self,
        url: str,
        etag: str | None = None,
        last_modified: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> FetchResult:
        self._check(httpx.URL(url))
        headers = dict(headers or {})
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        result: FetchResult = self._get(url, headers)
        return result

    def _check(self, url: httpx.URL) -> None:
        """Rule 1 allow-list. Runs before the first request and again on every redirect hop."""
        if url.host not in self.allowed:
            raise DisallowedHostError(f"{url.host} is not an allowed source host")
        if not path_allowed(url.host, url.path):
            raise DisallowedHostError(f"{url.path} is not an allowed path on {url.host}")

    def _get_once(self, url: str, headers: dict[str, str]) -> FetchResult:
        self.limiter.wait()
        resp = self.client.get(url, headers=headers)
        if resp.status_code != 304:
            resp.raise_for_status()
        return FetchResult(
            resp.status_code,
            resp.content,
            resp.headers.get("ETag"),
            resp.headers.get("Last-Modified"),
        )
