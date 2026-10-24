"""Per-model locks (model-locks stage 2): one person or job works on a model at a time.

`acquire` is the only place that decides who holds a lock: it inserts with
`ON CONFLICT (model_id) DO NOTHING`, so the database's primary key settles a race and exactly one
caller wins. Nothing here commits, the caller owns the transaction, except `holding`, which
wraps a request's inline work and commits so the lock is visible while the work runs.
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
    row = session.execute(
        select(ModelLock, User.name)
        .join(User, User.id == ModelLock.user_id)
        .where(ModelLock.model_id == model_id)
        .execution_options(populate_existing=True)
    ).one_or_none()
    return None if row is None else (row[0], row[1])


def acquire(
    session: Session, *, model_id: int, user_id: str, activity: str, job_id: str | None = None
) -> ModelLock:
    """Take the lock on a model, or raise `LockHeld` if someone else has it.

    Re-entrant for the holder: the existing lock comes back as it is (its activity and job are
    kept) with `last_seen_at` refreshed.
    """
    if activity not in ACTIVITIES:
        raise ValueError(f"unknown lock activity: {activity!r}")
    while True:
        # RETURNING tells whether this insert won. rowcount cannot: SQLAlchemy 2.1 with psycopg
        # reports -1 for this statement whether or not ON CONFLICT skipped the row.
        inserted = session.scalar(
            pg_insert(ModelLock)
            .values(model_id=model_id, user_id=user_id, activity=activity, job_id=job_id)
            .on_conflict_do_nothing(index_elements=[ModelLock.model_id])
            .returning(ModelLock.model_id)
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
        session.execute(
            update(ModelLock)
            .where(ModelLock.model_id == model_id)
            .values(last_seen_at=func.clock_timestamp())
        )
        session.refresh(lock)
        return lock


def release(session: Session, *, model_id: int, user_id: str) -> bool:
    """Give a lock back. Only its holder can; returns whether a lock was removed."""
    result = session.execute(
        delete(ModelLock).where(ModelLock.model_id == model_id, ModelLock.user_id == user_id)
    )
    return bool(result.rowcount)  # type: ignore[attr-defined]


def attach_job(
    session: Session, *, model_id: int, user_id: str, job_id: str, activity: str
) -> bool:
    """Hand the holder's lock to a queued job, so the job gives it back when it ends.

    `acquire` keeps an existing lock as it is, so a holder who starts another job needs this to
    record the new job. Only the holder's lock moves; returns whether it did.
    """
    if activity not in ACTIVITIES:
        raise ValueError(f"unknown lock activity: {activity!r}")
    result = session.execute(
        update(ModelLock)
        .where(ModelLock.model_id == model_id, ModelLock.user_id == user_id)
        .values(job_id=job_id, activity=activity, last_seen_at=func.clock_timestamp())
    )
    return bool(result.rowcount)  # type: ignore[attr-defined]


@contextmanager
def holding(
    session: Session, *, model_ids: Iterable[int], user_id: str, activity: str
) -> Iterator[None]:
    """Hold the locks on these models while inline work runs (a report, a build step).

    The locks are committed before the work starts, so colleagues see them while it runs. When
    the work ends the locks are given back and committed with it; if it fails, its changes are
    rolled back first, so only the release is committed. Locks the user already held (another
    tab, their own queued update) are left as they were, and so is a lock the user handed to a
    queued job while the work ran (`attach_job`): the job gives that one back. Raises `LockHeld`,
    taking nothing, if a colleague holds any of them.
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
    result = session.execute(
        delete(ModelLock).where(ModelLock.model_id == model_id, ModelLock.job_id == job_id)
    )
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
