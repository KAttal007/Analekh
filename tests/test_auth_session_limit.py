"""Session limit and remembered devices: at most `session_max_per_user` live sessions on other
devices; one more picks a device to end. The same browser signing in again reuses its slot."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from analekh.api.main import app
from analekh.auth import service
from analekh.auth.devices import DEVICE_COOKIE, DeviceNameError, clean_device_name, device_label
from analekh.auth.service import create_user, login, name_device, replace_session, revoke_user_sessions, user_for_token
from analekh.config import get_settings
from analekh.db.models import AuthSession, SignInChoice, UserDevice
from analekh.db.session import get_session

T0 = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)
GOOD = "Correct-Horse-Battery-9"
EMAIL = "kaushal@firm.in"
CSRF = {"X-Analekh-CSRF": "1"}
CHROME_WIN = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def _limit() -> int:
    return get_settings().session_max_per_user


@pytest.fixture
def user(db):
    return create_user(db, EMAIL, "Kaushal", "analyst", GOOD)


def _fill(db, now=T0):
    """Sign in from `_limit()` different browsers (no device cookie: each is a new device)."""
    return [login(db, EMAIL, GOOD, now=now + timedelta(seconds=i)) for i in range(_limit())]


def _sessions(db, user_id):
    return db.scalar(select(func.count()).select_from(AuthSession).where(AuthSession.user_id == user_id))


# --- the limit ---


def test_sessions_up_to_the_limit_open_each_on_its_own_device(db, user):
    results = _fill(db)
    assert all(r.ok and r.device_key and r.device for r in results)
    assert _sessions(db, user.id) == _limit()
    assert len({r.device.device_id for r in results}) == _limit()
    stored = set(db.scalars(select(UserDevice.key_hash)))
    assert not stored & {r.device_key for r in results}  # only hashes stored


def test_one_more_device_is_held_with_the_live_devices(db, user):
    _fill(db)
    held = login(db, EMAIL, GOOD, now=T0 + timedelta(minutes=1))
    assert not held.ok and held.reason == "session_limit" and held.token is None
    assert held.choice_token and len(held.devices) == _limit()
    assert _sessions(db, user.id) == _limit()  # nothing opened
    assert db.scalar(select(SignInChoice.token_hash)) != held.choice_token


def test_the_same_browser_again_reuses_its_slot(db, user):
    first, *_ = _fill(db)
    again = login(db, EMAIL, GOOD, now=T0 + timedelta(minutes=1), device_key=first.device_key)
    assert again.ok and again.device.device_id == first.device.device_id
    assert _sessions(db, user.id) == _limit()
    assert user_for_token(db, first.token, now=T0 + timedelta(minutes=1)) is None  # old one ended


def test_a_device_key_of_another_user_is_not_theirs(db, user):
    create_user(db, "other@firm.in", "Other", "analyst", GOOD)
    theirs = login(db, "other@firm.in", GOOD, now=T0)
    _fill(db)
    held = login(db, EMAIL, GOOD, now=T0, device_key=theirs.device_key)
    assert held.reason == "session_limit"


@pytest.mark.parametrize("key", ["", "short", "x" * 500, "../../etc", "a b c" * 10])
def test_odd_device_cookies_count_as_a_new_device(db, user, key):
    assert login(db, EMAIL, GOOD, now=T0, device_key=key).device_key != key


def test_wrong_password_at_the_limit_is_still_just_wrong(db, user):
    _fill(db)
    assert login(db, EMAIL, "wrong", now=T0).reason == "bad_credentials"


def test_expired_sessions_do_not_count(db, user):
    _fill(db, now=T0 - timedelta(hours=get_settings().session_idle_hours, minutes=1))
    assert login(db, EMAIL, GOOD, now=T0).ok


# --- choosing a device to end ---


def test_replace_ends_the_chosen_device_and_signs_in(db, user):
    _fill(db)
    held = login(db, EMAIL, GOOD, now=T0)
    gone = held.devices[-1].device_id
    done = replace_session(db, held.choice_token, gone, now=T0 + timedelta(seconds=5), device_label="Firefox on macOS")
    assert done.ok and done.token and done.user is user and done.device_key
    assert done.device.label == "Firefox on macOS"
    live = db.scalars(select(UserDevice.device_id).join(AuthSession, AuthSession.device_pk == UserDevice.id)).all()
    assert len(live) == _limit() and gone not in live


def test_choice_token_is_one_use(db, user):
    _fill(db)
    held = login(db, EMAIL, GOOD, now=T0)
    assert replace_session(db, held.choice_token, held.devices[0].device_id, now=T0).ok
    again = replace_session(db, held.choice_token, held.devices[1].device_id, now=T0)
    assert again.reason == "choice_expired" and _sessions(db, user.id) == _limit()


def test_choice_token_expires(db, user):
    _fill(db)
    held = login(db, EMAIL, GOOD, now=T0)
    late = T0 + timedelta(minutes=get_settings().session_choice_minutes, seconds=1)
    assert replace_session(db, held.choice_token, held.devices[0].device_id, now=late).reason == "choice_expired"
    assert _sessions(db, user.id) == _limit()


def test_another_users_device_id_ends_nothing(db, user):
    create_user(db, "other@firm.in", "Other", "analyst", GOOD)
    theirs = login(db, "other@firm.in", GOOD, now=T0)
    _fill(db)
    held = login(db, EMAIL, GOOD, now=T0)
    again = replace_session(db, held.choice_token, theirs.device.device_id, now=T0)
    assert again.reason == "session_limit" and again.choice_token  # still full: a fresh choice
    assert service.user_for_token(db, theirs.token, now=T0) is not None


def test_revoke_also_drops_held_choices(db, user):
    _fill(db)
    held = login(db, EMAIL, GOOD, now=T0)
    revoke_user_sessions(db, user.id)
    assert replace_session(db, held.choice_token, held.devices[0].device_id, now=T0).reason == "choice_expired"


def test_purge_drops_expired_choices_and_forgotten_devices(db, user):
    _fill(db)
    login(db, EMAIL, GOOD, now=T0)
    service.purge_expired_sessions(db, now=T0 + timedelta(minutes=get_settings().session_choice_minutes, seconds=1))
    assert db.scalar(select(func.count()).select_from(SignInChoice)) == 0
    assert db.scalar(select(func.count()).select_from(UserDevice)) == _limit()  # still remembered
    service.purge_expired_sessions(db, now=T0 + timedelta(days=get_settings().device_cookie_days, minutes=1))
    assert db.scalar(select(func.count()).select_from(UserDevice)) == 0


# --- naming ---


def test_a_name_outlives_the_session(db, user):
    first = login(db, EMAIL, GOOD, now=T0)
    assert first.device.name is None
    assert name_device(db, first.token, "Office laptop").name == "Office laptop"
    service.logout(db, first.token)
    later = login(db, EMAIL, GOOD, now=T0 + timedelta(days=3), device_key=first.device_key)
    assert later.device.name == "Office laptop" and later.device.device_id == first.device.device_id


@pytest.mark.parametrize(
    ("raw", "clean"),
    [("  Office   laptop ", "Office laptop"), ("Kaushal's PC (home)", "Kaushal's PC (home)"), ("दफ़्तर", "दफ़्तर"), ("   ", None)],
)
def test_device_names_are_tidied(raw, clean):
    assert clean_device_name(raw) == clean


@pytest.mark.parametrize("raw", ["<script>", "a\x00b", "x" * 41, "name; DROP TABLE"])
def test_odd_device_names_are_refused(raw):
    with pytest.raises(DeviceNameError):
        clean_device_name(raw)


@pytest.mark.parametrize(
    ("ua", "label"),
    [
        (CHROME_WIN, "Chrome on Windows"),
        ("Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/130.0 Safari/537.36 Edg/130.0", "Edge on Windows"),
        ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile Safari/604.1", "Safari on iPhone"),
        ("Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36 Chrome/130.0 Mobile Safari/537.36", "Chrome on Android"),
        ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14.0; rv:131.0) Gecko/20100101 Firefox/131.0", "Firefox on macOS"),
        ("<script>alert(1)</script>", None),
        (None, None),
    ],
)
def test_device_label_is_fixed_vocabulary(ua, label):
    assert device_label(ua) == label


# --- over HTTP ---


@pytest.fixture
def raw(db):
    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _http_login(client):
    return client.post("/auth/login", json={"email": EMAIL, "password": GOOD}, headers={"User-Agent": CHROME_WIN})


def test_http_sets_a_lasting_httponly_device_cookie(raw, user):
    res = _http_login(raw)
    assert res.status_code == 200 and res.json()["device"]["label"] == "Chrome on Windows"
    cookie = next(c for c in res.headers.get_list("set-cookie") if c.startswith(f"{DEVICE_COOKIE}="))
    lowered = cookie.lower()
    assert "httponly" in lowered and "samesite=strict" in lowered
    assert f"max-age={get_settings().device_cookie_days * 86400}" in lowered


def test_http_limit_reply_then_replace(raw, user, db):
    for _ in range(_limit()):
        assert _http_login(TestClient(app)).status_code == 200
    res = _http_login(raw)
    assert res.status_code == 409 and "set-cookie" not in res.headers
    assert res.headers["cache-control"] == "no-store"
    body = res.json()
    assert body["limit"] == _limit() and len(body["devices"]) == _limit()
    assert set(body["devices"][0]) == {"device_id", "name", "label", "signed_in_at", "last_seen_at"}
    pick = body["devices"][0]["device_id"]
    done = raw.post("/auth/login/replace", json={"choice_token": body["choice_token"], "device_id": pick}, headers={"User-Agent": CHROME_WIN})
    assert done.status_code == 200 and done.json()["email"] == EMAIL
    assert raw.get("/auth/me").status_code == 200
    live = db.scalars(select(UserDevice.device_id).join(AuthSession, AuthSession.device_pk == UserDevice.id)).all()
    assert pick not in live


def test_http_same_browser_at_the_limit_signs_straight_in(raw, user):
    assert _http_login(raw).status_code == 200
    for _ in range(_limit() - 1):
        assert _http_login(TestClient(app)).status_code == 200
    assert _http_login(raw).status_code == 200  # raw still holds its device cookie


def test_http_name_this_device(raw, user):
    device = _http_login(raw).json()["device"]
    res = raw.post("/auth/device-name", json={"name": "Office laptop"}, headers=CSRF)
    assert res.status_code == 200 and res.json() == {**device, "name": "Office laptop"}
    assert raw.post("/auth/device-name", json={"name": "<b>"}, headers=CSRF).status_code == 400
    assert raw.post("/auth/device-name", json={"name": "x"}).status_code == 403  # anti-forgery header


def test_http_replace_with_a_bad_token_is_401(raw, user):
    res = raw.post("/auth/login/replace", json={"choice_token": "nope", "device_id": "abcd1234"})
    assert res.status_code == 401 and "set-cookie" not in res.headers


def test_http_replace_rejects_odd_device_ids(raw, user):
    res = raw.post("/auth/login/replace", json={"choice_token": "x", "device_id": "../../x"})
    assert res.status_code == 422
