"""Sign-in service: sessions, failure tiers, disable (auth design, section 5).

SQLAlchemy bound parameters only. Tokens random; only SHA-256 stored. Functions flush, never
commit: caller commits, also after a failed sign-in so failure counters persist. `now` is a
parameter so tests control time.
"""

import hashlib
import math
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal, NamedTuple, cast

from sqlalchemy import ColumnElement, delete, func, select
from sqlalchemy.orm import Session

from analekh.auth.devices import valid_device_key
from analekh.auth.passwords import (
    hash_password,
    normalize_email,
    validate_new_password,
    verify_password,
)
from analekh.auth.tokens import revoke_all_api_tokens
from analekh.config import get_settings
from analekh.db.models import AuthSession, SignInChoice, User, UserDevice, new_device_id

Role = Literal["admin", "analyst"]
ROLES: tuple[Role, ...] = ("admin", "analyst")


def role_of(user: User) -> Role:
    """The user's role, typed. The column's CHECK constraint allows only these two values."""
    return cast(Role, user.role)


LAST_SEEN_WRITE_EVERY = timedelta(minutes=1)

Reason = Literal["ok", "bad_credentials", "paused", "blocked", "first_password_expired", "session_limit", "choice_expired"]


class DeviceInfo(NamedTuple):
    """A device as its owner sees it: the public id, their name for it, the browser label."""

    device_id: str
    name: str | None
    label: str | None


class DeviceSession(NamedTuple):
    """One live session as its owner sees it in the session-limit choice."""

    device_id: str
    name: str | None
    label: str | None
    created_at: datetime
    last_seen_at: datetime


class LoginResult(NamedTuple):
    ok: bool
    token: str | None
    user: User | None
    reason: Reason
    retry_after_seconds: int | None
    must_change_password: bool = False
    # set only when reason == "session_limit": the one-use token for replace_session, and the
    # sessions the person may end
    choice_token: str | None = None
    devices: tuple[DeviceSession, ...] = ()
    # set only when ok: the device signed in, and the raw device key to (re)send as its cookie
    device: DeviceInfo | None = None
    device_key: str | None = None


_BAD = LoginResult(False, None, None, "bad_credentials", None)


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(UTC)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def _count_failure(db: Session, user: User, now: datetime) -> None:
    """One wrong password: count it, pause at the Nth, block at the Mth (one pause; the block
    still comes later)."""
    cfg = get_settings()
    user.failed_count += 1
    if user.failed_count >= cfg.login_block_after:
        user.blocked = True
    elif user.failed_count == cfg.login_pause_after:
        user.paused_until = now + timedelta(minutes=cfg.login_pause_minutes)
    db.flush()


def _usable(now: datetime) -> ColumnElement[bool]:
    """Sessions still within both the idle and the hard limit."""
    cfg = get_settings()
    return (AuthSession.created_at >= now - timedelta(hours=cfg.session_max_hours)) & (AuthSession.last_seen_at >= now - timedelta(hours=cfg.session_idle_hours))


def _known_device(db: Session, user_id: str, device_key: str | None) -> UserDevice | None:
    """The user's device behind the browser's device cookie. Scoped to the user: a key another
    user's sign-in left in a shared browser is simply not theirs."""
    if device_key is None or not valid_device_key(device_key):
        return None
    return db.scalar(select(UserDevice).where(UserDevice.user_id == user_id, UserDevice.key_hash == _hash_token(device_key)))


def _live_elsewhere(db: Session, user_id: str, now: datetime, device: UserDevice | None) -> list[tuple[AuthSession, UserDevice]]:
    """The user's live sessions, newest first, leaving out the signing-in device's own (signing
    in again from the same browser reuses its slot)."""
    query = select(AuthSession, UserDevice).join(UserDevice, AuthSession.device_pk == UserDevice.id).where(AuthSession.user_id == user_id, _usable(now)).order_by(AuthSession.last_seen_at.desc())
    if device is not None:
        query = query.where(UserDevice.id != device.id)
    return [(row[0], row[1]) for row in db.execute(query)]


def _open_session(db: Session, user: User, now: datetime, device: UserDevice | None, label: str | None, device_key: str | None) -> LoginResult:
    if device is None:  # a browser not seen before: remember it under a fresh key
        taken = set(db.scalars(select(UserDevice.device_id).where(UserDevice.user_id == user.id)))
        public = new_device_id()
        while public in taken:  # 8 hex digits against a handful of devices: almost never loops
            public = new_device_id()
        device_key = secrets.token_urlsafe(32)
        device = UserDevice(user_id=user.id, device_id=public, key_hash=_hash_token(device_key), label=label, created_at=now, last_seen_at=now)
        db.add(device)
        db.flush()
    else:  # the same browser again: its old session ends, so it never holds two slots
        db.execute(delete(AuthSession).where(AuthSession.device_pk == device.id))
        device.label = label or device.label
        device.last_seen_at = now
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(token_hash=_hash_token(token), user_id=user.id, device_pk=device.id, created_at=now, last_seen_at=now))
    db.flush()
    info = DeviceInfo(device.device_id, device.name, device.label)
    return LoginResult(True, token, user, "ok", None, user.must_change_password, device=info, device_key=device_key)


def _hold(db: Session, user: User, now: datetime, live: list[tuple[AuthSession, UserDevice]]) -> LoginResult:
    """At the limit: open no session; hand back a one-use choice token and the live sessions."""
    db.execute(delete(SignInChoice).where(SignInChoice.user_id == user.id, SignInChoice.expires_at < now))
    token = secrets.token_urlsafe(32)
    expires = now + timedelta(minutes=get_settings().session_choice_minutes)
    db.add(SignInChoice(token_hash=_hash_token(token), user_id=user.id, expires_at=expires))
    db.flush()
    devices = tuple(DeviceSession(d.device_id, d.name, d.label, s.created_at, s.last_seen_at) for s, d in live)
    return LoginResult(False, None, user, "session_limit", None, user.must_change_password, token, devices)


def _sign_in(db: Session, user: User, now: datetime, label: str | None, device_key: str | None) -> LoginResult:
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id, ~_usable(now)))
    device = _known_device(db, user.id, device_key)
    live = _live_elsewhere(db, user.id, now, device)
    if len(live) >= get_settings().session_max_per_user:
        return _hold(db, user, now, live)
    return _open_session(db, user, now, device, label, device_key)


def login(
    db: Session,
    email: str,
    password: str,
    now: datetime | None = None,
    device_label: str | None = None,
    device_key: str | None = None,
) -> LoginResult:
    """Check the password and open a session on this device (`device_key` is the browser's
    device cookie, if any). At `session_max_per_user` live sessions on OTHER devices no session
    opens: the result is "session_limit" with a choice token for `replace_session`."""
    now = _now(now)
    try:
        key = normalize_email(email)
    except ValueError:
        verify_password(password, None)  # same cost as any other failure
        return _BAD
    user = db.scalar(select(User).where(User.email == key).with_for_update())
    if user is None or not user.is_active or user.auth_kind != "password" or not user.password_hash:
        verify_password(password, None)
        return _BAD
    if user.blocked:
        verify_password(password, None)
        return LoginResult(False, None, None, "blocked", None)
    if user.paused_until is not None and user.paused_until > now:
        verify_password(password, None)
        wait = math.ceil((user.paused_until - now).total_seconds())
        return LoginResult(False, None, None, "paused", wait)
    if not verify_password(password, user.password_hash):
        _count_failure(db, user, now)
        return _BAD
    user.failed_count = 0
    user.paused_until = None
    if user.must_change_password and user.first_password_expires_at is not None and user.first_password_expires_at < now:
        db.flush()
        return LoginResult(False, None, None, "first_password_expired", None)
    return _sign_in(db, user, now, device_label, device_key)


_CHOICE_GONE = LoginResult(False, None, None, "choice_expired", None)


def replace_session(
    db: Session,
    choice_token: str,
    device_id: str,
    now: datetime | None = None,
    device_label: str | None = None,
    device_key: str | None = None,
) -> LoginResult:
    """Finish a held sign-in: end the chosen device's session (same user only), then open the
    new one. The choice token is spent whatever happens. A device that already went is no
    error: if the user is still at the limit, a fresh choice comes back instead."""
    now = _now(now)
    choice = db.get(SignInChoice, _hash_token(choice_token), with_for_update=True)
    if choice is None:
        return _CHOICE_GONE
    user_id, expired = choice.user_id, choice.expires_at < now
    db.delete(choice)
    db.flush()
    if expired:
        return _CHOICE_GONE
    # lock the user row as login() does, so two finishes cannot both slip under the limit
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None or not user.is_active or user.blocked or user.auth_kind != "password":
        return _CHOICE_GONE
    if user.must_change_password and user.first_password_expires_at is not None and user.first_password_expires_at < now:
        return LoginResult(False, None, None, "first_password_expired", None)
    # the owner check is in the WHERE: a device id of another user ends nothing
    target = db.scalar(select(UserDevice.id).where(UserDevice.user_id == user.id, UserDevice.device_id == device_id))
    if target is not None:
        db.execute(delete(AuthSession).where(AuthSession.device_pk == target))
    return _sign_in(db, user, now, device_label, device_key)


def name_device(db: Session, session_token: str, name: str | None) -> DeviceInfo | None:
    """Give the device behind this session the user's own name (None clears it)."""
    session = db.get(AuthSession, _hash_token(session_token))
    if session is None:
        return None
    device = db.get(UserDevice, session.device_pk)
    if device is None:
        return None
    device.name = name
    db.flush()
    return DeviceInfo(device.device_id, device.name, device.label)


def user_for_token(db: Session, token: str, now: datetime | None = None) -> User | None:
    now = _now(now)
    session = db.get(AuthSession, _hash_token(token))
    if session is None:
        return None
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        return None
    cfg = get_settings()
    if now - session.last_seen_at > timedelta(hours=cfg.session_idle_hours):
        return None
    if now - session.created_at > timedelta(hours=cfg.session_max_hours):
        return None
    if now - session.last_seen_at >= LAST_SEEN_WRITE_EVERY:
        session.last_seen_at = now
        db.flush()
    return user


def logout(db: Session, token: str) -> None:
    db.execute(delete(AuthSession).where(AuthSession.token_hash == _hash_token(token)))
    db.flush()


def revoke_user_sessions(db: Session, user_id: str) -> int:
    """End every session of the user, and any held sign-in waiting to replace one."""
    db.execute(delete(SignInChoice).where(SignInChoice.user_id == user_id))
    result = db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
    db.flush()
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


def purge_expired_sessions(db: Session, now: datetime | None = None) -> int:
    """Delete every session past its idle or hard limit (they can no longer be used), and every
    expired held sign-in, and every device unused for `device_cookie_days`. Sign-in only clears the signing-in user's own; this sweeps the rest (a
    daily job). Returns the sessions deleted."""
    now = _now(now)
    db.execute(delete(SignInChoice).where(SignInChoice.expires_at < now))
    result = db.execute(delete(AuthSession).where(~_usable(now)))
    forgotten = now - timedelta(days=get_settings().device_cookie_days)
    db.execute(delete(UserDevice).where(UserDevice.last_seen_at < forgotten))  # its cookie is gone too
    db.flush()
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


def last_seen(db: Session) -> dict[str, datetime]:
    """Each user's most recent activity in any live or stale session, by user id."""
    rows = db.execute(select(AuthSession.user_id, func.max(AuthSession.last_seen_at)).group_by(AuthSession.user_id))
    return {uid: at for uid, at in rows}


def create_user(
    db: Session,
    email: str,
    name: str,
    role: str,
    password: str | None = None,
    auth_kind: str = "password",
) -> User:
    key = normalize_email(email)
    if role not in ROLES:
        raise ValueError("role must be admin or analyst")
    if auth_kind not in ("password", "microsoft"):
        raise ValueError("unknown auth kind")
    if _by_email(db, key) is not None:
        raise ValueError("a user with this email already exists")
    if password:
        validate_new_password(password)  # PasswordRuleError is a ValueError
    user = User(
        id=uuid.uuid4().hex,
        email=key,
        name=name.strip(),
        role=role,
        auth_kind=auth_kind,
        password_hash=hash_password(password) if password else None,
    )
    db.add(user)
    db.flush()
    return user


def create_user_with_first_password(db: Session, email: str, name: str, role: str) -> tuple[User, str]:
    """A password user with a generated first password (flag set, expiry set). Returns the user
    and the plain password; the caller commits, then emails it with `first_password.send`
    or `first_password.deliver`."""
    from analekh.auth import first_password  # imported here: first_password imports this module

    user = create_user(db, email, name, role)
    return user, first_password.issue(db, user)


def set_password(db: Session, user: User, plain: str) -> None:
    """The person's own choice (or an emailed-code reset): checked against the rules, clears the
    first-password flag, ends every session and revokes every bridge token."""
    validate_new_password(plain)
    user.password_hash = hash_password(plain)
    user.must_change_password = False
    user.first_password_expires_at = None
    user.blocked = False
    user.failed_count = 0
    user.paused_until = None
    revoke_user_sessions(db, user.id)
    revoke_all_api_tokens(db, user.id)
    db.flush()


FirstChange = Literal["ok", "wrong_current", "same_as_first", "expired", "not_pending"]


def change_first_password(db: Session, user: User, current: str, new: str, now: datetime | None = None) -> FirstChange:
    """The forced change. The new password must meet the rules (PasswordRuleError, raised before
    anything is hashed or counted). The current one must be the first password: a wrong one counts
    as a failed sign-in, and the block ends the session. The new one must differ from it."""
    now = _now(now)
    validate_new_password(new)
    user = db.scalar(select(User).where(User.id == user.id).with_for_update()) or user
    if not user.must_change_password:
        return "not_pending"
    if not verify_password(current, user.password_hash):
        _count_failure(db, user, now)
        if user.blocked:
            revoke_user_sessions(db, user.id)
        return "wrong_current"
    user.failed_count = 0
    if user.first_password_expires_at is not None and user.first_password_expires_at < now:
        return "expired"
    if new == current:
        return "same_as_first"
    set_password(db, user, new)  # clears the flag and expiry, ends every session
    return "ok"
