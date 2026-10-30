"""Sign-in API: cookie, CSRF, protected routers, public endpoints (auth design, 5 and 6)."""

import logging
import re
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from analekh.api.main import app
from analekh.auth.service import create_user
from analekh.config import get_settings
from analekh.db.models import AuthSession, Company, FeedItem, User
from analekh.db.session import get_session
from analekh.universe.loader import parse_equity_list, upsert_universe
from tests.test_universe import EQUITY_L

GOOD = "Correct-Horse-Battery-9"
CSRF = {"X-Analekh-CSRF": "1"}
WRONG = "Email or password is incorrect."


@pytest.fixture
def raw(db):
    """A client with the real sign-in dependencies (only the database is swapped)."""
    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def user(db):
    return create_user(db, "kaushal@firm.in", "Kaushal", "analyst", GOOD)


def _login(client, email="kaushal@firm.in", password=GOOD):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_login_sets_httponly_samesite_strict_cookie(raw, user):
    res = _login(raw)
    assert res.status_code == 200
    body = res.json()
    assert set(body.pop("device")) == {"device_id", "name", "label"}
    assert body == {
        "id": user.id,
        "name": "Kaushal",
        "email": "kaushal@firm.in",
        "role": "analyst",
        "must_change_password": False,
    }
    cookie = res.headers["set-cookie"].lower()
    assert "analekh_session=" in cookie
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert "secure" not in cookie  # ENV=dev works over plain http


def test_cookie_is_secure_outside_dev(raw, user, monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    get_settings.cache_clear()
    cookie = _login(raw).headers["set-cookie"].lower()
    assert "secure" in cookie and "httponly" in cookie


def test_get_login_is_405_so_credentials_cannot_ride_a_url(raw, user):
    res = raw.get("/auth/login", params={"email": "kaushal@firm.in", "password": GOOD})
    assert res.status_code == 405


def test_login_never_reads_query_string(raw, user):
    res = raw.post("/auth/login", params={"email": "kaushal@firm.in", "password": GOOD})
    assert res.status_code == 422
    assert "set-cookie" not in res.headers


def test_wrong_password_message_identical_for_unknown_email(raw, user):
    """The reply never tells anyone whether an address has an account (owner, 2026-10-22)."""
    wrong = _login(raw, password="not the password")
    unknown = _login(raw, email="nobody@firm.in")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": WRONG}
    assert wrong.headers["cache-control"] == unknown.headers["cache-control"]
    assert "set-cookie" not in unknown.headers


def test_login_response_has_no_store_and_no_referrer(raw, user):
    for res in (_login(raw), _login(raw, password="nope")):
        assert res.headers["cache-control"] == "no-store"
        assert res.headers["referrer-policy"] == "no-referrer"


def test_three_failed_logins_over_http_pause_the_account(raw, user, db):
    for _ in range(3):
        assert _login(raw, password="wrong one").status_code == 401
    db.expire_all()
    assert db.get(User, user.id).failed_count == 3
    paused = _login(raw)  # right password, still refused, with the reply an unknown email gets
    assert paused.status_code == 401 and paused.json() == {"detail": WRONG}
    assert "set-cookie" not in paused.headers


def test_five_failed_logins_block_with_the_unknown_email_reply(raw, user, db):
    for _ in range(5):
        _login(raw, password="wrong one")
        user.paused_until = None  # skip the pause so the next failure counts
    db.flush()
    res = _login(raw)
    assert res.status_code == 401 and res.json() == {"detail": WRONG}


def test_paused_and_blocked_replies_match_an_unknown_email(raw, user, db):
    """Security audit run-1: replies must not reveal which emails have an account (rule 9)."""
    replies = []
    for email in ("kaushal@firm.in", "nobody@firm.in"):
        replies.append([(r.status_code, r.json()) for r in (_login(raw, email=email, password="wrong one") for _ in range(6))])
    assert replies[0] == replies[1]


def test_me_and_logout_round_trip(raw, user, db):
    _login(raw)
    me = raw.get("/auth/me")
    assert me.status_code == 200 and me.json()["email"] == "kaushal@firm.in"
    assert raw.post("/auth/logout").status_code == 403  # CSRF header missing
    out = raw.post("/auth/logout", headers=CSRF)
    assert out.status_code == 204
    assert 'analekh_session=""' in out.headers["set-cookie"].lower() or ("max-age=0" in out.headers["set-cookie"].lower())
    assert db.scalar(select(AuthSession.token_hash)) is None
    raw.cookies.clear()
    assert raw.get("/auth/me").status_code == 401


def test_disabled_user_session_gets_401(raw, user, db):
    _login(raw)
    user.is_active = False
    db.flush()
    assert raw.get("/auth/me").status_code == 401


def test_post_without_csrf_header_is_403(raw, user):
    _login(raw)
    assert raw.post("/watchlist", json={"symbol": "X"}).status_code == 403
    assert raw.post("/watchlist", json={"symbol": "X"}, headers=CSRF).status_code != 403


def test_get_needs_no_csrf_header(raw, user):
    _login(raw)
    assert raw.get("/watchlist").status_code == 200


def test_login_itself_needs_no_csrf_header(raw, user):
    assert _login(raw).status_code == 200  # _login sends no CSRF header


def test_admin_only_dependency_refuses_analyst(raw, user, db):
    from analekh.api.deps import AdminUser

    @app.get("/_probe_admin")
    def probe(who: AdminUser) -> dict:  # noqa: ARG001
        return {"ok": True}

    try:
        _login(raw)
        res = raw.get("/_probe_admin")
        assert res.status_code == 403 and res.json() == {"detail": "Admins only."}
        user.role = "admin"
        db.flush()
        assert raw.get("/_probe_admin").status_code == 200
    finally:
        app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", "") != "/_probe_admin"]


_OPEN = (
    "/auth/login",
    "/auth/reset/",
    "/auth/password-rules",
    "/public/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
)


def test_every_non_public_route_requires_session(raw):
    checked = 0
    for route, methods in app.openapi()["paths"].items():
        if route.startswith(_OPEN):
            continue
        path = re.sub(r"\{[^}]+\}", "x", route)
        for method in methods:
            res = raw.request(method.upper(), path, json={} if method != "get" else None)
            assert res.status_code == 401, f"{method} {route} -> {res.status_code}"
            assert res.json() == {"detail": "Sign in required."}
            checked += 1
    assert checked > 30


def test_public_routes_stay_open(raw):
    assert raw.get("/public/welcome").status_code == 200
    assert raw.get("/public/calendar").status_code == 200
    assert raw.get("/openapi.json").status_code == 200
    assert raw.get("/docs").status_code == 200


def test_public_welcome_mirrors_desk_counts(raw, db):
    upsert_universe(db, parse_equity_list(EQUITY_L))
    res = raw.get("/public/welcome")
    assert set(res.json()) == {
        "companies_in_scope",
        "filings_total",
        "reported",
        "quarter_label",
        "latest_filed_at",
    }
    from analekh.desk import desk

    d = desk(db, limit=1)
    assert res.json()["companies_in_scope"] == d.companies_in_scope
    assert res.json()["filings_total"] == d.filings_total


def test_public_calendar_has_no_watched_flag(raw, db):
    upsert_universe(db, parse_equity_list(EQUITY_L))
    c = db.scalar(select(Company).where(Company.nse_symbol == "DEMOFIN"))
    when = date.today().strftime("%d-%b-%Y")
    db.add(
        FeedItem(
            feed="board_meetings",
            item_key="g-1",
            title="Demo Fin",
            link="https://example.test/x",
            description=f"Financial Results |Meeting Date: {when}",
            pub_date=datetime.now(),
            company_id=c.id,
        )
    )
    db.flush()
    res = raw.get("/public/calendar", params={"start": date.today(), "end": date.today()})
    assert res.status_code == 200
    body = res.json()
    assert body["events"], "the seeded board meeting should appear"
    for event in body["events"]:
        assert "watched" not in event
    assert "unscheduled" not in body
    assert raw.get("/public/calendar", params={"start": "2026-02-01", "end": "2026-01-01"}).status_code == 422


def test_access_log_has_no_secrets(raw, db, caplog):
    secret_pw = "Sup3r-secret-passw0rd!"
    create_user(db, "z@firm.in", "Z", "analyst", secret_pw)
    with caplog.at_level(logging.DEBUG):
        ok = _login(raw, email="z@firm.in", password=secret_pw)
        _login(raw, email="z@firm.in", password="another-wrong-one")
        raw.get("/auth/me")
    token = raw.cookies.get("analekh_session")
    assert ok.status_code == 200 and token
    text = "\n".join(r.getMessage() + " " + str(r.__dict__) for r in caplog.records)
    for secret in (secret_pw, "another-wrong-one", token):
        assert secret not in text


def test_form_limits_match_the_service_limits(raw, user):
    from analekh.auth.passwords import MAX_EMAIL

    assert _login(raw, password="x" * (get_settings().password_max_length + 1)).status_code == 422
    assert _login(raw, email="a" * (MAX_EMAIL + 1)).status_code == 422
    assert _login(raw, password="x" * get_settings().password_max_length).status_code == 401
