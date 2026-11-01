"""Report thread lifecycle: drafting, approved, published (design: the flow)."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from analekh.config import get_settings
from analekh.db.models import ReportThread
from analekh.reports.store import StaleVersion, ThreadFrozen


class ThreadNotFound(Exception):
    """No such thread for this user. Someone else's thread looks exactly like a missing one."""


class ThreadBusy(Exception):
    """An AI job is writing to the draft."""


REPORT_TYPES = ("quarterly", "initiating")
FORMATS = ("word", "ppt")
BASES = ("consolidated", "standalone", "both")


def create_thread(
    db: Session,
    owner_id: str,
    company_id: int,
    report_type: str,
    format: str,  # noqa: A002 - matches the column name
    basis: str,
    quarter_end: date | None = None,
    model_id: int | None = None,
) -> ReportThread:
    """A new thread in `drafting`, at version 0. The caller has checked the company and model belong
    together and that the owner may use them."""
    if report_type not in REPORT_TYPES:
        raise ValueError("unknown report type")
    if format not in FORMATS:
        raise ValueError("unknown format")
    if basis not in BASES:
        raise ValueError("unknown basis")
    thread = ReportThread(
        owner_id=owner_id,
        company_id=company_id,
        model_id=model_id,
        report_type=report_type,
        format=format,
        basis=basis,
        quarter_end=quarter_end,
    )
    db.add(thread)
    db.flush()
    return thread


def get_owned(db: Session, thread_id: int, owner_id: str, *, for_update: bool = False) -> ReportThread:
    """The user's own thread, or ThreadNotFound. With `for_update` the row is locked until commit."""
    q = select(ReportThread).where(ReportThread.id == thread_id, ReportThread.owner_id == owner_id)
    if for_update:
        q = q.with_for_update()
    thread = db.scalars(q).one_or_none()
    if thread is None:
        raise ThreadNotFound
    return thread


def _busy_for() -> timedelta:
    cfg = get_settings()
    return timedelta(seconds=cfg.chat_turn_timeout_s + cfg.chat_busy_grace_s)


def is_busy(thread: ReportThread) -> bool:
    """True while an AI job holds the draft. A job that died stops counting after the timeout."""
    return thread.busy_since is not None and datetime.now(UTC) - thread.busy_since < _busy_for()


def claim(db: Session, thread_id: int, owner_id: str, base_version: int, job_id: str) -> None:
    """Take the draft for an AI job, in one statement: only if the thread is the user's, still being
    drafted, at `base_version`, and not busy. Raises ThreadNotFound, ThreadFrozen, ThreadBusy or
    StaleVersion. The caller commits before queueing the job."""
    res = db.execute(
        update(ReportThread)
        .where(
            ReportThread.id == thread_id,
            ReportThread.owner_id == owner_id,
            ReportThread.status == "drafting",
            ReportThread.current_version == base_version,
            or_(ReportThread.busy_since.is_(None), ReportThread.busy_since < func.now() - _busy_for()),
        )
        .values(busy_since=func.now(), busy_job_id=job_id)
        .execution_options(synchronize_session=False)
    )
    if res.rowcount == 1:  # type: ignore[attr-defined]
        return
    thread = get_owned(db, thread_id, owner_id)
    db.refresh(thread)
    if thread.status != "drafting":
        raise ThreadFrozen("the thread is no longer being drafted")
    if is_busy(thread):
        raise ThreadBusy("the AI is still writing")
    raise StaleVersion("the draft has changed since you opened it")


def release(db: Session, thread_id: int, job_id: str) -> None:
    """Hand the draft back. Only the job that claimed it can; a late job cannot free a newer claim."""
    db.execute(update(ReportThread).where(ReportThread.id == thread_id, ReportThread.busy_job_id == job_id).values(busy_since=None, busy_job_id=None).execution_options(synchronize_session=False))
