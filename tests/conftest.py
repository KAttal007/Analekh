import os
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.orm import Session

# A database of its own: tests run in rolled-back transactions, but against the working database
# (10M facts after the full sweep) every unscoped query scans real data: 6 minutes instead of 50 s.
TEST_DB = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://app:app@127.0.0.1:5432/analekh_test"
)


def _ensure_database(url: str) -> None:
    """Create the test database on first use (from the server's postgres database)."""
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": target.database},
            )
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    finally:
        admin.dispose()


@pytest.fixture(autouse=True)
def _no_real_claude(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Tests never call the real Claude API, whatever key the developer's .env holds.

    An environment variable outranks .env in pydantic-settings, so an empty key switches off
    every code path that is gated on one (e.g. AI label matching on template upload).
    """
    from analekh.config import get_settings

    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _fresh_in_memory_state() -> Iterator[None]:
    """The per-address sign-in counts and the public answer cache live in memory; no test may
    inherit another's."""
    from analekh.api.routers import public
    from analekh.auth import ip_limit

    ip_limit.clear()
    public.clear_cache()
    yield
    ip_limit.clear()
    public.clear_cache()


@pytest.fixture(scope="session")
def engine():
    """Real PostgreSQL + pgvector (docker compose up postgres). Skips DB tests when unreachable."""
    from analekh.db.models import Base

    eng = create_engine(TEST_DB)
    try:
        _ensure_database(TEST_DB)
        with eng.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"PostgreSQL not reachable at {TEST_DB}: {exc}")
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def db(engine) -> Iterator[Session]:
    """Each test runs in a transaction that is rolled back."""
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


@pytest.fixture
def store(tmp_path):
    from analekh.ingest.storage import LocalStore

    return LocalStore(tmp_path / "objects")
