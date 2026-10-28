"""Bearer tokens for the Excel bridge and add-in (auth design, section 5; plan task 8)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from analekh.api.main import app
from analekh.auth.service import create_user
from analekh.auth.tokens import create_api_token, revoke_api_token, user_for_api_token
from analekh.config import get_settings
from analekh.db.models import ApiToken
from analekh.db.session import get_session

GOOD = "Correct-Horse-Battery-9"
CSRF = {"X-Analekh-CSRF": "1"}


@pytest.fixture
def raw(db):
    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def user(db):
    return create_user(db, "kaushal@firm.in", "Kaushal", "analyst", GOOD)


@pytest.fixture
def signed_in(raw, user):
    res = raw.post("/auth/login", json={"email": "kaushal@firm.in", "password": GOOD})
    assert res.status_code == 200
    return raw


def test_token_is_shown_once_and_stored_hashed(db, user):
    row, token = create_api_token(db, user, "Office laptop")
    assert token not in (row.token_hash, row.name)
    assert db.scalar(select(ApiToken.token_hash).where(ApiToken.id == row.id)) != token
    assert user_for_api_token(db, token).id == user.id


def test_unknown_or_revoked_token_gives_nobody(db, user):
    row, token = create_api_token(db, user, "Office laptop")
    assert user_for_api_token(db, "not-a-token") is None
    revoke_api_token(db, user, row.id)
    assert user_for_api_token(db, token) is None


def test_cannot_revoke_someone_elses_token(db, user):
    other = create_user(db, "arjun@firm.in", "Arjun", "analyst", GOOD)
    row, token = create_api_token(db, other, "Arjun laptop")
    assert revoke_api_token(db, user, row.id) is False
    assert user_for_api_token(db, token).id == other.id


def test_disabled_user_token_stops_working(db, user):
    _, token = create_api_token(db, user, "Office laptop")
    user.is_active = False
    db.flush()
    assert user_for_api_token(db, token) is None


def test_create_list_and_revoke_over_http(signed_in):
    made = signed_in.post("/auth/tokens", json={"name": "Office laptop"}, headers=CSRF)
    assert made.status_code == 201
    token = made.json()["token"]
    listed = signed_in.get("/auth/tokens").json()
    assert [t["name"] for t in listed] == ["Office laptop"]
    assert all("token" not in t and "token_hash" not in t for t in listed)
    gone = signed_in.delete(f"/auth/tokens/{made.json()['id']}", headers=CSRF)
    assert gone.status_code == 204
    assert TestClient(app).get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_bearer_token_authenticates_and_carries_role(signed_in, raw):
    token = signed_in.post("/auth/tokens", json={"name": "x"}, headers=CSRF).json()["token"]
    fresh = TestClient(app)  # no cookie
    me = fresh.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and me.json()["role"] == "analyst"


def test_bearer_request_needs_no_csrf_header(signed_in):
    token = signed_in.post("/auth/tokens", json={"name": "x"}, headers=CSRF).json()["token"]
    fresh = TestClient(app)
    out = fresh.post("/auth/tokens", json={"name": "second"}, headers={"Authorization": f"Bearer {token}"})
    assert out.status_code == 201


def test_token_in_the_query_string_is_ignored(signed_in):
    token = signed_in.post("/auth/tokens", json={"name": "x"}, headers=CSRF).json()["token"]
    fresh = TestClient(app)
    assert fresh.get(f"/auth/me?token={token}").status_code == 401
    assert fresh.get("/auth/me", headers={"Authorization": "Bearer "}).status_code == 401


def test_bridge_sends_the_token_in_a_header(monkeypatch):
    from analekh.excel_bridge.cli import _api

    monkeypatch.setenv("ANALEKH_TOKEN", "ak_example")
    get_settings.cache_clear()
    try:
        client = _api()
        assert client.headers["Authorization"] == "Bearer ak_example"
        assert "ak_example" not in str(client.base_url)
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
