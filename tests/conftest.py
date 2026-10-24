import os
from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.orm import Session, sessionmaker

if TYPE_CHECKING:
    from analekh.db.models import Model, User

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
            # Many tests provoke constraint errors on purpose (duplicate email, bad role, a
            # race on the file hash) and the code handles them. The server log is shared with
            # the working database and should show only errors that really happen, so the test
            # database logs none; a test that fails says so through pytest.
            conn.execute(
                text(f"ALTER DATABASE \"{target.database}\" SET log_min_messages = 'fatal'")
            )
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
    # Tests run the real sign-in; ENV=dev alone would switch it off (test_auth_switch covers that).
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("AUTH_ENABLED", "true")
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
def db_session_factory(engine) -> sessionmaker[Session]:
    """Sessions on their own connections, for tests that need two at once. Data they commit is
    real: the test removes it itself."""
    return sessionmaker(bind=engine)


def _user(db: Session, uid: str, name: str, role: str = "analyst") -> "User":
    from analekh.db.models import User

    user = User(id=uid, email=f"{uid}@example.com", name=name, role=role)
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def analyst(db: Session) -> "User":
    return _user(db, "u-analyst-1", "Asha Analyst")


@pytest.fixture
def analyst2(db: Session) -> "User":
    return _user(db, "u-analyst-2", "Ravi Analyst")


@pytest.fixture
def admin(db: Session) -> "User":
    return _user(db, "u-admin-1", "Meera Admin", role="admin")


@pytest.fixture
def model(db: Session) -> "Model":
    from analekh.db.models import Company, Model

    company = Company(nse_symbol="FIXTCO", name="Fixture Co Limited", isin="INE000F01011")
    db.add(company)
    db.flush()
    workbook = Model(company_id=company.id, name="Fixture Co model", origin="built")
    db.add(workbook)
    db.flush()
    return workbook


@pytest.fixture
def store(tmp_path):
    from analekh.ingest.storage import LocalStore

    return LocalStore(tmp_path / "objects")
