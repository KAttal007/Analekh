"""The first password: made by the server, emailed once, valid for `first_password_hours`
(first-password design, sections 4 and 6).

The plain text exists only as a return value of `issue` and in the email body. Nothing here logs
it, and `issue` does not commit: the caller commits, then calls `send` (or use `send_now`), or
hands `deliver` to a background task so the reply does not wait for the mail server.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from analekh.alerts import mail
from analekh.auth import service
from analekh.auth.passwords import generate_first_password, hash_password
from analekh.config import get_settings
from analekh.db.models import AuditEntry, User

SUBJECT_FIRST = "Your Analekh account"
SUBJECT_RESET = "Your Analekh password was reset"

# User.first_password_mail
MAIL_SENDING = "sending"
MAIL_SENT = "sent"
MAIL_FAILED = "failed"


def issue(db: Session, user: User, now: datetime | None = None) -> str:
    """Give the user a new first password: replaces the hash, sets the flag and a fresh expiry,
    clears any pause or block, and ends their sessions. Returns the plain password."""
    hours = get_settings().first_password_hours
    plain = generate_first_password()
    user.password_hash = hash_password(plain)
    user.must_change_password = True
    user.first_password_expires_at = service._now(now) + timedelta(hours=hours)
    user.paused_until = None
    user.blocked = False
    user.failed_count = 0
    user.first_password_mail = MAIL_SENDING
    service.revoke_user_sessions(db, user.id)
    db.flush()
    return plain


def _body(user: User, plain: str, *, first: bool) -> str:
    s = get_settings()
    opening = (
        "An Analekh account has been made for you."
        if first
        else "Your Analekh password was reset by an admin."
    )
    lines = [
        opening,
        "",
        f"Username: {user.email}",
        f"First password: {plain}",
        "",
        f"This password works once and lasts {s.first_password_hours} hours. When you sign in "
        "you will be asked to choose your own password.",
    ]
    if s.web_app_url:
        lines += ["", f"Sign in at: {s.web_app_url}"]
    return "\n".join(lines)


def send(user: User, plain: str, *, first: bool) -> bool:
    """Email the first password (plain text, inline). True when the mail was handed on."""
    subject = SUBJECT_FIRST if first else SUBJECT_RESET
    ok = mail.send_mail(user.email, subject, _body(user, plain, first=first))
    user.first_password_mail = MAIL_SENT if ok else MAIL_FAILED
    return ok


def deliver(
    open_session: Callable[[], AbstractContextManager[Session]],
    user_id: str,
    plain: str,
    *,
    first: bool,
    actor_id: str,
) -> None:
    """Background task, run after the reply: send, then record the outcome on the user (the
    Users page shows it) and in the audit log. A newer first password issued meanwhile wins:
    the outcome of this older mail is not recorded on the user."""
    with open_session() as db:
        user = db.get(User, user_id)
        if user is None:
            return
        hash_now = user.password_hash
        db.commit()  # no transaction held open while the mail server is slow
        ok = mail.send_mail(
            user.email, SUBJECT_FIRST if first else SUBJECT_RESET, _body(user, plain, first=first)
        )
        db.refresh(user)
        if user.password_hash == hash_now:
            user.first_password_mail = MAIL_SENT if ok else MAIL_FAILED
        db.add(
            AuditEntry(
                user_id=actor_id,
                action="user.first_password_mail",
                detail={"target": user_id, "sent": ok},
            )
        )
        db.commit()


def send_now(db: Session, user: User, *, first: bool, now: datetime | None = None) -> bool:
    """Issue, commit, then send. If the mail fails the password stays issued, so an admin can
    send again."""
    plain = issue(db, user, now)
    db.commit()
    return send(user, plain, first=first)
