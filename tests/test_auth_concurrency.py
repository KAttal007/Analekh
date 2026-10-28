"""Sign-in under parallel load (review finding 1).

Each simulated request gets own database connection and commits, as real requests do. A flood of
wrong passwords at the same moment must not skip the pause or block, and API must answer every
request without server error.
"""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session, sessionmaker

from analekh.api.main import app
from analekh.auth import service
from analekh.config import get_settings
from analekh.db.models import AuthSession, User
from analekh.db.session import get_session

GOOD = "Correct-Horse-Battery-9"


@pytest.fixture
def committed_user(engine):
    """A user committed to the test database (other connections can see it), removed after."""
    email = f"flood-{uuid4().hex[:8]}@firm.in"
    with Session(engine) as s:
        user = service.create_user(s, email, "Flood", "analyst", GOOD)
        s.commit()
        uid = user.id
    yield email, uid
    with Session(engine) as s:
        s.execute(delete(AuthSession).where(AuthSession.user_id == uid))
        s.execute(delete(User).where(User.id == uid))
        s.commit()


def _attempt(engine, email: str, password: str) -> str:
    with Session(engine) as s:
        reason = service.login(s, email, password).reason
        s.commit()
        return reason


def test_parallel_wrong_passwords_cannot_skip_the_pause(engine, committed_user):
    email, uid = committed_user
    pause_after = get_settings().login_pause_after
    with ThreadPoolExecutor(max_workers=16) as pool:
        reasons = list(pool.map(lambda _: _attempt(engine, email, "wrong"), range(32)))
    with Session(engine) as s:
        user = s.get(User, uid)
        assert user.failed_count == pause_after
        assert user.paused_until is not None
    counts = Counter(reasons)
    assert counts["bad_credentials"] == pause_after
    assert counts["paused"] == 32 - pause_after


def test_login_flood_gets_no_server_errors(engine, committed_user):
    email, _ = committed_user
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def session():
        s = factory()
        try:
            yield s
            s.commit()
        finally:
            s.close()

    app.dependency_overrides[get_session] = session
    try:
        client = TestClient(app)
        targets = [email, "nobody-here@firm.in"] * 20

        def hit(target: str) -> int:
            return client.post("/auth/login", json={"email": target, "password": "wrong"}).status_code

        with ThreadPoolExecutor(max_workers=12) as pool:
            codes = list(pool.map(hit, targets))
    finally:
        app.dependency_overrides.clear()
    assert all(code < 500 for code in codes), Counter(codes)
    assert set(codes) <= {401, 429, 403}
