"""Shared API dependencies. Tests override get_session and get_store."""

from functools import lru_cache
from typing import Annotated, Any

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from analekh.api import schemas
from analekh.config import get_settings
from analekh.db.models import Company
from analekh.db.session import get_session
from analekh.ingest.storage import ObjectStore, default_store
from analekh.universe.search import get as get_company


@lru_cache
def get_store() -> ObjectStore:
    """One store per process. A failed connect raises (and isn't cached), so the next request
    tries again once storage is up."""
    return default_store()


def get_user() -> str:
    """Single user until authentication lands (section 19.1 settings)."""
    return get_settings().default_user_id


DB = Annotated[Session, Depends(get_session)]
Store = Annotated[ObjectStore, Depends(get_store)]
User = Annotated[str, Depends(get_user)]


def company_or_404(db: Session, symbol: str) -> Company:
    c = get_company(db, symbol)
    if c is None:
        raise HTTPException(
            404,
            f"{symbol.upper()} is not in the NSE universe; run "
            "`analekh universe load` if the list has not been loaded",
        )
    return c


def job(task: Any, *args: Any) -> schemas.JobOut:
    """Queue a background job, or answer 503 at once when the queue isn't running (Celery would
    otherwise retry the broker and leave the request hanging)."""
    from analekh.jobs.health import NOT_RUNNING, queue_available

    if not queue_available():
        raise HTTPException(503, NOT_RUNNING)
    result = task.delay(*args)
    return schemas.JobOut(job_id=result.id, status=result.status)
