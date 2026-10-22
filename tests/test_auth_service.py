"""Sign-in service: sessions, failure tiers, disable (auth design, section 5)."""

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from analekh.auth import service
from analekh.auth.service import (
    create_user,
    login,
    logout,
    revoke_user_sessions,
    set_password,
    user_for_token,
)
from analekh.db.models import AuthSession, User

T0 = datetime(2026, 10, 22, 9, 0, tzinfo=UTC)
GOOD = "correct horse battery"


def _make(db, email="kaushal@firm.in", **kw):
    return create_user(db, email, "Kaushal", "analyst", kw.pop("password", GOOD), **kw)


def test_good_login_returns_token_and_stores_only_its_hash(db):
    user = _make(db)
    res = login(db, "kaushal@firm.in", GOOD, now=T0)
    assert res.ok and res.reason == "ok" and res.user is user and res.token
    stored = db.scalars(select(AuthSession.token_hash)).all()
    assert stored == [hashlib.sha256(res.token.encode()).hexdigest()]
    assert res.token not in stored


def test_third_failure_pauses_five_minutes(db):
    _make(db)
    for _ in range(3):
        assert login(db, "kaushal@firm.in", "wrong", now=T0).reason == "bad_credentials"
    res = login(db, "kaushal@firm.in", GOOD, now=T0)
    assert not res.ok and res.reason == "paused" and res.retry_after_seconds == 300
    assert res.token is None
    later = login(db, "kaushal@firm.in", GOOD, now=T0 + timedelta(minutes=5, seconds=1))
    assert later.ok


def test_two_more_failures_after_the_pause_block_the_account(db):
    """Hard limit of 5: 3 failures, a 5-minute pause, then 2 more wrong tries lock the account.
    The 4th failure does not start a second pause."""
    _make(db)
    for _ in range(3):
        login(db, "kaushal@firm.in", "wrong", now=T0)
    after = T0 + timedelta(minutes=5, seconds=1)
    fourth = login(db, "kaushal@firm.in", "wrong", now=after)
    assert fourth.reason == "bad_credentials"
    # no new pause after the 4th: the right password is not held back
    user = db.scalar(select(User).where(User.email == "kaushal@firm.in"))
    assert user.paused_until is not None and user.paused_until <= after
    fifth = login(db, "kaushal@firm.in", "wrong", now=after)
    assert fifth.reason == "bad_credentials"
    blocked = login(db, "kaushal@firm.in", GOOD, now=after)
    assert blocked.reason == "blocked" and not blocked.ok


def test_failures_during_the_pause_do_not_count_or_extend_it(db):
    _make(db)
    for _ in range(3):
        login(db, "kaushal@firm.in", "wrong", now=T0)
    for _ in range(10):  # hammering while paused is turned away, not counted
        assert (
            login(db, "kaushal@firm.in", "wrong", now=T0 + timedelta(minutes=1)).reason == "paused"
        )
    user = db.scalar(select(User).where(User.email == "kaushal@firm.in"))
    assert user.failed_count == 3 and user.blocked is False
    assert login(db, "kaushal@firm.in", GOOD, now=T0 + timedelta(minutes=5, seconds=1)).ok


def test_fifth_failure_blocks_until_set_password(db):
    user = _make(db)
    t = T0
    for _ in range(5):
        login(db, "kaushal@firm.in", "wrong", now=t)
        t += timedelta(minutes=6)
    res = login(db, "kaushal@firm.in", GOOD, now=t)
    assert res.reason == "blocked" and not res.ok and res.token is None
    set_password(db, user, "a brand new password")
    assert user.blocked is False and user.failed_count == 0 and user.paused_until is None
    assert login(db, "kaushal@firm.in", "a brand new password", now=t).ok


def test_microsoft_account_blocked_cannot_password_login(db):
    create_user(db, "ms@firm.in", "MS", "analyst", None, auth_kind="microsoft")
    for pw in ("", "anything", GOOD):
        res = login(db, "ms@firm.in", pw, now=T0)
        assert not res.ok and res.reason == "bad_credentials" and res.token is None
    assert db.scalar(select(func.count()).select_from(AuthSession)) == 0


def test_email_case_and_spaces_same_account(db):
    user = _make(db)
    res = login(db, " Kaushal@Firm.IN ", GOOD, now=T0)
    assert res.ok and res.user is user
    with pytest.raises((IntegrityError, ValueError)):
        _make(db, " Kaushal@Firm.IN ")
        db.flush()


def test_disabling_user_kills_live_session(db):
    user = _make(db)
    token = login(db, "kaushal@firm.in", GOOD, now=T0).token
    assert user_for_token(db, token, now=T0 + timedelta(minutes=1)) is user
    user.is_active = False
    db.flush()
    assert user_for_token(db, token, now=T0 + timedelta(minutes=2)) is None


def test_idle_9_hours_expires_session(db):
    _make(db)
    token = login(db, "kaushal@firm.in", GOOD, now=T0).token
    # activity keeps it alive: each call moves last_seen_at forward
    assert user_for_token(db, token, now=T0 + timedelta(hours=8)) is not None
    assert user_for_token(db, token, now=T0 + timedelta(hours=16)) is not None
    assert user_for_token(db, token, now=T0 + timedelta(hours=16, minutes=1)) is not None
    assert user_for_token(db, token, now=T0 + timedelta(hours=25, minutes=2)) is None
    assert user_for_token(db, "not-a-token", now=T0) is None


def test_session_dies_at_max_lifetime_even_when_active(db):
    _make(db)
    token = login(db, "kaushal@firm.in", GOOD, now=T0).token
    step = timedelta(hours=8)
    for i in (1, 2):  # active every 8 h: idle limit never trips
        assert user_for_token(db, token, now=T0 + step * i) is not None
    assert user_for_token(db, token, now=T0 + timedelta(hours=24, minutes=1)) is None


def test_sign_in_clears_that_users_expired_sessions(db):
    user = _make(db)
    old = login(db, "kaushal@firm.in", GOOD, now=T0).token
    later = T0 + timedelta(hours=30)
    new = login(db, "kaushal@firm.in", GOOD, now=later).token
    from analekh.db.models import AuthSession

    rows = db.query(AuthSession).filter_by(user_id=user.id).all()
    assert len(rows) == 1 and old != new


def test_success_resets_failure_count(db):
    user = _make(db)
    login(db, "kaushal@firm.in", "wrong", now=T0)
    login(db, "kaushal@firm.in", "wrong", now=T0)
    assert user.failed_count == 2
    assert login(db, "kaushal@firm.in", GOOD, now=T0).ok
    assert user.failed_count == 0 and user.paused_until is None


def test_injection_password_and_email_are_plain_bad_credentials(db):
    _make(db)
    for bad in ("' OR 1=1 --", "x'; DROP TABLE users;--"):
        for email, pw in (("kaushal@firm.in", bad), (bad, GOOD), (bad, bad)):
            res = login(db, email, pw, now=T0)
            assert (res.ok, res.token, res.user, res.reason, res.retry_after_seconds) == (
                False,
                None,
                None,
                "bad_credentials",
                None,
            )
    assert db.scalar(select(func.count()).select_from(User)) == 1


def test_unknown_email_is_reported_as_unknown(db):
    _make(db)
    unknown = login(db, "nobody@firm.in", "whatever", now=T0)
    wrong = login(db, "kaushal@firm.in", "whatever", now=T0)
    assert unknown == service.LoginResult(False, None, None, "unknown_email", None)
    assert wrong.reason == "bad_credentials"


def test_over_long_password_is_bad_credentials_not_counted_as_error(db):
    _make(db)
    res = login(db, "kaushal@firm.in", "x" * 10_000, now=T0)
    assert res.reason == "bad_credentials"


def test_logout_and_revoke_user_sessions(db):
    user = _make(db)
    t1 = login(db, "kaushal@firm.in", GOOD, now=T0).token
    t2 = login(db, "kaushal@firm.in", GOOD, now=T0).token
    logout(db, t1)
    assert user_for_token(db, t1, now=T0) is None
    assert user_for_token(db, t2, now=T0) is user
    assert revoke_user_sessions(db, user.id) == 1
    assert user_for_token(db, t2, now=T0) is None


def test_set_password_revokes_sessions(db):
    user = _make(db)
    token = login(db, "kaushal@firm.in", GOOD, now=T0).token
    set_password(db, user, "another password here")
    assert user_for_token(db, token, now=T0) is None


def test_disabled_user_cannot_login(db):
    user = _make(db)
    user.is_active = False
    db.flush()
    assert login(db, "kaushal@firm.in", GOOD, now=T0).reason == "bad_credentials"


def test_create_user_validates_role_and_email(db):
    with pytest.raises(ValueError):
        create_user(db, "x@firm.in", "X", "boss", GOOD)
    with pytest.raises(ValueError):
        create_user(db, "not an email", "X", "analyst", GOOD)


def test_auth_code_has_no_raw_sql():
    root = Path(service.__file__).parent
    for path in root.rglob("*.py"):
        src = path.read_text(encoding="utf-8")
        assert "text(" not in src.replace("context(", ""), path
        assert 'execute("' not in src and "execute('" not in src, path


def test_failure_policy_comes_from_settings(db, monkeypatch):
    """Thresholds are configuration, not constants: 2 failures pause 10 minutes, 4 block."""
    from analekh.config import get_settings

    monkeypatch.setenv("LOGIN_PAUSE_AFTER", "2")
    monkeypatch.setenv("LOGIN_BLOCK_AFTER", "4")
    monkeypatch.setenv("LOGIN_PAUSE_MINUTES", "10")
    get_settings.cache_clear()
    try:
        _make(db)
        for _ in range(2):
            login(db, "kaushal@firm.in", "wrong", now=T0)
        res = login(db, "kaushal@firm.in", GOOD, now=T0)
        assert res.reason == "paused" and res.retry_after_seconds == 600
        after = T0 + timedelta(minutes=10, seconds=1)
        for _ in range(2):
            login(db, "kaushal@firm.in", "wrong", now=after)
        assert login(db, "kaushal@firm.in", GOOD, now=after).reason == "blocked"
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_last_seen_written_at_most_once_a_minute(db):
    _make(db)
    res = login(db, "kaushal@firm.in", GOOD, now=T0)
    db.commit()
    token = res.token
    session = db.get(AuthSession, service._hash_token(token))
    first = session.last_seen_at
    service.user_for_token(db, token, now=T0 + timedelta(seconds=30))
    assert session.last_seen_at == first
    service.user_for_token(db, token, now=T0 + timedelta(seconds=61))
    assert session.last_seen_at == T0 + timedelta(seconds=61)
