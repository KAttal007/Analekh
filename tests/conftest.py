import os
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://app:app@localhost:5432/analekh")


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


@pytest.fixture(scope="session")
def engine():
    """Real PostgreSQL + pgvector (docker compose up postgres). Skips DB tests when unreachable."""
    from analekh.db.models import Base

    eng = create_engine(TEST_DB)
    try:
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
