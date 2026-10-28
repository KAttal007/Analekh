"""Shared API dependencies. Tests override get_session and get_store."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from functools import lru_cache
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from analekh.api import schemas
from analekh.auth import service as auth_service
from analekh.auth import tokens as api_tokens
from analekh.config import get_settings
from analekh.db.models import Company
from analekh.db.models import User as UserRow
from analekh.db.session import get_session, session_scope
from analekh.ingest.storage import ObjectStore, default_store
from analekh.universe.search import get as get_company


@lru_cache
def get_store() -> ObjectStore:
    """One store per process. A failed connect raises (and isn't cached), so the next request
    tries again once storage is up."""
    return default_store()


SESSION_COOKIE = "analekh_session"
CSRF_HEADER = "X-Analekh-CSRF"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _session_user(request: Request, db: Session) -> UserRow | None:
    """The user behind the session cookie. The token comes only from the cookie, never from a
    URL. A state-changing request made with the cookie must also carry the anti-forgery header
    (SameSite=Strict is the first defence, the header the second)."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    user = auth_service.user_for_token(db, token)
    if user is None:
        return None
    db.commit()  # keep the session's last_seen_at
    if request.method not in _SAFE_METHODS and request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(403, "Missing anti-forgery header.")
    return user


def _bearer_user(request: Request, db: Session) -> UserRow | None:
    """`Authorization: Bearer <token>` (Excel bridge and add-in tokens). The token comes only from
    the header, never from a URL. Bearer requests carry no ambient cookie, so they need no CSRF
    header."""
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return api_tokens.user_for_api_token(db, token.strip())


def auth_is_off() -> bool:
    """True when ENV=dev (unless AUTH_ENABLED=true). ENV=prod always has sign-in on."""
    return not get_settings().sign_in_on


def check_auth_switch() -> None:
    """Refuse to start with sign-in explicitly turned off outside development."""
    s = get_settings()
    if s.auth_enabled is False and s.env != "dev":
        raise RuntimeError("AUTH_ENABLED=false is only allowed when ENV=dev")


def _dev_user(db: Session) -> UserRow:
    """The built-in admin used while sign-in is off. It has the id pre-sign-in data is keyed by
    (default_user_id) and no password, so it can never be signed in to with one."""
    uid = get_settings().default_user_id
    user = db.get(UserRow, uid)
    if user is None:
        s = get_settings()
        user = UserRow(id=uid, email=s.dev_user_email, name=s.dev_user_name, role="admin", auth_kind="password")
        db.add(user)
        db.commit()
    return user


# (first-password design, section 6). Matched on the route's path template, not the URL.
FIRST_PASSWORD_ALLOWED: frozenset[tuple[str, str]] = frozenset(
    {
        ("GET", "/auth/me"),
        ("POST", "/auth/logout"),
        ("GET", "/auth/password-rules"),
        ("POST", "/auth/first-password"),
    }
)


def get_current(request: Request, db: Annotated[Session, Depends(get_session)]) -> UserRow:
    if auth_is_off():  # the flag is ignored with sign-in off (development only)
        return _dev_user(db)
    user = _session_user(request, db) or _bearer_user(request, db)
    if user is None:
        raise HTTPException(401, "Sign in required.")
    if user.must_change_password:
        route = request.scope.get("route")
        key = (request.method, getattr(route, "path", ""))
        if key not in FIRST_PASSWORD_ALLOWED:  # an unmatched route is refused too
            raise HTTPException(403, {"code": "password_change_required"})
    return user


def get_user(current: Annotated[UserRow, Depends(get_current)]) -> str:
    """The signed-in user's id (what the watchlist, models and templates are keyed by)."""
    return current.id


def require_admin(current: Annotated[UserRow, Depends(get_current)]) -> UserRow:
    if current.role != "admin":
        raise HTTPException(403, "Admins only.")
    return current


DB = Annotated[Session, Depends(get_session)]

OpenSession = Callable[[], AbstractContextManager[Session]]


def get_session_scope() -> OpenSession:
    """A way to open a session after the reply, for work done in the background (the request's
    own session is closed by then)."""
    return session_scope


SessionScope = Annotated[OpenSession, Depends(get_session_scope)]
Store = Annotated[ObjectStore, Depends(get_store)]
User = Annotated[str, Depends(get_user)]
CurrentUser = Annotated[UserRow, Depends(get_current)]
AdminUser = Annotated[UserRow, Depends(require_admin)]


def company_or_404(db: Session, symbol: str) -> Company:
    c = get_company(db, symbol)
    if c is None:
        raise HTTPException(
            404,
            f"{symbol.upper()} is not in the NSE universe; run `analekh universe load` if the list has not been loaded",
        )
    return c


def job(task: Any, *args: Any, task_id: str | None = None) -> schemas.JobOut:
    """Queue a background job, or answer 503 at once when the queue isn't running (Celery would
    otherwise retry the broker and leave the request hanging). `task_id` names the job up front,
    e.g. so a model lock can record it before the job can start."""
    from analekh.jobs.health import NOT_RUNNING, queue_available

    if not queue_available(fresh=True):
        raise HTTPException(503, NOT_RUNNING)
    result = task.delay(*args) if task_id is None else task.apply_async(args, task_id=task_id)
    return schemas.JobOut(job_id=result.id, status=result.status)
