"""User administration (admin only; plan task 6). Passwords and hashes never appear in a reply."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from analekh.api.deps import DB, AdminUser
from analekh.auth import service
from analekh.auth.passwords import MAX_EMAIL, MAX_PASSWORD, PasswordTooLong, PasswordTooShort
from analekh.auth.service import Role
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
    # Sign-ins are refused until then (after repeated wrong passwords); null when not paused.
    paused_until: datetime | None = None
    # Latest activity in any session (to the minute); null when never signed in or purged.
    last_seen_at: datetime | None = None


class UserIn(BaseModel):
    email: str = Field(max_length=MAX_EMAIL)
    name: str = Field(min_length=1, max_length=MAX_NAME)
    role: Role
    password: str | None = Field(default=None, max_length=MAX_PASSWORD)


class UserPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=MAX_NAME)
    role: Role | None = None
    is_active: bool | None = None


class PasswordIn(BaseModel):
    new_password: str = Field(max_length=MAX_PASSWORD)


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
    )


def _get(db: DB, user_id: str) -> User:
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "User not found.")
    return u


def _audit(db: DB, actor: User, action: str, **detail: object) -> None:
    db.add(AuditEntry(user_id=actor.id, action=action, detail=detail))


def _active_admins(db: DB) -> int:
    return int(
        db.scalar(
            select(func.count()).select_from(User).where(User.role == "admin", User.is_active)
        )
        or 0
    )


@router.get("", response_model=list[UserOut])
def list_users(db: DB, _: AdminUser) -> list[UserOut]:
    seen = service.last_seen(db)
    return [_out(u, seen) for u in db.scalars(select(User).order_by(User.name, User.email))]


@router.post("", response_model=UserOut, status_code=201)
def create(body: UserIn, db: DB, actor: AdminUser) -> UserOut:
    try:
        u = service.create_user(db, body.email, body.name, body.role, body.password)
    except (PasswordTooShort, PasswordTooLong) as exc:
        raise HTTPException(422, str(exc)) from exc
    except ValueError as exc:
        msg = str(exc)
        raise HTTPException(409 if "already exists" in msg else 422, msg) from exc
    _audit(db, actor, "user.create", target=u.id, role=u.role)
    db.commit()
    return _out(u)


@router.patch("/{user_id}", response_model=UserOut)
def update(user_id: str, body: UserPatch, db: DB, actor: AdminUser) -> UserOut:
    u = _get(db, user_id)
    loses_admin = (
        u.role == "admin" and u.is_active and (body.role == "analyst" or body.is_active is False)
    )
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


@router.post("/{user_id}/reset-password", status_code=204)
def reset_password(user_id: str, body: PasswordIn, db: DB, actor: AdminUser) -> Response:
    u = _get(db, user_id)
    try:
        service.set_password(db, u, body.new_password)
    except (PasswordTooShort, PasswordTooLong) as exc:
        raise HTTPException(422, str(exc)) from exc
    _audit(db, actor, "user.password_reset", target=u.id)
    db.commit()
    return Response(status_code=204)


@router.post("/{user_id}/unblock", status_code=204)
def unblock(user_id: str, db: DB, actor: AdminUser) -> Response:
    u = _get(db, user_id)
    u.blocked = False
    u.failed_count = 0
    u.paused_until = None
    _audit(db, actor, "user.unblock", target=u.id)
    db.commit()
    return Response(status_code=204)
