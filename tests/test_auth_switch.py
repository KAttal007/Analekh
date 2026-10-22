"""The development switch that turns sign-in off (AUTH_ENABLED=false).

It must default to on, work only when ENV=dev, and never leave a way to sign in as the
development user with a password.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from analekh.api.main import app
from analekh.config import get_settings
from analekh.db.models import User
from analekh.db.session import get_session


@pytest.fixture
def raw(db):
    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def switch(monkeypatch):
    """Set the environment, clear the settings cache before and after."""

    def set_env(**env: str) -> None:
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()

    yield set_env
    monkeypatch.undo()
    get_settings.cache_clear()


def test_sign_in_is_on_by_default(raw):
    assert get_settings().auth_enabled is True
    assert raw.get("/auth/me").status_code == 401
    assert raw.get("/public/auth-status").json() == {"auth_enabled": True}


def test_switch_off_in_dev_acts_as_the_dev_admin(raw, db, switch):
    switch(AUTH_ENABLED="false", ENV="dev")
    me = raw.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == get_settings().default_user_id
    assert me.json()["role"] == "admin"
    assert raw.get("/public/auth-status").json() == {"auth_enabled": False}
    # state-changing requests need no anti-forgery header while sign-in is off
    assert raw.post("/auth/logout").status_code == 204


def test_dev_user_is_created_once(raw, db, switch):
    switch(AUTH_ENABLED="false", ENV="dev")
    raw.get("/auth/me")
    raw.get("/auth/me")
    count = db.scalar(
        select(func.count()).select_from(User).where(User.id == get_settings().default_user_id)
    )
    assert count == 1


def test_dev_user_cannot_sign_in_with_a_password(raw, db, switch):
    switch(AUTH_ENABLED="false", ENV="dev")
    raw.get("/auth/me")  # creates the dev user
    switch(AUTH_ENABLED="true")
    res = raw.post(
        "/auth/login", json={"email": get_settings().dev_user_email, "password": "anything"}
    )
    assert res.status_code == 401


def test_switch_is_ignored_outside_dev(raw, switch):
    switch(AUTH_ENABLED="false", ENV="prod")
    assert raw.get("/auth/me").status_code == 401
    assert raw.get("/public/auth-status").json() == {"auth_enabled": True}


def test_start_up_refuses_the_switch_outside_dev(switch):
    from analekh.api.deps import check_auth_switch

    switch(AUTH_ENABLED="false", ENV="prod")
    with pytest.raises(RuntimeError, match="AUTH_ENABLED"):
        check_auth_switch()
    switch(AUTH_ENABLED="false", ENV="dev")
    check_auth_switch()  # allowed in dev
    switch(AUTH_ENABLED="true", ENV="prod")
    check_auth_switch()  # on is always allowed


def test_dev_identity_comes_from_settings(raw, db, switch):
    switch(
        AUTH_ENABLED="false",
        ENV="dev",
        DEV_USER_EMAIL="me@my-machine.test",
        DEV_USER_NAME="My Laptop",
    )
    me = raw.get("/auth/me").json()
    assert me["email"] == "me@my-machine.test" and me["name"] == "My Laptop"
