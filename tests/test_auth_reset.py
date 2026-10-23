"""Emailed one-time reset code (auth design, section 5; plan task 5)."""

import hashlib
import re
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from analekh.alerts import mail
from analekh.api.main import app
from analekh.auth import reset, service
from analekh.config import get_settings
from analekh.db.models import AuthSession, PasswordReset
from analekh.db.session import get_session

OLD = "Correct-Horse-Battery-9"
NEW = "Brand-New-Passphrase-4"
SAME = {"detail": "If that account exists, a code has been sent."}
NOT_SET_UP = {"detail": "Email is not set up. Contact the admin team."}


@pytest.fixture
def sent(monkeypatch):
    """Capture mail instead of sending it."""
    box: list[tuple[str, str, str]] = []

    def fake(to, subject, body):
        box.append((to, subject, body))
        return True

    monkeypatch.setattr(reset, "send_mail", fake)
    return box


@pytest.fixture
def user(db):
    return service.create_user(db, "kaushal@firm.in", "Kaushal", "analyst", OLD)


@pytest.fixture
def client(db):
    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _code(box) -> str:
    found = re.search(r"\b(\d{6})\b", box[-1][2])
    assert found is not None
    return found.group(1)


def _wrong(code: str) -> str:
    return f"{(int(code) + 1) % 10**6:06d}"


def test_request_reply_same_for_unknown_email(client, user, sent, monkeypatch):
    monkeypatch.setenv("SMTP_URL", "smtp://u:p@mail.example:587")
    get_settings.cache_clear()
    known = client.post("/auth/reset/request", json={"email": "kaushal@firm.in"})
    unknown = client.post("/auth/reset/request", json={"email": "nobody@firm.in"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json() == SAME
    assert len(sent) == 1 and sent[0][0] == "kaushal@firm.in"


def test_request_is_503_when_smtp_unset(client, user, sent, monkeypatch):
    monkeypatch.setenv("SMTP_URL", "")
    get_settings.cache_clear()
    res = client.post("/auth/reset/request", json={"email": "kaushal@firm.in"})
    assert res.status_code == 503 and res.json() == NOT_SET_UP
    assert sent == []


def test_second_code_invalidates_first(db, user, sent):
    from datetime import UTC, datetime, timedelta

    t0 = datetime.now(UTC)
    later = t0 + timedelta(seconds=get_settings().reset_request_cooldown_seconds + 1)
    assert reset.request_reset(db, "kaushal@firm.in", now=t0) is True
    first = _code(sent)
    assert reset.request_reset(db, "kaushal@firm.in", now=later) is True
    second = _code(sent)
    if first != second:  # equal only on a one-in-a-million draw
        assert reset.confirm_reset(db, "kaushal@firm.in", first, NEW) is False
    assert reset.confirm_reset(db, "kaushal@firm.in", second, NEW) is True


def test_five_wrong_codes_burn_the_reset(db, user, sent):
    limit = get_settings().reset_max_attempts
    reset.request_reset(db, "kaushal@firm.in")
    code = _code(sent)
    for _ in range(limit):
        assert reset.confirm_reset(db, "kaushal@firm.in", _wrong(code), NEW) is False
    assert reset.confirm_reset(db, "kaushal@firm.in", code, NEW) is False  # right code, too late
    assert service.login(db, "kaushal@firm.in", OLD).user is not None  # password unchanged


def test_code_expires_after_configured_minutes(db, user, sent):
    minutes = get_settings().reset_code_minutes
    start = datetime.now(UTC)
    reset.request_reset(db, "kaushal@firm.in", now=start)
    code = _code(sent)
    late = start + timedelta(minutes=minutes, seconds=1)
    assert reset.confirm_reset(db, "kaushal@firm.in", code, NEW, now=late) is False
    reset.request_reset(db, "kaushal@firm.in", now=start)
    code = _code(sent)
    ok = start + timedelta(minutes=minutes, seconds=-1)
    assert reset.confirm_reset(db, "kaushal@firm.in", code, NEW, now=ok) is True


def test_code_single_use(db, user, sent):
    reset.request_reset(db, "kaushal@firm.in")
    code = _code(sent)
    assert reset.confirm_reset(db, "kaushal@firm.in", code, NEW) is True
    assert reset.confirm_reset(db, "kaushal@firm.in", code, "Another-Passphrase-Ok-5") is False


def test_code_is_stored_only_as_sha256(db, user, sent):
    reset.request_reset(db, "kaushal@firm.in")
    code = _code(sent)
    row = db.get(PasswordReset, user.id)
    assert row is not None
    assert row.code_hash == hashlib.sha256(code.encode()).hexdigest()


def test_confirm_unblocks_and_ends_other_sessions(db, user, sent):
    live = service.login(db, "kaushal@firm.in", OLD)
    assert live.token is not None
    user.blocked, user.failed_count = True, get_settings().login_block_after
    user.paused_until = datetime.now(UTC) + timedelta(minutes=5)
    db.flush()
    assert service.login(db, "kaushal@firm.in", OLD).reason == "blocked"
    reset.request_reset(db, "kaushal@firm.in")
    assert reset.confirm_reset(db, "kaushal@firm.in", _code(sent), NEW) is True
    db.refresh(user)
    assert user.blocked is False and user.failed_count == 0 and user.paused_until is None
    assert db.scalars(select(AuthSession).where(AuthSession.user_id == user.id)).all() == []
    assert service.user_for_token(db, live.token) is None
    assert service.login(db, "kaushal@firm.in", NEW).user is not None


def test_mail_body_has_no_link(db, user, sent):
    reset.request_reset(db, "kaushal@firm.in")
    body = sent[-1][2]
    assert "http" not in body.lower() and "://" not in body and "www." not in body.lower()
    assert str(get_settings().reset_code_minutes) in body
    assert _code(sent) in body


def test_microsoft_account_gets_no_code(db, sent):
    service.create_user(db, "ms@firm.in", "M", "analyst", None, auth_kind="microsoft")
    assert reset.request_reset(db, "ms@firm.in") is False
    assert reset.request_reset(db, "nobody@firm.in") is False
    assert reset.request_reset(db, "not an email") is False
    assert sent == []
    assert db.scalars(select(PasswordReset)).all() == []


def test_confirm_route_204_then_400_and_attempts_persist(client, db, user, sent, monkeypatch):
    monkeypatch.setenv("SMTP_URL", "smtp://u:p@mail.example:587")
    get_settings.cache_clear()
    client.post("/auth/reset/request", json={"email": "kaushal@firm.in"})
    code = _code(sent)
    bad = client.post(
        "/auth/reset/confirm",
        json={"email": "kaushal@firm.in", "code": _wrong(code), "new_password": NEW},
    )
    assert bad.status_code == 400 and bad.json() == {"detail": "That code is not valid."}
    db.expire_all()
    row = db.get(PasswordReset, user.id)
    assert row is not None and row.attempts == 1
    ok = client.post(
        "/auth/reset/confirm",
        json={"email": "kaushal@firm.in", "code": code, "new_password": NEW},
    )
    assert ok.status_code == 204
    assert service.login(db, "kaushal@firm.in", NEW).user is not None


def test_confirm_refuses_overlong_password(client, user):
    res = client.post(
        "/auth/reset/confirm",
        json={"email": "kaushal@firm.in", "code": "123456", "new_password": "x" * 10_000},
    )
    assert res.status_code == 422


def test_send_mail_false_without_smtp(monkeypatch):
    monkeypatch.setenv("SMTP_URL", "")
    get_settings.cache_clear()
    assert mail.send_mail("a@b.in", "s", "b") is False


def test_send_mail_uses_smtp_settings_and_never_logs_body(monkeypatch, caplog):
    monkeypatch.setenv("SMTP_URL", "smtp://sender%40firm.in:pw@mail.example:2525")
    get_settings.cache_clear()
    seen: dict[str, object] = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            seen["host"], seen["port"] = host, port

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            pass

        def login(self, user, password):
            seen["user"] = user

        def send_message(self, msg):
            seen["to"], seen["from"] = msg["To"], msg["From"]
            raise OSError("boom SECRETBODY")

    monkeypatch.setattr(mail.smtplib, "SMTP", FakeSMTP)
    with caplog.at_level("DEBUG"):
        assert mail.send_mail("to@firm.in", "subj", "SECRETBODY 123456") is False
    assert seen["host"] == "mail.example" and seen["port"] == 2525
    assert seen["to"] == "to@firm.in" and seen["from"] == "sender@firm.in"
    assert "SECRETBODY" not in caplog.text


def test_one_request_per_cooldown_and_no_new_mail_inside_it(db, user, sent):
    """One reset mail per account per cooldown (default 2 minutes): time for the mail to arrive
    and the code to be typed. A request inside the cooldown sends nothing and keeps the code."""
    from datetime import UTC, datetime, timedelta

    t0 = datetime.now(UTC)
    assert reset.request_reset(db, "kaushal@firm.in", now=t0) is True
    code = _code(sent)
    assert reset.request_reset(db, "kaushal@firm.in", now=t0 + timedelta(seconds=60)) is False
    assert len(sent) == 1  # no second mail
    assert reset.confirm_reset(db, "kaushal@firm.in", code, NEW, now=t0 + timedelta(seconds=61))


def test_cooldown_reply_is_the_same_as_any_other(client, user, sent, monkeypatch):
    monkeypatch.setenv("SMTP_URL", "smtp://u:p@mail.example:587")
    get_settings.cache_clear()
    client_reset = client
    first = client_reset.post("/auth/reset/request", json={"email": "kaushal@firm.in"})
    again = client_reset.post("/auth/reset/request", json={"email": "kaushal@firm.in"})
    unknown = client_reset.post("/auth/reset/request", json={"email": "nobody@firm.in"})
    assert first.status_code == again.status_code == unknown.status_code == 202
    assert first.json() == again.json() == unknown.json() == SAME
    assert len(sent) == 1


def test_confirm_short_password_says_so_and_spends_no_attempt(client, user, sent, monkeypatch):
    monkeypatch.setenv("SMTP_URL", "smtp://u:p@mail.example:587")
    get_settings.cache_clear()
    client.post("/auth/reset/request", json={"email": "kaushal@firm.in"})
    code = _code(sent)
    short = client.post(
        "/auth/reset/confirm",
        json={"email": "kaushal@firm.in", "code": code, "new_password": "x" * 14},
    )
    assert short.status_code == 400
    assert short.json()["detail"].startswith("Password needs: 15 to 30 characters")
    ok = client.post(
        "/auth/reset/confirm",
        json={"email": "kaushal@firm.in", "code": code, "new_password": "Valid-Passw0rd-Here"},
    )
    assert ok.status_code == 204
