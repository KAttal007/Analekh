"""Sign-in service: sessions, failure tiers, disable (auth design, section 5).

Everything goes through SQLAlchemy bound parameters. Tokens are random and only their SHA-256 is
stored. Functions flush but never commit: the caller commits, and must commit after a failed
sign-in too, so the failure counters persist. `now` is a parameter so tests control time.
"""

import hashlib
import math
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal, NamedTuple, cast

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from analekh.auth.passwords import hash_password, normalize_email, verify_password
from analekh.config import get_settings
from analekh.db.models import AuthSession, User

Role = Literal["admin", "analyst"]
ROLES: tuple[Role, ...] = ("admin", "analyst")


def role_of(user: User) -> Role:
    """The user's role, typed. The column's CHECK constraint allows only these two values."""
    return cast(Role, user.role)


LAST_SEEN_WRITE_EVERY = timedelta(minutes=1)

Reason = Literal["ok", "bad_credentials", "paused", "blocked"]


class LoginResult(NamedTuple):
    ok: bool
    token: str | None
    user: User | None
    reason: Reason
    retry_after_seconds: int | None


_BAD = LoginResult(False, None, None, "bad_credentials", None)


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(UTC)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def login(db: Session, email: str, password: str, now: datetime | None = None) -> LoginResult:
    now = _now(now)
    cfg = get_settings()
    try:
        key = normalize_email(email)
    except ValueError:
        verify_password(password, None)  # same cost as any other failure
        return _BAD
    # Lock the row for this attempt: parallel guesses queue here instead of all reading the same
    # failure count, so a flood cannot skip the pause or the block.
    user = db.scalar(select(User).where(User.email == key).with_for_update())
    # Unknown, disabled and Microsoft accounts: same work, same reply as a wrong password, so the
    # reply never tells anyone whether an address has an account (owner, 2026-10-22).
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
        user.failed_count += 1
        if user.failed_count >= cfg.login_block_after:
            user.blocked = True
        elif user.failed_count == cfg.login_pause_after:  # one pause; the block still comes later
            user.paused_until = now + timedelta(minutes=cfg.login_pause_minutes)
        db.flush()
        return _BAD
    user.failed_count = 0
    user.paused_until = None
    # Housekeeping: drop this user's sessions that can no longer be used.
    db.execute(
        delete(AuthSession).where(
            AuthSession.user_id == user.id,
            (AuthSession.created_at < now - timedelta(hours=cfg.session_max_hours))
            | (AuthSession.last_seen_at < now - timedelta(hours=cfg.session_idle_hours)),
        )
    )
    token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            token_hash=_hash_token(token), user_id=user.id, created_at=now, last_seen_at=now
        )
    )
    db.flush()
    return LoginResult(True, token, user, "ok", None)


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
    # Write at most once a minute, so every click does not cost a database write.
    if now - session.last_seen_at >= LAST_SEEN_WRITE_EVERY:
        session.last_seen_at = now
        db.flush()
    return user


def logout(db: Session, token: str) -> None:
    db.execute(delete(AuthSession).where(AuthSession.token_hash == _hash_token(token)))
    db.flush()


def revoke_user_sessions(db: Session, user_id: str) -> int:
    result = db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
    db.flush()
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


def purge_expired_sessions(db: Session, now: datetime | None = None) -> int:
    """Delete every session past its idle or hard limit (they can no longer be used). Sign-in
    only clears the signing-in user's own; this sweeps the rest (a daily job)."""
    now = _now(now)
    cfg = get_settings()
    result = db.execute(
        delete(AuthSession).where(
            (AuthSession.created_at < now - timedelta(hours=cfg.session_max_hours))
            | (AuthSession.last_seen_at < now - timedelta(hours=cfg.session_idle_hours))
        )
    )
    db.flush()
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


def last_seen(db: Session) -> dict[str, datetime]:
    """Each user's most recent activity in any live or stale session, by user id."""
    rows = db.execute(
        select(AuthSession.user_id, func.max(AuthSession.last_seen_at)).group_by(
            AuthSession.user_id
        )
    )
    return {uid: at for uid, at in rows}


def create_user(
    db: Session,
    email: str,
    name: str,
    role: str,
    password: str | None,
    auth_kind: str = "password",
) -> User:
    key = normalize_email(email)
    if role not in ROLES:
        raise ValueError("role must be admin or analyst")
    if auth_kind not in ("password", "microsoft"):
        raise ValueError("unknown auth kind")
    if _by_email(db, key) is not None:
        raise ValueError("a user with this email already exists")
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


def set_password(db: Session, user: User, plain: str) -> None:
    user.password_hash = hash_password(plain)
    user.blocked = False
    user.failed_count = 0
    user.paused_until = None
    revoke_user_sessions(db, user.id)
    db.flush()
