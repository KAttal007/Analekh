"""Per-address limit on failed sign-ins: one address cannot try many accounts (the per-account
lockout does not see that), and a refused address costs no password hashing."""

import pytest
from fastapi.testclient import TestClient

from analekh.api.main import app
from analekh.auth import ip_limit
from analekh.auth.service import create_user
from analekh.config import get_settings
from analekh.db.session import get_session

GOOD = "correct horse battery"


@pytest.fixture(autouse=True)
def _fresh():
    ip_limit.clear()
    yield
    ip_limit.clear()


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setenv("LOGIN_IP_MAX_FAILURES", "4")
    get_settings.cache_clear()
    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _login(client, email, password="wrong-password-here"):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_one_address_trying_many_accounts_is_stopped(client, db):
    for i in range(6):
        create_user(db, f"u{i}@firm.in", f"U{i}", "analyst", GOOD)
    codes = [_login(client, f"u{i}@firm.in").status_code for i in range(6)]
    assert codes[:4] == [401, 401, 401, 401]  # four different accounts, one failure each
    assert codes[4:] == [429, 429]
    assert "Retry-After" in _login(client, "u5@firm.in").headers


def test_unknown_emails_count_too(client):
    codes = [_login(client, f"nobody{i}@firm.in").status_code for i in range(6)]
    assert codes[4:] == [429, 429]


def test_a_refused_address_is_refused_even_with_the_right_password(client, db):
    create_user(db, "a@firm.in", "A", "analyst", GOOD)
    for i in range(4):
        _login(client, f"nobody{i}@firm.in")
    assert _login(client, "a@firm.in", GOOD).status_code == 429


def test_successful_sign_ins_do_not_count(client, db):
    create_user(db, "a@firm.in", "A", "analyst", GOOD)
    for _ in range(10):
        assert _login(client, "a@firm.in", GOOD).status_code == 200


def test_the_window_expires(client, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(ip_limit.time, "monotonic", lambda: clock[0])
    for i in range(4):
        _login(client, f"nobody{i}@firm.in")
    assert _login(client, "nobody9@firm.in").status_code == 429
    clock[0] += get_settings().login_ip_window_minutes * 60 + 1
    assert _login(client, "nobody9@firm.in").status_code == 401


def test_other_addresses_are_not_affected(monkeypatch):
    monkeypatch.setenv("LOGIN_IP_MAX_FAILURES", "4")
    get_settings.cache_clear()
    for _ in range(4):
        ip_limit.record_failure("10.0.0.1")
    assert ip_limit.retry_after("10.0.0.1") is not None
    assert ip_limit.retry_after("10.0.0.2") is None


def test_tracking_is_bounded(monkeypatch):
    monkeypatch.setenv("LOGIN_IP_MAX_TRACKED", "5")
    get_settings.cache_clear()
    for i in range(50):
        ip_limit.record_failure(f"10.0.1.{i}")
    assert ip_limit.tracked() <= 5


def test_limits_come_from_settings():
    cfg = get_settings()
    assert cfg.login_ip_max_failures > cfg.login_block_after  # a shared office must not trip it
    assert cfg.login_ip_window_minutes > 0
