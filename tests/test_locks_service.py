"""Per-model locks (model-locks stage 2): the table, then the service that decides who holds one."""

import threading
import uuid
from datetime import datetime

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from analekh.db.models import AuditEntry, Company, Model, User
from analekh.locks import (
    LockHeld,
    acquire,
    force_release,
    release,
    release_for_job,
    status,
)


def _model_and_user(db: Session) -> tuple[Model, User]:
    company = Company(nse_symbol="LOCKCO", name="Lock Co Limited", isin="INE000K01011")
    db.add(company)
    db.flush()
    model = Model(company_id=company.id, name="Lock Co model", origin="built")
    user = User(id="u-lock-1", email="lock1@example.com", name="Lock One")
    db.add_all([model, user])
    db.flush()
    return model, user


def test_model_lock_table_exists(db):
    from analekh.db.models import ModelLock

    assert {"model_id", "user_id", "activity", "job_id", "taken_at", "last_seen_at"} <= set(ModelLock.__table__.columns.keys())


def test_lock_defaults_times_and_allows_no_job(db):
    from analekh.db.models import ModelLock

    model, user = _model_and_user(db)
    db.add(ModelLock(model_id=model.id, user_id=user.id, activity="update"))
    db.flush()
    lock = db.scalars(select(ModelLock).where(ModelLock.model_id == model.id)).one()
    db.refresh(lock)
    assert lock.job_id is None
    assert isinstance(lock.taken_at, datetime) and lock.taken_at.tzinfo is not None
    assert isinstance(lock.last_seen_at, datetime) and lock.last_seen_at.tzinfo is not None


def test_one_lock_per_model(db):
    from analekh.db.models import ModelLock

    model, user = _model_and_user(db)
    other = User(id="u-lock-2", email="lock2@example.com", name="Lock Two")
    db.add(other)
    db.add(ModelLock(model_id=model.id, user_id=user.id, activity="build"))
    db.flush()
    db.expunge_all()  # a second object with the same key would fail in the identity map first
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(ModelLock(model_id=model.id, user_id=other.id, activity="report"))
        db.flush()


@pytest.mark.parametrize("activity", ["update", "build", "report"])
def test_known_activities_accepted(db, activity):
    from analekh.db.models import ModelLock

    model, user = _model_and_user(db)
    db.add(ModelLock(model_id=model.id, user_id=user.id, activity=activity))
    db.flush()


@pytest.mark.parametrize("activity", ["edit", "UPDATE", ""])
def test_unknown_activity_rejected(db, activity):
    from analekh.db.models import ModelLock

    model, user = _model_and_user(db)
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(ModelLock(model_id=model.id, user_id=user.id, activity=activity))
        db.flush()


def test_lock_needs_existing_model_and_user(db):
    from analekh.db.models import ModelLock

    model, user = _model_and_user(db)
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(ModelLock(model_id=model.id, user_id="no-such-user", activity="update"))
        db.flush()
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(ModelLock(model_id=-1, user_id=user.id, activity="update"))
        db.flush()


def test_deleting_model_removes_its_lock(db):
    from analekh.db.models import ModelLock

    model, user = _model_and_user(db)
    db.add(ModelLock(model_id=model.id, user_id=user.id, activity="update"))
    db.flush()
    db.execute(delete(Model).where(Model.id == model.id))
    db.expunge_all()
    assert db.scalars(select(ModelLock).where(ModelLock.model_id == model.id)).all() == []


def test_deleting_user_removes_their_lock(db):
    from analekh.db.models import ModelLock

    model, user = _model_and_user(db)
    db.add(ModelLock(model_id=model.id, user_id=user.id, activity="update"))
    db.flush()
    db.execute(delete(User).where(User.id == user.id))
    db.expunge_all()
    assert db.scalars(select(ModelLock).where(ModelLock.model_id == model.id)).all() == []


# --- the service: acquire, release, status --------------------------------------------------------


def _lock_row(db: Session, model_id: int):
    from analekh.db.models import ModelLock

    db.expire_all()
    return db.scalars(select(ModelLock).where(ModelLock.model_id == model_id)).one_or_none()


def test_acquire_takes_a_free_model(db, model, analyst):
    lock = acquire(db, model_id=model.id, user_id=analyst.id, activity="update", job_id="job-1")
    assert (lock.model_id, lock.user_id, lock.activity, lock.job_id) == (
        model.id,
        analyst.id,
        "update",
        "job-1",
    )
    assert lock.taken_at.tzinfo is not None
    assert _lock_row(db, model.id) is not None


def test_second_acquire_is_refused(db, model, analyst, analyst2):
    first = acquire(db, model_id=model.id, user_id=analyst.id, activity="update")
    with pytest.raises(LockHeld) as err:
        acquire(db, model_id=model.id, user_id=analyst2.id, activity="build")
    assert err.value.holder_name == analyst.name
    assert err.value.activity == "update"
    assert err.value.taken_at == first.taken_at
    # The refusal leaves the holder's lock as it was.
    row = _lock_row(db, model.id)
    assert (row.user_id, row.activity) == (analyst.id, "update")


def test_same_user_reacquire_is_idempotent(db, model, analyst):
    a = acquire(db, model_id=model.id, user_id=analyst.id, activity="update")
    taken = a.taken_at
    b = acquire(db, model_id=model.id, user_id=analyst.id, activity="update")
    assert b.taken_at == taken
    assert b.last_seen_at > taken  # refreshed on re-entry


def test_same_user_other_activity_keeps_the_existing_lock(db, model, analyst):
    acquire(db, model_id=model.id, user_id=analyst.id, activity="build", job_id="job-b")
    again = acquire(db, model_id=model.id, user_id=analyst.id, activity="report")
    assert (again.activity, again.job_id) == ("build", "job-b")


@pytest.mark.parametrize("activity", ["edit", "UPDATE", ""])
def test_acquire_rejects_unknown_activity(db, model, analyst, activity):
    with pytest.raises(ValueError):
        acquire(db, model_id=model.id, user_id=analyst.id, activity=activity)
    assert _lock_row(db, model.id) is None


def test_release_only_by_holder(db, model, analyst, analyst2):
    acquire(db, model_id=model.id, user_id=analyst.id, activity="report")
    assert release(db, model_id=model.id, user_id=analyst2.id) is False
    assert _lock_row(db, model.id) is not None
    assert release(db, model_id=model.id, user_id=analyst.id) is True
    assert _lock_row(db, model.id) is None


def test_release_of_free_model_is_false(db, model, analyst):
    assert release(db, model_id=model.id, user_id=analyst.id) is False


def test_release_for_job_needs_the_same_job(db, model, analyst):
    acquire(db, model_id=model.id, user_id=analyst.id, activity="build", job_id="job-1")
    assert release_for_job(db, model_id=model.id, job_id="job-2") is False
    assert _lock_row(db, model.id) is not None
    assert release_for_job(db, model_id=model.id, job_id="job-1") is True
    assert _lock_row(db, model.id) is None


def test_release_for_job_ignores_a_lock_without_job(db, model, analyst):
    acquire(db, model_id=model.id, user_id=analyst.id, activity="update")
    assert release_for_job(db, model_id=model.id, job_id="job-1") is False
    assert _lock_row(db, model.id) is not None


def test_model_is_free_again_after_release(db, model, analyst, analyst2):
    acquire(db, model_id=model.id, user_id=analyst.id, activity="update")
    release(db, model_id=model.id, user_id=analyst.id)
    lock = acquire(db, model_id=model.id, user_id=analyst2.id, activity="build")
    assert lock.user_id == analyst2.id


def test_force_release_writes_audit_with_holder(db, model, analyst, admin):
    taken = acquire(db, model_id=model.id, user_id=analyst.id, activity="update").taken_at
    released = force_release(db, model_id=model.id, admin_id=admin.id)
    assert released is not None and released.user_id == analyst.id
    assert _lock_row(db, model.id) is None
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "lock.release")).one()
    assert entry.user_id == admin.id
    assert entry.detail == {
        "model_id": model.id,
        "holder_id": analyst.id,
        "holder_name": analyst.name,
        "taken_at": taken.isoformat(),
    }


def test_force_release_of_free_model_writes_nothing(db, model, admin):
    assert force_release(db, model_id=model.id, admin_id=admin.id) is None
    assert db.scalars(select(AuditEntry).where(AuditEntry.action == "lock.release")).all() == []


def test_status(db, model, analyst):
    assert status(db, model_id=model.id) is None
    acquire(db, model_id=model.id, user_id=analyst.id, activity="report")
    held = status(db, model_id=model.id)
    assert held is not None and (held.user_id, held.activity) == (analyst.id, "report")


def test_lock_goes_with_its_holder(db, model, analyst, analyst2):
    acquire(db, model_id=model.id, user_id=analyst.id, activity="update")
    db.execute(delete(User).where(User.id == analyst.id))
    db.expire_all()
    assert status(db, model_id=model.id) is None
    assert acquire(db, model_id=model.id, user_id=analyst2.id, activity="update")


@pytest.fixture
def committed_model(db_session_factory):
    """A model and two users committed for real, so that two connections can see them."""
    tag = uuid.uuid4().hex[:8]
    with db_session_factory() as s:
        company = Company(nse_symbol=f"RACE{tag}", name=f"Race {tag}", isin=f"INR{tag}")
        s.add(company)
        s.flush()
        workbook = Model(company_id=company.id, name="Race model", origin="built")
        users = [User(id=f"u-race-{tag}-{n}", email=f"race-{tag}-{n}@x.test", name=f"R{n}") for n in (1, 2)]
        s.add_all([workbook, *users])
        s.commit()
        ids = (workbook.id, company.id, [u.id for u in users])
    yield ids
    model_id, company_id, user_ids = ids
    with db_session_factory() as s:
        s.execute(delete(Model).where(Model.id == model_id))
        s.execute(delete(Company).where(Company.id == company_id))
        s.execute(delete(User).where(User.id.in_(user_ids)))
        s.commit()


def test_concurrent_acquire_one_winner(db_session_factory, committed_model):
    model_id, _, user_ids = committed_model
    barrier = threading.Barrier(len(user_ids))
    won: list[str] = []
    refused: list[str] = []
    errors: list[BaseException] = []

    def attempt(user_id: str) -> None:
        with db_session_factory() as s:
            try:
                barrier.wait()
                acquire(s, model_id=model_id, user_id=user_id, activity="update")
                s.commit()
                won.append(user_id)
            except LockHeld:
                s.rollback()
                refused.append(user_id)
            except BaseException as exc:  # noqa: BLE001 - reported below
                errors.append(exc)

    threads = [threading.Thread(target=attempt, args=(uid,)) for uid in user_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert errors == []
    assert len(won) == 1 and len(refused) == 1
