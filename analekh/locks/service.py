"""Per-model locks (model-locks stage 2): one person or job works on a model at a time.

`acquire` alone decides who holds a lock: inserts with `ON CONFLICT (model_id) DO NOTHING`, so
primary key settles a race, exactly one caller wins. Nothing here commits (caller owns
transaction), except `holding`, which wraps a request's inline work and commits so lock is visible
while work runs.
"""

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from analekh.db.models import AuditEntry, ModelLock, User

ACTIVITIES = ("update", "build", "report")


class LockHeld(Exception):
    """Someone else holds the model: who, doing what, since when."""

    def __init__(self, *, holder_name: str, activity: str, taken_at: datetime) -> None:
        super().__init__(f"{holder_name} is working on this model ({activity})")
        self.holder_name = holder_name
        self.activity = activity
        self.taken_at = taken_at


def _held(session: Session, model_id: int) -> tuple[ModelLock, str] | None:
    """The current lock on a model and its holder's name, read fresh from the database."""
    row = session.execute(select(ModelLock, User.name).join(User, User.id == ModelLock.user_id).where(ModelLock.model_id == model_id).execution_options(populate_existing=True)).one_or_none()
    return None if row is None else (row[0], row[1])


def acquire(session: Session, *, model_id: int, user_id: str, activity: str, job_id: str | None = None) -> ModelLock:
    """Take lock on a model, or raise `LockHeld` if someone else has it.

    Re-entrant for holder: existing lock returns as is (activity and job kept), `last_seen_at`
    refreshed.
    """
    if activity not in ACTIVITIES:
        raise ValueError(f"unknown lock activity: {activity!r}")
    while True:
        # RETURNING tells whether this insert won. rowcount cannot: SQLAlchemy 2.1 with psycopg
        # reports -1 for this statement whether or not ON CONFLICT skipped the row.
        inserted = session.scalar(
            pg_insert(ModelLock).values(model_id=model_id, user_id=user_id, activity=activity, job_id=job_id).on_conflict_do_nothing(index_elements=[ModelLock.model_id]).returning(ModelLock.model_id)
        )
        held = _held(session, model_id)
        if held is None:
            # The holder let go between our insert and our read: try again.
            continue
        lock, holder_name = held
        if inserted is not None:
            return lock
        if lock.user_id != user_id:
            raise LockHeld(holder_name=holder_name, activity=lock.activity, taken_at=lock.taken_at)
        session.execute(update(ModelLock).where(ModelLock.model_id == model_id).values(last_seen_at=func.clock_timestamp()))
        session.refresh(lock)
        return lock


def release(session: Session, *, model_id: int, user_id: str) -> bool:
    """Give a lock back. Only its holder can; returns whether a lock was removed."""
    result = session.execute(delete(ModelLock).where(ModelLock.model_id == model_id, ModelLock.user_id == user_id))
    return bool(result.rowcount)  # type: ignore[attr-defined]


def attach_job(session: Session, *, model_id: int, user_id: str, job_id: str, activity: str) -> bool:
    """Hand holder's lock to a queued job, so job gives it back when it ends.

    `acquire` keeps an existing lock as is, so a holder starting another job needs this to record
    the new job. Only holder's lock moves; returns whether it did.
    """
    if activity not in ACTIVITIES:
        raise ValueError(f"unknown lock activity: {activity!r}")
    result = session.execute(update(ModelLock).where(ModelLock.model_id == model_id, ModelLock.user_id == user_id).values(job_id=job_id, activity=activity, last_seen_at=func.clock_timestamp()))
    return bool(result.rowcount)  # type: ignore[attr-defined]


@contextmanager
def holding(session: Session, *, model_ids: Iterable[int], user_id: str, activity: str) -> Iterator[None]:
    """Hold locks on these models while inline work runs (report, build step).

    Locks committed before work starts, so colleagues see them while it runs. When work ends locks
    are given back and committed with it; on failure its changes roll back first, only the release
    commits. Locks user already held (another tab, own queued update) left as they were, so is a
    lock user handed to a queued job during the work (`attach_job`): job gives that one back. Raises
    `LockHeld`, taking nothing, if a colleague holds any.
    """
    taken: list[int] = []
    try:
        for model_id in sorted(set(model_ids)):  # one order everywhere: no deadlocks
            before = status(session, model_id=model_id)
            already_mine = before is not None and before.user_id == user_id
            acquire(session, model_id=model_id, user_id=user_id, activity=activity)
            if not already_mine:
                taken.append(model_id)
    except LockHeld:
        session.rollback()
        raise
    session.commit()
    finished = False
    try:
        yield
        finished = True
    finally:
        if not finished:
            session.rollback()
        if taken:
            session.execute(
                delete(ModelLock).where(
                    ModelLock.model_id.in_(taken),
                    ModelLock.user_id == user_id,
                    ModelLock.job_id.is_(None),  # not handed to a job meanwhile
                )
            )
        session.commit()


def release_for_job(session: Session, *, model_id: int, job_id: str) -> bool:
    """Give back the lock a background job took; returns whether a lock was removed."""
    result = session.execute(delete(ModelLock).where(ModelLock.model_id == model_id, ModelLock.job_id == job_id))
    return bool(result.rowcount)  # type: ignore[attr-defined]


def force_release(session: Session, *, model_id: int, admin_id: str) -> ModelLock | None:
    """An admin frees a model whoever holds it. The audit log records whose lock it was."""
    held = _held(session, model_id)
    if held is None:
        return None
    lock, holder_name = held
    session.add(
        AuditEntry(
            user_id=admin_id,
            action="lock.release",
            detail={
                "model_id": model_id,
                "holder_id": lock.user_id,
                "holder_name": holder_name,
                "taken_at": lock.taken_at.isoformat(),
            },
        )
    )
    session.delete(lock)
    session.flush()
    return lock


def status(session: Session, *, model_id: int) -> ModelLock | None:
    """The lock on a model, or None when it is free."""
    held = _held(session, model_id)
    return None if held is None else held[0]
