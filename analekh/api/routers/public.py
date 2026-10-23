"""Public NSE-derived data for the sign-in screen: counts and this week's calendar, nothing
user-specific (no watchlist marks). Everything else needs a session (auth design, section 6)."""

import threading
import time
from collections.abc import Callable
from dataclasses import asdict
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from analekh import schedule
from analekh.api.deps import DB
from analekh.config import get_settings
from analekh.desk import desk

router = APIRouter(prefix="/public", tags=["public"])

# One answer per key, shared by every visitor and kept for `public_cache_seconds`. Each worker
# process has its own copy. Bounded, so distinct ranges cannot grow it without limit.
_cache: dict[tuple, tuple[float, object]] = {}
_cache_lock = threading.Lock()


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def cache_size() -> int:
    with _cache_lock:
        return len(_cache)


def _cached[T](key: tuple, build: Callable[[], T]) -> T:
    cfg = get_settings()
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit is not None and now - hit[0] < cfg.public_cache_seconds:
            return hit[1]  # type: ignore[return-value]
    value = build()
    with _cache_lock:
        _cache[key] = (now, value)
        while len(_cache) > cfg.public_cache_max_entries:
            _cache.pop(next(iter(_cache)))  # oldest first
    return value


class WelcomeOut(BaseModel):
    companies_in_scope: int
    filings_total: int
    reported: int
    quarter_label: str | None
    latest_filed_at: datetime | None


class PublicEventOut(BaseModel):
    date: date
    kind: Literal["results", "meeting", "concall"]
    symbol: str
    name: str
    sector: str | None
    purpose: str | None
    source_url: str | None
    status: Literal["scheduled", "filed"] = "scheduled"
    revised: bool = False


class PublicCalendarOut(BaseModel):
    start: date
    end: date
    events: list[PublicEventOut]


@router.get("/auth-status")
def auth_status() -> dict[str, bool]:
    """Whether sign-in is on, so the web app can skip the sign-in screen in development."""
    from analekh.api.deps import auth_is_off

    return {"auth_enabled": not auth_is_off()}


@router.get("/welcome", response_model=WelcomeOut)
def welcome(db: DB) -> WelcomeOut:
    """Cached: the sign-in screen is opened often and the counts move slowly."""

    def build() -> WelcomeOut:
        d = desk(db, limit=1)
        return WelcomeOut(
            companies_in_scope=d.companies_in_scope,
            filings_total=d.filings_total,
            reported=d.reported,
            quarter_label=d.quarter_label,
            latest_filed_at=d.latest_filed_at,
        )

    return _cached(("welcome",), build)


@router.get("/calendar", response_model=PublicCalendarOut)
def calendar(
    db: DB,
    start: date | None = None,
    end: date | None = None,
    kind: Literal["results", "meeting", "concall"] | None = None,
) -> PublicCalendarOut:
    today = date.today()
    start = start or today - timedelta(days=2)
    end = end or start + timedelta(days=45)
    limit = get_settings().public_calendar_max_days
    if end < start or (end - start).days > limit:
        raise HTTPException(422, f"end must be after start, within {limit} days")

    def build() -> PublicCalendarOut:
        found = schedule.events(db, start, end)  # no watchlist user: nothing personal
        rows = []
        for e in found:
            if kind and e.kind != kind:
                continue  # the sign-in screen asks for results only: a smaller reply
            data = asdict(e)
            data.pop("watched")
            rows.append(PublicEventOut(**data))
        return PublicCalendarOut(start=start, end=end, events=rows)

    return _cached(("calendar", start, end, kind), build)
