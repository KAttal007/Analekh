"""First password and password rules on the sign-in path (first-password design)."""

import logging
from pathlib import Path

import pytest
from sqlalchemy import func, select

from analekh.auth.passwords import check_password_rules
from analekh.auth.service import create_user, login
from analekh.db.models import User
from tests.test_auth_passwords_rules import ATTACKS


@pytest.mark.parametrize("pw", ATTACKS)
def test_attack_strings_store_and_sign_in_exactly(db, pw, caplog):
    caplog.set_level(logging.DEBUG)
    assert check_password_rules(pw) == []
    user = create_user(db, "a@firm.in", "A", "analyst", pw)
    assert user.password_hash and pw not in user.password_hash
    assert login(db, "a@firm.in", pw).user is user
    assert login(db, "a@firm.in", pw + "x").user is None
    assert db.scalar(select(func.count()).select_from(User)) >= 1  # tables intact
    assert pw not in caplog.text


def test_no_raw_sql_in_auth_routes_and_service():
    root = Path(__file__).resolve().parents[1] / "analekh"
    paths = list((root / "auth").rglob("*.py"))
    paths += [root / "api" / "routers" / "auth.py", root / "api" / "routers" / "users.py"]
    for path in paths:
        src = path.read_text(encoding="utf-8")
        assert "text(" not in src.replace("context(", ""), path
        assert 'execute("' not in src and "execute('" not in src, path


# --- issue, send, expire, clear (service layer) -----------------------------------------------

from datetime import UTC, datetime, timedelta  # noqa: E402

from analekh.auth import first_password, reset  # noqa: E402
from analekh.auth.passwords import verify_password  # noqa: E402
from analekh.auth.service import (  # noqa: E402
    create_user_with_first_password,
    set_password,
)
from analekh.config import get_settings  # noqa: E402
from analekh.db.models import AuthSession  # noqa: E402

NEW_VALID = "Brand-New-Passw0rd-Ok"
T0 = datetime(2026, 10, 23, 9, 0, tzinfo=UTC)


class Sent:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self.ok = True

    @property
    def body(self) -> str:
        return self.calls[-1][2]

    @property
    def subject(self) -> str:
        return self.calls[-1][1]


@pytest.fixture
def sent(monkeypatch):
    box = Sent()

    def fake(to, subject, body):
        box.calls.append((to, subject, body))
        return box.ok

    monkeypatch.setattr("analekh.alerts.mail.send_mail", fake)
    monkeypatch.setattr("analekh.auth.reset.send_mail", fake)
    return box


@pytest.fixture
def user_with_first(db, sent):
    return create_user_with_first_password(db, "new@firm.in", "New", "analyst")


def test_add_user_makes_first_password_and_sends_once(db, sent):
    user, plain = create_user_with_first_password(db, "new@firm.in", "New", "analyst")
    assert user.must_change_password and user.first_password_expires_at is not None
    assert verify_password(plain, user.password_hash)
    assert check_password_rules(plain) == []
    assert len(sent.calls) == 0  # issuing does not send; the caller sends
    assert first_password.send(user, plain, first=True) is True
    assert len(sent.calls) == 1
    assert "new@firm.in" in sent.body and plain in sent.body
    assert sent.subject == "Your Analekh account"
    assert plain not in repr(user)


def test_first_password_works_until_changed_then_dies(db, user_with_first):
    user, plain = user_with_first
    first = login(db, user.email, plain)
    assert first.ok and first.must_change_password is True
    set_password(db, user, NEW_VALID)
    assert user.must_change_password is False and user.first_password_expires_at is None
    assert login(db, user.email, plain).ok is False
    again = login(db, user.email, NEW_VALID)
    assert again.ok and again.must_change_password is False


def test_expired_first_password_refused(db, user_with_first):
    user, plain = user_with_first
    hours = get_settings().first_password_hours
    later = datetime.now(UTC) + timedelta(hours=hours, seconds=1)
    res = login(db, user.email, plain, now=later)
    assert res.ok is False and res.reason == "first_password_expired" and res.token is None
    # a wrong password still gets the plain reply, not the expiry message
    assert login(db, user.email, plain + "x", now=later).reason == "bad_credentials"


def test_mail_failure_still_issues(db, sent):
    sent.ok = False
    user, _plain = create_user_with_first_password(db, "n2@firm.in", "N", "analyst")
    assert first_password.send_now(db, user, first=True) is False
    assert user.must_change_password and user.password_hash


def test_send_now_commits_and_returns_sent(db, sent):
    user, _ = create_user_with_first_password(db, "n3@firm.in", "N", "analyst")
    assert first_password.send_now(db, user, first=False) is True
    assert sent.subject == "Your Analekh password was reset"


def test_send_first_password_ends_sessions_and_clears_block(db, sent):
    user = create_user(db, "b@firm.in", "B", "analyst", "Old-Passw0rd-Is-Fine1")
    assert login(db, user.email, "Old-Passw0rd-Is-Fine1").ok
    user.blocked, user.failed_count, user.paused_until = True, 9, T0 + timedelta(days=1)
    db.flush()
    t = datetime.now(UTC)
    plain = first_password.issue(db, user, now=t)
    assert user.blocked is False and user.failed_count == 0 and user.paused_until is None
    assert user.must_change_password is True
    assert user.first_password_expires_at == t + timedelta(
        hours=get_settings().first_password_hours
    )
    assert db.scalar(select(func.count()).select_from(AuthSession)) == 0
    assert not verify_password("Old-Passw0rd-Is-Fine1", user.password_hash)
    assert verify_password(plain, user.password_hash)


def test_forgot_password_confirm_clears_flag(db, user_with_first, sent):
    user, _plain = user_with_first
    assert reset.request_reset(db, user.email) is True
    code = sent.body.split("code is ")[1][:6]
    assert reset.confirm_reset(db, user.email, code, NEW_VALID) is True
    assert user.must_change_password is False and user.first_password_expires_at is None


def test_mail_has_no_html_and_no_link(db, sent, monkeypatch):
    monkeypatch.setenv("WEB_APP_URL", "")
    get_settings.cache_clear()
    user, plain = create_user_with_first_password(db, "n4@firm.in", "N", "analyst")
    for first in (True, False):
        first_password.send(user, plain, first=first)
        assert "<" not in sent.body and "http" not in sent.body
        assert "24 hours" in sent.body


def test_sign_in_address_only_when_set(db, sent, monkeypatch):
    monkeypatch.setenv("WEB_APP_URL", "analekh.firm.in")
    get_settings.cache_clear()
    user, plain = create_user_with_first_password(db, "n5@firm.in", "N", "analyst")
    first_password.send(user, plain, first=True)
    assert "analekh.firm.in" in sent.body and "http" not in sent.body


def test_microsoft_user_gets_no_first_password(db):
    user = create_user(db, "ms@firm.in", "M", "analyst", auth_kind="microsoft")
    assert user.password_hash is None and user.must_change_password is False


def test_weak_password_given_to_create_user_refused(db):
    with pytest.raises(ValueError):
        create_user(db, "w@firm.in", "W", "analyst", "short")


# --- the HTTP side: gate, rules route, first-password route -----------------------------------

import re  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from analekh.api.deps import FIRST_PASSWORD_ALLOWED  # noqa: E402
from analekh.api.main import app  # noqa: E402
from analekh.db.models import AuditEntry  # noqa: E402
from analekh.db.session import get_session  # noqa: E402

CSRF = {"X-Analekh-CSRF": "1"}


@pytest.fixture
def raw(db):
    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def flagged(db, raw):
    """A real signed-in session for a user who still has the emailed password."""
    user, plain = create_user_with_first_password(db, "new@firm.in", "New", "analyst")
    db.commit()
    res = raw.post("/auth/login", json={"email": user.email, "password": plain})
    assert res.status_code == 200 and res.json()["must_change_password"] is True
    return raw, user, plain


OPEN_PREFIXES = (
    "/auth/login",
    "/auth/reset/",
    "/auth/password-rules",
    "/public/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
)


def _routes(protected: bool):
    """(method, path template) for every route, from the OpenAPI document (the app nests its
    routers, so app.routes alone does not list them)."""
    for path, methods in app.openapi()["paths"].items():
        if path.startswith(OPEN_PREFIXES) is not protected:
            for method in sorted(methods):
                yield method.upper(), path


def _resolved(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "1", path)


def test_flagged_user_is_limited_to_four_routes(flagged):
    client, _user, _plain = flagged
    protected = list(_routes(True))
    assert len(protected) > 30
    for method, path in protected:
        if (method, path) in FIRST_PASSWORD_ALLOWED:
            continue
        res = client.request(method, _resolved(path), headers=CSRF)
        assert res.status_code == 403, (method, path, res.status_code)
        assert res.json()["detail"] == {"code": "password_change_required"}, (method, path)
    assert client.get("/auth/me").json()["must_change_password"] is True
    assert client.get("/auth/password-rules").status_code == 200


def test_gate_holds_for_bearer_tokens(db, raw):
    from analekh.auth import tokens

    user, _plain = create_user_with_first_password(db, "new@firm.in", "New", "analyst")
    user.must_change_password = False
    _row, token = tokens.create_api_token(db, user, "bridge")
    db.commit()
    bearer = {"Authorization": f"Bearer {token}"}
    assert raw.get("/companies/index", headers=bearer).status_code != 403
    user.must_change_password = True
    db.commit()
    res = raw.get("/companies/index", headers=bearer)
    assert res.status_code == 403 and res.json()["detail"] == {"code": "password_change_required"}
    assert raw.post("/auth/tokens", json={"name": "x"}, headers=bearer).status_code == 403


def test_gate_is_off_when_sign_in_is_off(db, raw, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    get_settings.cache_clear()
    from analekh.api.deps import _dev_user

    dev = _dev_user(db)
    dev.must_change_password = True  # even a flagged dev account is not gated
    db.flush()
    assert raw.get("/users").status_code == 200


def test_unflagged_user_is_not_gated(db, raw):
    create_user(db, "ok@firm.in", "Ok", "analyst", NEW_VALID)
    raw.post("/auth/login", json={"email": "ok@firm.in", "password": NEW_VALID})
    assert raw.get("/companies/index").status_code == 200
    assert raw.get("/auth/me").json()["must_change_password"] is False


def test_password_rules_endpoint_public_and_no_store(raw):
    res = raw.get("/auth/password-rules")
    assert res.status_code == 200 and res.headers["cache-control"] == "no-store"
    body = res.json()
    assert [r["id"] for r in body["rules"]] == [
        "length",
        "letters",
        "digits",
        "specials",
        "upper",
        "lower",
        "no_spaces",
    ]
    cfg = get_settings()
    assert body["max_length"] == cfg.password_max_length
    assert body["min_length"] == cfg.password_min_length
    assert body["combined"] and all(r["pattern"] for r in body["rules"])


def test_first_password_needs_sign_in(raw):
    res = raw.post(
        "/auth/first-password",
        json={"current_password": "a", "new_password": "b"},
        headers=CSRF,
    )
    assert res.status_code == 401


def test_first_password_route_rejects_31_chars_and_rule_failures(flagged, db):
    client, user, plain = flagged
    cfg = get_settings()
    long_pw = "Aa1!" + "x" * (cfg.password_max_length - 3)
    assert len(long_pw) == cfg.password_max_length + 1
    hashed = user.password_hash
    a = client.post(
        "/auth/first-password",
        json={"current_password": plain, "new_password": long_pw},
        headers=CSRF,
    )
    assert a.status_code == 400 and a.json()["missing"] == ["length"]
    weak = client.post(
        "/auth/first-password",
        json={"current_password": plain, "new_password": "alllowercaseletters"},
        headers=CSRF,
    )
    assert weak.status_code == 400 and "digits" in weak.json()["missing"]
    assert user.password_hash == hashed and user.failed_count == 0  # nothing hashed or counted
    # the reset route gives the very same message for the same input
    reset_res = client.post(
        "/auth/reset/confirm",
        json={"email": user.email, "code": "123456", "new_password": long_pw},
    )
    assert reset_res.status_code == 400
    assert reset_res.json()["detail"] == a.json()["detail"]


def test_first_password_same_as_first_is_refused(flagged):
    client, user, plain = flagged
    res = client.post(
        "/auth/first-password",
        json={"current_password": plain, "new_password": plain},
        headers=CSRF,
    )
    assert res.status_code == 400 and user.must_change_password


def test_wrong_current_password_counts_as_failure(flagged, db):
    client, user, _plain = flagged
    res = client.post(
        "/auth/first-password",
        json={"current_password": "Not-The-First-Pw-9x", "new_password": NEW_VALID},
        headers=CSRF,
    )
    assert res.status_code == 401 and res.json()["detail"] == "Email or password is incorrect."
    assert user.failed_count == 1 and user.must_change_password


def test_wrong_current_repeated_blocks_and_ends_session(flagged, db):
    client, user, _plain = flagged
    for _ in range(get_settings().login_block_after):
        client.post(
            "/auth/first-password",
            json={"current_password": "Not-The-First-Pw-9x", "new_password": NEW_VALID},
            headers=CSRF,
        )
    assert user.blocked
    assert client.get("/auth/me").status_code == 401


def test_first_password_success_then_normal_access(flagged, db):
    client, user, plain = flagged
    res = client.post(
        "/auth/first-password",
        json={"current_password": plain, "new_password": NEW_VALID},
        headers=CSRF,
    )
    assert res.status_code == 204
    assert not user.must_change_password and user.first_password_expires_at is None
    assert client.get("/auth/me").status_code == 401  # every session ended
    assert login(db, user.email, plain).ok is False
    fresh = TestClient(app)
    ok = fresh.post("/auth/login", json={"email": user.email, "password": NEW_VALID})
    assert ok.status_code == 200 and ok.json()["must_change_password"] is False
    assert fresh.get("/companies/index").status_code == 200
    assert "user.first_password_change" in set(db.scalars(select(AuditEntry.action)))


def test_first_password_route_refused_for_unflagged(db, raw):
    create_user(db, "ok@firm.in", "Ok", "analyst", NEW_VALID)
    raw.post("/auth/login", json={"email": "ok@firm.in", "password": NEW_VALID})
    res = raw.post(
        "/auth/first-password",
        json={"current_password": NEW_VALID, "new_password": NEW_VALID + "x"},
        headers=CSRF,
    )
    assert res.status_code == 400


def test_expired_first_password_message_at_login(db, raw):
    user, plain = create_user_with_first_password(db, "new@firm.in", "New", "analyst")
    user.first_password_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    res = raw.post("/auth/login", json={"email": user.email, "password": plain})
    assert res.status_code == 401
    assert (
        res.json()["detail"] == "This first password has expired. Ask an admin to send a new one."
    )


def test_allow_list_names_real_routes():
    every = {(m, p) for m, p in _routes(True)} | {(m, p) for m, p in _routes(False)}
    assert every >= FIRST_PASSWORD_ALLOWED
