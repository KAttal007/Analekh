"""Sign-in, sign-out and who-am-I (auth design, sections 5 and 6).

Credentials travel only in the JSON body of POST /auth/login. Nothing here logs a request body
or a Cookie / Authorization header.
"""

from fastapi import APIRouter, BackgroundTasks, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from analekh.api.deps import DB, SESSION_COOKIE, CurrentUser
from analekh.auth import ip_limit, reset, service
from analekh.auth import tokens as api_tokens
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


def _cookie_secure() -> bool:
    return get_settings().env != "dev"


@router.post("/login", response_model=MeOut)
def login(body: LoginIn, request: Request, db: DB, response: Response) -> object:
    """Sign in. The session is committed after a FAILED attempt too, so the failure counters
    persist; no 401, 429 or 403 path rolls back."""
    ip = request.client.host if request.client else "unknown"
    wait_ip = ip_limit.retry_after(ip)
    if wait_ip is not None:  # refused before any password hashing or database work
        return JSONResponse(
            {"detail": f"Too many attempts. Try again in {max(1, -(-wait_ip // 60))} minute(s)."},
            status_code=429,
            headers={**NO_STORE, "Retry-After": str(wait_ip)},
        )
    result = service.login(db, body.email, body.password)
    db.commit()
    # Unknown emails, wrong passwords and paused or blocked accounts all get the same counted
    # reply: only real accounts can be paused or blocked, so a distinct reply would reveal which
    # emails have an account (rule 9). A blocked holder recovers with the reset code.
    if result.reason in ("bad_credentials", "paused", "blocked"):
        ip_limit.record_failure(ip)
        return JSONResponse({"detail": BAD_CREDENTIALS}, status_code=401, headers=NO_STORE)
    if result.reason == "first_password_expired":  # only the holder of the right password sees it
        return JSONResponse({"detail": FIRST_EXPIRED}, status_code=401, headers=NO_STORE)
    if result.reason != "ok" or result.user is None or result.token is None:
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
    u = result.user
    return MeOut(
        id=u.id,
        name=u.name,
        email=u.email,
        role=service.role_of(u),
        must_change_password=bool(result.must_change_password),
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
