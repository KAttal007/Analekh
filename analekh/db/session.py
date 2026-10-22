from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from analekh.config import get_settings


@lru_cache
def get_engine() -> Engine:
    cfg = get_settings()
    return create_engine(
        cfg.database_url,
        pool_pre_ping=True,
        pool_size=cfg.db_pool_size,
        max_overflow=cfg.db_pool_overflow,
        pool_timeout=cfg.db_pool_timeout_seconds,
    )


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """One transaction per unit of work: commit on success, roll back on error."""
    session = _session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    with session_scope() as session:
        yield session
