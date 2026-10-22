"""Public endpoints under load: cached answers, settings-driven limits, a fast 503 when the
database pool is exhausted (found by the 2026-10-22 load test: 100 concurrent calendar requests
waited 30 s for one of 15 connections)."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import TimeoutError as PoolTimeout

from analekh import schedule
from analekh.api.main import app
from analekh.api.routers import public
from analekh.config import get_settings
from analekh.db.session import get_engine, get_session


@pytest.fixture(autouse=True)
def _fresh_cache():
    public.clear_cache()
    yield
    public.clear_cache()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def calls(monkeypatch):
    """Counts how often the calendar really reaches the database."""
    seen: list[tuple[date, date]] = []
    real = schedule.events

    def counting(db, start, end, *a, **k):
        seen.append((start, end))
        return real(db, start, end, *a, **k)

    monkeypatch.setattr(schedule, "events", counting)
    return seen


def _cal(client, start="2026-03-01", end="2026-03-10"):
    return client.get("/public/calendar", params={"start": start, "end": end})


def test_repeat_calendar_requests_hit_the_database_once(client, calls):
    for _ in range(5):
        assert _cal(client).status_code == 200
    assert len(calls) == 1


def test_different_ranges_are_cached_separately(client, calls):
    _cal(client, "2026-03-01", "2026-03-10")
    _cal(client, "2026-04-01", "2026-04-10")
    _cal(client, "2026-03-01", "2026-03-10")
    assert len(calls) == 2


def test_calendar_cache_expires(client, calls, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(public.time, "monotonic", lambda: clock[0])
    _cal(client)
    clock[0] += get_settings().public_cache_seconds + 1
    _cal(client)
    assert len(calls) == 2


def test_cache_seconds_comes_from_settings(client, calls, monkeypatch):
    monkeypatch.setenv("PUBLIC_CACHE_SECONDS", "0")
    get_settings.cache_clear()
    _cal(client)
    _cal(client)
    assert len(calls) == 2


def test_cache_is_bounded(client, calls, monkeypatch):
    monkeypatch.setenv("PUBLIC_CACHE_MAX_ENTRIES", "3")
    get_settings.cache_clear()
    for day in range(1, 8):
        _cal(client, f"2026-03-{day:02d}", f"2026-03-{day:02d}")
    assert public.cache_size() <= 3


def test_a_rejected_range_is_not_cached_and_costs_no_query(client, calls):
    assert _cal(client, "2026-02-01", "2026-01-01").status_code == 422
    assert calls == []


def test_range_cap_comes_from_settings(client, monkeypatch):
    assert _cal(client, "2026-03-01", "2026-03-31").status_code == 200
    monkeypatch.setenv("PUBLIC_CALENDAR_MAX_DAYS", "10")
    get_settings.cache_clear()
    res = _cal(client, "2026-03-01", "2026-03-31")
    assert res.status_code == 422 and "10 days" in res.json()["detail"]


def test_exhausted_pool_answers_503_quickly(client, monkeypatch):
    def pool_full(*a, **k):
        raise PoolTimeout("QueuePool limit of size 20 overflow 20 reached, connection timed out")

    monkeypatch.setattr(schedule, "events", pool_full)
    res = _cal(client)
    assert res.status_code == 503
    assert res.headers["retry-after"]
    assert "busy" in res.json()["detail"].lower()
    assert "QueuePool" not in res.text  # no internals in the reply


def test_pool_is_sized_from_settings_and_fails_fast(monkeypatch):
    monkeypatch.setenv("DB_POOL_SIZE", "7")
    monkeypatch.setenv("DB_POOL_OVERFLOW", "3")
    monkeypatch.setenv("DB_POOL_TIMEOUT_SECONDS", "2.5")
    get_settings.cache_clear()
    get_engine.cache_clear()
    try:
        pool = get_engine().pool
        assert pool.size() == 7  # type: ignore[attr-defined]
        assert pool._max_overflow == 3  # type: ignore[attr-defined]
        assert pool._timeout == 2.5  # type: ignore[attr-defined]
    finally:
        get_engine.cache_clear()


def test_pool_is_at_least_as_big_as_the_worker_thread_limit():
    """Waiting threads must not be able to starve the connections that would free them."""
    cfg = get_settings()
    assert cfg.db_pool_size + cfg.db_pool_overflow >= cfg.api_thread_limit
