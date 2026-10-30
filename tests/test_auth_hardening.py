"""Stage 1 follow-ups: sign out everywhere, session purge, Users page fields, reset length check,
the body-size cap and the reset timing gap (auth design, sections 5 and 7)."""

import json
import statistics
import time
from datetime import UTC, datetime, timedelta

import anyio
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from analekh.api.main import app
from analekh.auth import reset, service
from analekh.auth.passwords import PasswordTooLong, PasswordTooShort
from analekh.auth.tokens import create_api_token
from analekh.config import get_settings
from analekh.db.models import AuditEntry, AuthSession, PasswordReset, UserDevice
from analekh.db.session import get_session

GOOD = "Correct-Horse-Battery-9"
NEW = "Brand-New-Passphrase-4"
CSRF = {"X-Analekh-CSRF": "1"}
T0 = datetime(2026, 10, 22, 9, 0, tzinfo=UTC)


@pytest.fixture
def raw(db):
    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def user(db):
    return service.create_user(db, "kaushal@firm.in", "Kaushal", "admin", GOOD)


@pytest.fixture
def sent(monkeypatch):
    box: list[tuple[str, str, str]] = []
    monkeypatch.setattr(reset, "send_mail", lambda to, s, b: box.append((to, s, b)) or True)
    return box


def _signed_in(db) -> TestClient:
    app.dependency_overrides[get_session] = lambda: db
    c = TestClient(app)
    assert c.post("/auth/login", json={"email": "kaushal@firm.in", "password": GOOD}).is_success
    return c


def test_sign_out_everywhere_ends_every_session_and_token(raw, db, user):
    laptop, desktop = _signed_in(db), _signed_in(db)
    _, token = create_api_token(db, user, "bridge")
    bearer = {"Authorization": f"Bearer {token}"}
    assert raw.get("/auth/me", headers=bearer).status_code == 200

    res = laptop.post("/auth/logout-everywhere", headers=CSRF)
    assert res.status_code == 204
    assert 'analekh_session=""' in res.headers["set-cookie"] or "Max-Age=0" in res.headers["set-cookie"]
    assert laptop.get("/auth/me").status_code == 401
    assert desktop.get("/auth/me").status_code == 401
    assert raw.get("/auth/me", headers=bearer).status_code == 401
    assert db.scalars(select(AuthSession).where(AuthSession.user_id == user.id)).all() == []
    actions = db.scalars(select(AuditEntry.action).where(AuditEntry.user_id == user.id)).all()
    assert "user.logout_everywhere" in actions


def test_sign_out_everywhere_needs_the_anti_forgery_header(db, user):
    c = _signed_in(db)
    assert c.post("/auth/logout-everywhere").status_code == 403
    assert c.get("/auth/me").status_code == 200


def test_sign_out_everywhere_needs_a_session(raw):
    assert raw.post("/auth/logout-everywhere", headers=CSRF).status_code == 401


def test_purge_deletes_only_unusable_sessions(db, user):
    cfg = get_settings()
    fresh = service.login(db, "kaushal@firm.in", GOOD, now=T0).token
    idle = service.login(db, "kaushal@firm.in", GOOD, now=T0 - timedelta(hours=cfg.session_idle_hours, minutes=1)).token
    assert fresh and idle
    row = db.get(AuthSession, service._hash_token(fresh))
    assert row is not None
    other = service.create_user(db, "other@firm.in", "Other", "analyst", GOOD)
    device = UserDevice(user_id=other.id, key_hash="k" * 64)
    db.add(device)
    db.flush()
    db.add(
        AuthSession(
            token_hash="x" * 64,
            user_id=other.id,
            device_pk=device.id,
            created_at=T0 - timedelta(hours=cfg.session_max_hours, minutes=1),
            last_seen_at=T0,
        )
    )
    db.flush()
    assert service.purge_expired_sessions(db, now=T0) == 2
    left = db.scalars(select(AuthSession.token_hash)).all()
    assert left == [service._hash_token(fresh)]


def test_purge_runs_on_the_beat_schedule():
    from analekh.jobs.app import app as celery_app

    entry = celery_app.conf.beat_schedule["purge-sessions"]
    assert entry["task"] == "analekh.jobs.tasks.purge_sessions"


def test_users_list_shows_last_seen_and_current_pause(db, user, monkeypatch):
    from analekh.api.deps import get_current

    analyst = service.create_user(db, "ana@firm.in", "Ana", "analyst", GOOD)
    service.login(db, "kaushal@firm.in", GOOD)
    analyst.paused_until = datetime.now(UTC) + timedelta(minutes=10)
    db.flush()
    app.dependency_overrides[get_session] = lambda: db
    app.dependency_overrides[get_current] = lambda: user
    try:
        rows = {r["email"]: r for r in TestClient(app).get("/users").json()}
    finally:
        app.dependency_overrides.clear()
    assert rows["kaushal@firm.in"]["last_seen_at"] is not None
    assert rows["kaushal@firm.in"]["paused_until"] is None
    assert rows["ana@firm.in"]["last_seen_at"] is None
    assert rows["ana@firm.in"]["paused_until"] is not None


def test_users_list_hides_a_pause_that_has_ended(db, user):
    from analekh.api.deps import get_current

    user.paused_until = datetime.now(UTC) - timedelta(minutes=1)
    db.flush()
    app.dependency_overrides[get_session] = lambda: db
    app.dependency_overrides[get_current] = lambda: user
    try:
        rows = TestClient(app).get("/users").json()
    finally:
        app.dependency_overrides.clear()
    assert rows[0]["paused_until"] is None


def test_confirm_reset_refuses_bad_length_before_spending_an_attempt(db, user, sent):
    reset.request_reset(db, "kaushal@firm.in")
    code = sent[-1][2].split("code is ")[1][:6]
    minimum = get_settings().password_min_length
    with pytest.raises(PasswordTooShort):
        reset.confirm_reset(db, "kaushal@firm.in", "000000", "x" * (minimum - 1))
    with pytest.raises(PasswordTooLong):
        reset.confirm_reset(db, "kaushal@firm.in", "000000", "x" * 10_000)
    row = db.get(PasswordReset, user.id)
    assert row is not None and row.attempts == 0
    assert reset.confirm_reset(db, "kaushal@firm.in", code, NEW) is True


@pytest.fixture
def small_cap(monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_CEILING_BYTES", "2048")
    monkeypatch.setenv("REQUEST_BODY_OVERHEAD_BYTES", "0")
    get_settings.cache_clear()


def test_declared_oversized_body_is_413_before_the_route(raw, small_cap):
    res = raw.post("/auth/login", content=b"x" * 4096, headers={"Content-Type": "application/json"})
    assert res.status_code == 413
    assert "the most Analekh accepts" in res.json()["detail"]


def test_streamed_oversized_body_is_cut_off(raw, small_cap):
    def chunks():
        for _ in range(100):
            yield b"x" * 1024

    res = raw.post("/auth/login", content=chunks(), headers={"Content-Type": "application/json"})
    assert res.status_code == 413


def test_small_bodies_pass_the_cap(raw, user, small_cap):
    res = raw.post("/auth/login", json={"email": "kaushal@firm.in", "password": GOOD})
    assert res.status_code == 200


def _reply_seconds(path: str, payload: dict) -> tuple[int, float]:
    """Status and the time until the reply's last byte is sent, calling the app over ASGI.
    (TestClient waits for background tasks too, so it cannot see when the reply left.)"""
    body = json.dumps(payload).encode()
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"host", b"testserver"),
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ],
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }
    out: dict[str, float | int] = {}
    pending = [{"type": "http.request", "body": body, "more_body": False}]

    async def receive():
        return pending.pop() if pending else {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.start":
            out["status"] = message["status"]
        if message["type"] == "http.response.body" and not message.get("more_body"):
            out["at"] = time.perf_counter()

    async def run() -> float:
        start = time.perf_counter()
        await app(scope, receive, send)
        return float(out["at"]) - start

    seconds = anyio.run(run)
    return int(out["status"]), seconds


def test_reset_request_timing_known_vs_unknown(db, sent, monkeypatch):
    """Known account must not answer measurably slower than unknown: mail goes out after reply,
    extra work before it is one small write. Measured 2026-10-22 on dev machine: medians within a
    few ms. With a 200 ms SMTP stand-in, regression to sending before reply would show full 200 ms;
    bound leaves room for a busy runner.
    """
    monkeypatch.setenv("SMTP_URL", "smtp://u:p@mail.example:587")
    get_settings.cache_clear()
    slow_smtp = 0.2

    def slow_send(to, s, b):
        time.sleep(slow_smtp)  # a real SMTP round trip
        sent.append((to, s, b))
        return True

    monkeypatch.setattr(reset, "send_mail", slow_send)
    app.dependency_overrides[get_session] = lambda: db
    rounds = 8
    for i in range(rounds):
        service.create_user(db, f"user{i}@firm.in", f"U{i}", "analyst", GOOD)
    known, unknown = [], []
    try:
        for i in range(rounds):  # alternate, so drift hits both equally
            status, took = _reply_seconds("/auth/reset/request", {"email": f"user{i}@firm.in"})
            assert status == 202
            known.append(took)
            status, took = _reply_seconds("/auth/reset/request", {"email": f"nobody{i}@firm.in"})
            assert status == 202
            unknown.append(took)
    finally:
        app.dependency_overrides.clear()
    assert len(sent) == rounds  # every known account did get its mail, after its reply
    gap = statistics.median(known) - statistics.median(unknown)
    assert gap < slow_smtp / 4, f"known accounts answer {gap * 1000:.0f} ms slower"
