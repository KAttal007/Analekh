"""Sign-in, sign-out and who-am-I (auth design, sections 5 and 6).

Credentials travel only in the JSON body of POST /auth/login. Nothing here logs a request body
or a Cookie / Authorization header.
"""

from fastapi import APIRouter, BackgroundTasks, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from analekh.api.deps import DB, SESSION_COOKIE, CurrentUser
from analekh.auth import ip_limit, reset, service
from analekh.auth.passwords import MAX_EMAIL, MAX_PASSWORD
from analekh.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])

# The sign-in page must not be cached or leak its address in a Referer header.
NO_STORE = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}
BAD_CREDENTIALS = "Email or password is incorrect."
UNKNOWN_EMAIL = "Enter your registered email."


class LoginIn(BaseModel):
    email: str = Field(max_length=MAX_EMAIL)
    password: str = Field(max_length=MAX_PASSWORD)


class MeOut(BaseModel):
    id: str
    name: str
    email: str
    role: str


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
    if result.reason in ("bad_credentials", "unknown_email"):
        ip_limit.record_failure(ip)
    if result.reason == "bad_credentials":
        return JSONResponse({"detail": BAD_CREDENTIALS}, status_code=401, headers=NO_STORE)
    if result.reason == "unknown_email":
        return JSONResponse({"detail": UNKNOWN_EMAIL}, status_code=401, headers=NO_STORE)
    if result.reason == "paused":
        wait = result.retry_after_seconds or 300
        minutes = max(1, -(-wait // 60))  # round up to whole minutes
        headers = {**NO_STORE, "Retry-After": str(wait)}
        return JSONResponse(
            {"detail": f"Too many attempts. Try again in {minutes} minute(s)."},
            status_code=429,
            headers=headers,
        )
    if result.reason == "blocked":
        return JSONResponse(
            {"detail": "Reset your password to continue.", "blocked": True},
            status_code=403,
            headers=NO_STORE,
        )
    assert result.user is not None and result.token is not None
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
    return MeOut(id=u.id, name=u.name, email=u.email, role=u.role)


@router.post("/logout", status_code=204)
def logout(request: Request, db: DB, _: CurrentUser) -> Response:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        service.logout(db, token)
        db.commit()
    out = Response(status_code=204, headers=NO_STORE)
    out.delete_cookie(
        SESSION_COOKIE, path="/", httponly=True, secure=_cookie_secure(), samesite="strict"
    )
    return out


@router.get("/me", response_model=MeOut)
def me(current: CurrentUser) -> MeOut:
    return MeOut(id=current.id, name=current.name, email=current.email, role=current.role)


class ResetRequestIn(BaseModel):
    email: str = Field(max_length=MAX_EMAIL)


class ResetConfirmIn(BaseModel):
    email: str = Field(max_length=MAX_EMAIL)
    code: str = Field(max_length=32)
    new_password: str = Field(max_length=MAX_PASSWORD)


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
    minimum = get_settings().password_min_length
    if len(body.new_password) < minimum:
        # Checked before the code, so a short password does not use up an attempt.
        return JSONResponse(
            {"detail": f"Password must be at least {minimum} characters."},
            status_code=400,
            headers=NO_STORE,
        )
    ok = reset.confirm_reset(db, body.email, body.code, body.new_password)
    db.commit()
    if not ok:
        return JSONResponse(
            {"detail": "That code is not valid."}, status_code=400, headers=NO_STORE
        )
    return Response(status_code=204, headers=NO_STORE)
