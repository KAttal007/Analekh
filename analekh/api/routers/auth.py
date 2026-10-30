"""Sign-in, sign-out and who-am-I (auth design, sections 5 and 6).

Credentials travel only in the JSON body of POST /auth/login. Nothing here logs a request body
or a Cookie / Authorization header.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from analekh.api.deps import DB, SESSION_COOKIE, CurrentUser
from analekh.auth import ip_limit, reset, service
from analekh.auth import tokens as api_tokens
from analekh.auth.devices import DEVICE_COOKIE, DeviceNameError, clean_device_name, device_label
from analekh.auth.passwords import (
    MAX_EMAIL,
    PasswordRuleError,
    check_password_rules,
    combined_pattern,
    password_rules,
    validate_new_password,
)
from analekh.config import get_settings
from analekh.db.models import AuditEntry

router = APIRouter(prefix="/auth", tags=["auth"])

NO_STORE = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}
BAD_CREDENTIALS = "Email or password is incorrect."
FIRST_EXPIRED = "This first password has expired. Ask an admin to send a new one."
CHOICE_EXPIRED = "This sign-in has timed out. Sign in again."
FIELD_CAP = 128


class LoginIn(BaseModel):
    email: str = Field(max_length=MAX_EMAIL)
    password: str = Field(max_length=get_settings().password_max_length)


class MeOut(BaseModel):
    id: str
    name: str
    email: str
    role: service.Role
    must_change_password: bool = False


class ThisDeviceOut(BaseModel):
    device_id: str
    name: str | None  # the user's own name; None until they give one
    label: str | None  # "Chrome on Windows"; None: the browser did not say what it is


class LoginOut(MeOut):
    device: ThisDeviceOut


class DeviceOut(BaseModel):
    device_id: str
    name: str | None
    label: str | None
    signed_in_at: datetime
    last_seen_at: datetime


class SessionLimitOut(BaseModel):
    """409 from sign-in at the session limit. `choice_token` is spent by POST /auth/login/replace;
    it opens nothing by itself and expires in `session_choice_minutes`."""

    detail: str
    limit: int
    choice_token: str
    devices: list[DeviceOut]


class DeviceNameIn(BaseModel):
    name: str = Field(max_length=FIELD_CAP)  # checked again, tighter, by clean_device_name


class ReplaceIn(BaseModel):
    choice_token: str = Field(min_length=1, max_length=FIELD_CAP)
    device_id: str = Field(min_length=1, max_length=16, pattern=r"^[0-9a-f]+$")


def _cookie_secure() -> bool:
    return get_settings().env != "dev"


def _too_many(ip: str) -> JSONResponse | None:
    wait_ip = ip_limit.retry_after(ip)
    if wait_ip is None:
        return None
    return JSONResponse(
        {"detail": f"Too many attempts. Try again in {max(1, -(-wait_ip // 60))} minute(s)."},
        status_code=429,
        headers={**NO_STORE, "Retry-After": str(wait_ip)},
    )


def _at_limit(result: service.LoginResult) -> JSONResponse:
    limit = get_settings().session_max_per_user
    out = SessionLimitOut(
        detail=f"You are signed in on {limit} devices, the most allowed. Sign out of one to sign in here.",
        limit=limit,
        choice_token=result.choice_token or "",
        devices=[DeviceOut(device_id=d.device_id, name=d.name, label=d.label, signed_in_at=d.created_at, last_seen_at=d.last_seen_at) for d in result.devices],
    )
    return JSONResponse(out.model_dump(mode="json"), status_code=409, headers=NO_STORE)


_LIMIT_REPLY: dict[int | str, dict[str, Any]] = {409: {"model": SessionLimitOut, "description": "At the session limit: pick a device to sign out of."}}


@router.post("/login", response_model=LoginOut, responses=_LIMIT_REPLY)
def login(body: LoginIn, request: Request, db: DB, response: Response) -> object:
    """Sign in. The session is committed after a FAILED attempt too, so the failure counters
    persist; no 401, 429 or 403 path rolls back. At the session limit the reply is 409 with the
    live devices and a choice token, and no session opens."""
    ip = request.client.host if request.client else "unknown"
    refused = _too_many(ip)  # refused before any password hashing or database work
    if refused is not None:
        return refused
    result = service.login(db, body.email, body.password, device_label=_label(request), device_key=request.cookies.get(DEVICE_COOKIE))
    db.commit()
    # Unknown emails, wrong passwords and paused or blocked accounts all get the same counted
    # reply: only real accounts can be paused or blocked, so a distinct reply would reveal which
    # emails have an account (rule 9). A blocked holder recovers with the reset code.
    if result.reason in ("bad_credentials", "paused", "blocked"):
        ip_limit.record_failure(ip)
        return JSONResponse({"detail": BAD_CREDENTIALS}, status_code=401, headers=NO_STORE)
    return _finish(result, response)


@router.post("/login/replace", response_model=LoginOut, responses=_LIMIT_REPLY)
def login_replace(body: ReplaceIn, request: Request, db: DB, response: Response) -> object:
    """Second step of a sign-in held at the session limit: sign out of the chosen device and sign
    in here. Needs no session (the choice token, from a correct password, stands in for one)."""
    ip = request.client.host if request.client else "unknown"
    refused = _too_many(ip)
    if refused is not None:
        return refused
    result = service.replace_session(db, body.choice_token, body.device_id, device_label=_label(request), device_key=request.cookies.get(DEVICE_COOKIE))
    if result.ok and result.user is not None:
        db.add(AuditEntry(user_id=result.user.id, action="user.session_replaced", detail={"device_id": body.device_id}))
    db.commit()
    if result.reason == "choice_expired":
        ip_limit.record_failure(ip)  # a guessed or replayed token counts like a wrong password
        return JSONResponse({"detail": CHOICE_EXPIRED}, status_code=401, headers=NO_STORE)
    return _finish(result, response)


def _label(request: Request) -> str | None:
    """The signing-in browser's label (fixed vocabulary; the raw User-Agent goes no further)."""
    return device_label(request.headers.get("User-Agent"))


def _finish(result: service.LoginResult, response: Response) -> object:
    """The reply once the password is known to be right: limit, expiry or a signed-in cookie."""
    if result.reason == "session_limit":  # only the holder of the right password sees it
        return _at_limit(result)
    if result.reason == "first_password_expired":  # likewise
        return JSONResponse({"detail": FIRST_EXPIRED}, status_code=401, headers=NO_STORE)
    if result.reason != "ok" or result.user is None or result.token is None or result.device is None:
        return JSONResponse({"detail": BAD_CREDENTIALS}, status_code=401, headers=NO_STORE)
    cfg = get_settings()
    for name, value in NO_STORE.items():
        response.headers[name] = value
    response.set_cookie(
        SESSION_COOKIE,
        result.token,
        max_age=min(cfg.session_idle_hours, cfg.session_max_hours) * 3600,
        httponly=True,
        secure=_cookie_secure(),
        samesite="strict",
        path="/",
    )
    if result.device_key:  # (re)sent on every sign-in, so a device in use is never forgotten
        response.set_cookie(
            DEVICE_COOKIE,
            result.device_key,
            max_age=cfg.device_cookie_days * 86400,
            httponly=True,
            secure=_cookie_secure(),
            samesite="strict",
            path="/",
        )
    u, d = result.user, result.device
    return LoginOut(
        id=u.id,
        name=u.name,
        email=u.email,
        role=service.role_of(u),
        must_change_password=bool(result.must_change_password),
        device=ThisDeviceOut(device_id=d.device_id, name=d.name, label=d.label),
    )


def _signed_out() -> Response:
    out = Response(status_code=204, headers=NO_STORE)
    out.delete_cookie(SESSION_COOKIE, path="/", httponly=True, secure=_cookie_secure(), samesite="strict")
    return out


@router.post("/logout", status_code=204)
def logout(request: Request, db: DB, _: CurrentUser) -> Response:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        service.logout(db, token)
        db.commit()
    return _signed_out()


@router.post("/logout-everywhere", status_code=204)
def logout_everywhere(db: DB, current: CurrentUser) -> Response:
    """End every session of this user, in every browser, and revoke their Excel bridge and
    add-in tokens (a lost laptop, a shared machine)."""
    service.revoke_user_sessions(db, current.id)
    api_tokens.revoke_all_api_tokens(db, current.id)
    db.add(AuditEntry(user_id=current.id, action="user.logout_everywhere", detail={}))
    db.commit()
    return _signed_out()


@router.post("/device-name", response_model=ThisDeviceOut)
def device_name(body: DeviceNameIn, request: Request, db: DB, _: CurrentUser) -> object:
    """Name the device this browser is signed in on ("Office laptop"); an empty name clears it.
    Only the session cookie says which device: a bearer token has none to name."""
    token = request.cookies.get(SESSION_COOKIE)
    try:
        name = clean_device_name(body.name)
    except DeviceNameError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=400, headers=NO_STORE)
    info = service.name_device(db, token, name) if token else None
    if info is None:
        return JSONResponse({"detail": "Only a browser sign-in has a device to name."}, status_code=400, headers=NO_STORE)
    db.commit()
    return ThisDeviceOut(device_id=info.device_id, name=info.name, label=info.label)


@router.get("/me", response_model=MeOut)
def me(current: CurrentUser) -> MeOut:
    return MeOut(
        id=current.id,
        name=current.name,
        email=current.email,
        role=service.role_of(current),
        must_change_password=bool(current.must_change_password),
    )


@router.get("/password-rules")
def password_rules_route() -> JSONResponse:
    """The rules the web app shows and checks as the person types. Public; holds no secrets."""
    cfg = get_settings()
    return JSONResponse(
        {
            "rules": password_rules(),
            "combined": combined_pattern(),
            "max_length": cfg.password_max_length,
            "min_length": cfg.password_min_length,
        },
        headers=NO_STORE,
    )


class FirstPasswordIn(BaseModel):
    current_password: str = Field(max_length=FIELD_CAP)
    new_password: str = Field(max_length=FIELD_CAP)


@router.post("/first-password", status_code=204)
def first_password(body: FirstPasswordIn, db: DB, current: CurrentUser) -> Response:
    """Choose your own password in place of the emailed one. Committed after a wrong first
    password too, so the failure count persists."""
    if not current.must_change_password:
        return JSONResponse({"detail": "No password change is pending."}, status_code=400, headers=NO_STORE)
    try:  # the rules come first: nothing is hashed, verified or counted for a weak password
        validate_new_password(body.new_password)
    except PasswordRuleError as exc:
        return JSONResponse(
            {"detail": str(exc), "missing": check_password_rules(body.new_password)},
            status_code=400,
            headers=NO_STORE,
        )
    outcome = service.change_first_password(db, current, body.current_password, body.new_password)
    if outcome == "ok":
        db.add(AuditEntry(user_id=current.id, action="user.first_password_change", detail={}))
    db.commit()
    if outcome == "wrong_current":
        return JSONResponse({"detail": BAD_CREDENTIALS}, status_code=401, headers=NO_STORE)
    if outcome == "expired":
        return JSONResponse({"detail": FIRST_EXPIRED}, status_code=401, headers=NO_STORE)
    if outcome == "same_as_first":
        return JSONResponse(
            {"detail": "Choose a password different from the first one."},
            status_code=400,
            headers=NO_STORE,
        )
    if outcome == "not_pending":
        return JSONResponse({"detail": "No password change is pending."}, status_code=400, headers=NO_STORE)
    return _signed_out()


class ResetRequestIn(BaseModel):
    email: str = Field(max_length=MAX_EMAIL)


class ResetConfirmIn(BaseModel):
    email: str = Field(max_length=MAX_EMAIL)
    code: str = Field(max_length=32)
    new_password: str = Field(max_length=FIELD_CAP)


@router.post("/reset/request", status_code=202)
def reset_request(body: ResetRequestIn, db: DB, background: BackgroundTasks) -> JSONResponse:
    """Mail a one-time code. The reply is the same whether or not the account exists, and the
    mail is sent after the reply, so the timing does not reveal the account either."""
    if not get_settings().smtp_url:
        return JSONResponse(
            {"detail": "Email is not set up. Contact the admin team."},
            status_code=503,
            headers=NO_STORE,
        )

    def queue(to: str, subject: str, text: str) -> None:
        background.add_task(reset.send_mail, to, subject, text)

    reset.request_reset(db, body.email, schedule=queue)
    db.commit()
    return JSONResponse(
        {"detail": "If that account exists, a code has been sent."},
        status_code=202,
        headers=NO_STORE,
    )


@router.post("/reset/confirm", status_code=204)
def reset_confirm(body: ResetConfirmIn, db: DB) -> Response:
    """Set a new password with the emailed code. Committed after a FAILED attempt too, so the
    attempt count persists."""
    try:
        ok = reset.confirm_reset(db, body.email, body.code, body.new_password)
    except PasswordRuleError as exc:  # checked first: no attempt spent
        return JSONResponse(
            {"detail": str(exc), "missing": check_password_rules(body.new_password)},
            status_code=400,
            headers=NO_STORE,
        )
    db.commit()
    if not ok:
        return JSONResponse({"detail": "That code is not valid."}, status_code=400, headers=NO_STORE)
    return Response(status_code=204, headers=NO_STORE)
