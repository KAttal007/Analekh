"""User administration (admin only; plan task 6). Passwords and hashes never appear in a reply."""

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from analekh.api.deps import DB, AdminUser, SessionScope
from analekh.auth import first_password, service
from analekh.auth.passwords import MAX_EMAIL
from analekh.auth.service import Role
from analekh.config import get_settings
from analekh.db.models import AuditEntry, User

router = APIRouter(prefix="/users", tags=["users"])

MAX_NAME = 120


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: Role
    auth_kind: str
    is_active: bool
    blocked: bool
    created_at: datetime | None = None
    paused_until: datetime | None = None
    last_seen_at: datetime | None = None
    must_change_password: bool = False
    first_password_mail: Literal["sending", "sent", "failed"] | None = None


class UserIn(BaseModel):
    email: str = Field(max_length=MAX_EMAIL)
    name: str = Field(min_length=1, max_length=MAX_NAME)
    role: Role


class UserPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=MAX_NAME)
    role: Role | None = None
    is_active: bool | None = None


NO_EMAIL = "Email is not set up. Contact the admin team."


def _out(u: User, seen: dict[str, datetime] | None = None) -> UserOut:
    paused = u.paused_until
    return UserOut(
        id=u.id,
        email=u.email,
        name=u.name,
        role=service.role_of(u),
        auth_kind=u.auth_kind,
        is_active=u.is_active,
        blocked=u.blocked,
        created_at=u.created_at,
        paused_until=paused if paused is not None and paused > datetime.now(UTC) else None,
        last_seen_at=(seen or {}).get(u.id),
        must_change_password=u.must_change_password,
        first_password_mail=u.first_password_mail,  # type: ignore[arg-type]
    )


def _get(db: DB, user_id: str) -> User:
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "User not found.")
    return u


def _audit(db: DB, actor: User, action: str, **detail: object) -> None:
    db.add(AuditEntry(user_id=actor.id, action=action, detail=detail))


def _active_admins(db: DB) -> int:
    return int(db.scalar(select(func.count()).select_from(User).where(User.role == "admin", User.is_active)) or 0)


@router.get("", response_model=list[UserOut])
def list_users(db: DB, _: AdminUser) -> list[UserOut]:
    seen = service.last_seen(db)
    return [_out(u, seen) for u in db.scalars(select(User).order_by(User.name, User.email))]


@router.post("", response_model=UserOut, status_code=201)
def create(body: UserIn, db: DB, actor: AdminUser, background: BackgroundTasks, scope: SessionScope) -> UserOut:
    """Add a user. The server makes the first password and emails it after the reply (the mail
    server takes seconds); `first_password_mail` tells how it went. The reply never carries the
    password. Refused before anything is written when email is not set up."""
    if not get_settings().smtp_url:
        raise HTTPException(503, NO_EMAIL)
    try:
        u, plain = service.create_user_with_first_password(db, body.email, body.name, body.role)
    except ValueError as exc:
        msg = str(exc)
        raise HTTPException(409 if "already exists" in msg else 422, msg) from exc
    _audit(db, actor, "user.create", target=u.id, role=u.role)
    db.commit()  # the account exists whether or not the mail goes
    background.add_task(first_password.deliver, scope, u.id, plain, first=True, actor_id=actor.id)
    return _out(u)


@router.patch("/{user_id}", response_model=UserOut)
def update(user_id: str, body: UserPatch, db: DB, actor: AdminUser) -> UserOut:
    u = _get(db, user_id)
    loses_admin = u.role == "admin" and u.is_active and (body.role == "analyst" or body.is_active is False)
    if loses_admin and _active_admins(db) <= 1:
        raise HTTPException(400, "There must be at least one active admin.")
    if body.name is not None:
        u.name = body.name.strip()
    if body.role is not None and body.role != u.role:
        u.role = body.role
        _audit(db, actor, "user.role", target=u.id, role=body.role)
    if body.is_active is not None and body.is_active != u.is_active:
        u.is_active = body.is_active
        if not body.is_active:
            service.revoke_user_sessions(db, u.id)
        _audit(db, actor, "user.enable" if body.is_active else "user.disable", target=u.id)
    db.commit()
    return _out(u)


@router.post("/{user_id}/send-first-password", response_model=UserOut, status_code=202)
def send_first_password(user_id: str, db: DB, actor: AdminUser, background: BackgroundTasks, scope: SessionScope) -> UserOut:
    """New first password for a user: ends their sessions, clears any pause or block, starts a
    new expiry, and emails it after the reply. Used for "Send again" and for an admin reset."""
    u = _get(db, user_id)
    if u.auth_kind != "password":
        raise HTTPException(400, "This account signs in with Microsoft and has no password.")
    if not get_settings().smtp_url:  # nothing changes if the mail cannot go
        raise HTTPException(503, NO_EMAIL)
    first = u.must_change_password
    plain = first_password.issue(db, u)
    _audit(db, actor, "user.password_reset", target=u.id)
    db.commit()
    background.add_task(first_password.deliver, scope, u.id, plain, first=first, actor_id=actor.id)
    return _out(u)


@router.post("/{user_id}/unblock", status_code=204)
def unblock(user_id: str, db: DB, actor: AdminUser) -> Response:
    u = _get(db, user_id)
    u.blocked = False
    u.failed_count = 0
    u.paused_until = None
    _audit(db, actor, "user.unblock", target=u.id)
    db.commit()
    return Response(status_code=204)
