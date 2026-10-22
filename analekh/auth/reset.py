"""Emailed one-time reset code (auth design, section 5).

A 6-digit code, stored only as SHA-256, valid for `reset_code_minutes`, single use, replaced by a
newer request, burned after `reset_max_attempts` wrong tries. Nothing here commits: the route
does, including after a failed attempt so the count persists.
"""

import hashlib
import hmac
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from analekh.alerts.mail import send_mail
from analekh.auth import service
from analekh.auth.passwords import check_password_length, normalize_email
from analekh.config import get_settings
from analekh.db.models import PasswordReset, User

CODE_DIGITS = 6


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _user(db: Session, email: str) -> User | None:
    try:
        key = normalize_email(email)
    except ValueError:
        return None
    return db.scalar(select(User).where(User.email == key))


def request_reset(
    db: Session,
    email: str,
    now: datetime | None = None,
    schedule: Callable[[str, str, str], object] | None = None,
) -> bool:
    """Issue a new code and mail it. True when mail was sent or queued. Unknown, disabled and
    Microsoft accounts get nothing (the caller answers the same way either way). `schedule`, when
    given, queues the mail to run after the reply goes out, so a known account is not slower than
    an unknown one."""
    user = _user(db, email)
    if user is None or not user.is_active or user.auth_kind != "password":
        return False
    s = get_settings()
    now = service._now(now)
    row = db.get(PasswordReset, user.id)
    if row is not None:
        # Inside the cooldown: keep the code already sent and send nothing. The caller replies the
        # same way, so the wait cannot reveal that the account exists.
        issued = row.expires_at - timedelta(minutes=s.reset_code_minutes)
        if now - issued < timedelta(seconds=s.reset_request_cooldown_seconds):
            return False
    code = f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"
    expires = now + timedelta(minutes=s.reset_code_minutes)
    if row is None:
        db.add(PasswordReset(user_id=user.id, code_hash=_hash_code(code), expires_at=expires))
    else:
        row.code_hash, row.expires_at, row.attempts = _hash_code(code), expires, 0
    db.flush()
    body = (
        f"Your Analekh password reset code is {code}.\n\n"
        f"It works once and expires in {s.reset_code_minutes} minutes. "
        "If you did not ask for it, ignore this message."
    )
    if schedule is not None:
        schedule(user.email, "Your Analekh reset code", body)
        return True
    return send_mail(user.email, "Your Analekh reset code", body)


def confirm_reset(
    db: Session, email: str, code: str, new_password: str, now: datetime | None = None
) -> bool:
    """Check the code and set the new password (which ends every session and clears any block).
    A wrong code counts an attempt; an expired or exhausted code is deleted. A new password of the
    wrong length raises PasswordTooShort / PasswordTooLong before the code is looked at, so it
    spends no attempt."""
    check_password_length(new_password)
    user = _user(db, email)
    row = db.get(PasswordReset, user.id) if user is not None else None
    if user is None or row is None:
        return False
    limit = get_settings().reset_max_attempts
    if service._now(now) > row.expires_at or row.attempts >= limit:
        db.delete(row)
        db.flush()
        return False
    if not hmac.compare_digest(row.code_hash, _hash_code(code.strip())):
        row.attempts += 1
        if row.attempts >= limit:
            db.delete(row)
        db.flush()
        return False
    db.delete(row)
    service.set_password(db, user, new_password)
    return True
