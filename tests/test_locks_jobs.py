"""Per-model locks and queued jobs (model-locks stage 2, task 4): a queued update gives its lock
back when it ends, whether it succeeds, fails or is cancelled, and only the lock it was given.

The task opens its own sessions (session_scope), so these tests work on committed rows in the
test database and remove them afterwards.
"""

from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import sessionmaker

from analekh.db.models import AuditEntry, Company, Model, ModelLock, User
from analekh.jobs import tasks
from analekh.locks import acquire, attach_job, force_release, status

SYMBOL = "JOBLOCKCO"
USERS = ("u-joblock-ana", "u-joblock-ravi", "u-joblock-admin")


@pytest.fixture
def committed(engine, monkeypatch):
    """A company, a model and three users, committed; session_scope points at the test database."""
    import analekh.db.session as session_module

    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(session_module, "_session_factory", lambda: factory)

    def cleanup() -> None:
        with factory.begin() as s:
            ids = list(s.scalars(select(Company.id).where(Company.nse_symbol == SYMBOL)))
            models = list(s.scalars(select(Model.id).where(Model.company_id.in_(ids))))
            s.execute(delete(ModelLock).where(ModelLock.model_id.in_(models)))
            s.execute(delete(Model).where(Model.id.in_(models)))
            s.execute(delete(Company).where(Company.id.in_(ids)))
            s.execute(delete(AuditEntry).where(AuditEntry.user_id.in_(USERS)))
            s.execute(delete(User).where(User.id.in_(USERS)))

    cleanup()
    with factory.begin() as s:
        for uid, role in zip(USERS, ("analyst", "analyst", "admin"), strict=True):
            s.add(User(id=uid, email=f"{uid}@example.com", name=uid, role=role))
        company = Company(nse_symbol=SYMBOL, name="Job Lock Co Limited", isin="INE000J01019")
        s.add(company)
        s.flush()
        workbook = Model(company_id=company.id, name="Job Lock Co model", origin="built")
        s.add(workbook)
        s.flush()
        ids = SimpleNamespace(model=workbook.id, ana=USERS[0], ravi=USERS[1], admin=USERS[2])
    try:
        yield factory, ids
    finally:
        cleanup()


def _lock(factory, model_id: int) -> tuple[str, str | None] | None:
    """The lock as another connection sees it: (holder, job id), or None when free."""
    with factory() as s:
        lock = status(s, model_id=model_id)
        return None if lock is None else (lock.user_id, lock.job_id)


def _queued(factory, model_id: int, user_id: str, job_id: str) -> None:
    """What POST /models/{id}/sync commits before it queues the job."""
    with factory.begin() as s:
        acquire(s, model_id=model_id, user_id=user_id, activity="update", job_id=job_id)
        attach_job(s, model_id=model_id, user_id=user_id, job_id=job_id, activity="update")


def _run(model_id: int, job_id: str, filing_id: int = 1) -> Any:
    """Run the sync task in this process under a job id, as a worker would; errors propagate."""
    return tasks.sync_model.apply(args=(model_id, filing_id), task_id=job_id, throw=True).get()


# --- success and failure ------------------------------------------------------------------------


def test_sync_task_releases_lock_on_success(committed, store, monkeypatch):
    factory, ids = committed
    monkeypatch.setattr(tasks, "default_store", lambda: store)  # CI has no object storage
    _queued(factory, ids.model, ids.ana, "job-ok")
    result = _run(ids.model, "job-ok", filing_id=987654321)  # the real task: no such filing
    assert result == {"error": "model or filing not found"}
    assert _lock(factory, ids.model) is None


def test_sync_task_releases_lock_on_failure_and_reraises(committed, monkeypatch):
    factory, ids = committed
    _queued(factory, ids.model, ids.ana, "job-boom")

    def boom() -> Any:
        raise RuntimeError("object storage is down")

    monkeypatch.setattr(tasks, "default_store", boom)  # the real task fails at its first step
    with pytest.raises(RuntimeError, match="object storage is down"):
        _run(ids.model, "job-boom")
    assert _lock(factory, ids.model) is None


def test_release_commits_although_the_jobs_own_work_rolled_back(committed, monkeypatch):
    """The job wrote to the database (and touched the lock row) then failed: its writes are
    rolled back, the release is still committed, and nothing waits on the job's row lock."""
    factory, ids = committed
    _queued(factory, ids.model, ids.ana, "job-rb")

    def work_then_fail(model_id: int, filing_id: int) -> dict:
        from analekh.db.session import session_scope

        with session_scope() as s:
            s.add(AuditEntry(user_id=ids.ana, action="test.job-work", detail={}))
            s.execute(
                update(ModelLock)
                .where(ModelLock.model_id == model_id)
                .values(last_seen_at=func.clock_timestamp())
            )
            s.flush()
            raise RuntimeError("change set failed")

    monkeypatch.setattr(tasks, "_sync_model", work_then_fail)
    with pytest.raises(RuntimeError, match="change set failed"):
        _run(ids.model, "job-rb")
    assert _lock(factory, ids.model) is None
    with factory() as s:
        n = s.scalar(select(func.count(AuditEntry.id)).where(AuditEntry.action == "test.job-work"))
        assert n == 0


# --- only the job's own lock --------------------------------------------------------------------


def test_older_job_end_leaves_the_newer_jobs_lock(committed, monkeypatch):
    """The holder started a second sync while the first ran: the lock moved to the new job, and
    the first job's end must not free the model under it."""
    factory, ids = committed
    _queued(factory, ids.model, ids.ana, "job-old")

    def newer_sync_meanwhile(model_id: int, filing_id: int) -> dict:
        _queued(factory, model_id, ids.ana, "job-new")
        return {"change_set_id": 1}

    monkeypatch.setattr(tasks, "_sync_model", newer_sync_meanwhile)
    assert _run(ids.model, "job-old") == {"change_set_id": 1}
    assert _lock(factory, ids.model) == (ids.ana, "job-new")


def test_job_end_after_admin_force_release_is_a_no_op(committed, monkeypatch):
    """An admin freed the model mid-job and a colleague took it for their own work: the job's
    end neither fails nor frees the colleague's lock."""
    factory, ids = committed
    _queued(factory, ids.model, ids.ana, "job-forced")

    def admin_frees_then_colleague_takes(model_id: int, filing_id: int) -> dict:
        with factory.begin() as s:
            force_release(s, model_id=model_id, admin_id=ids.admin)
        with factory.begin() as s:
            acquire(s, model_id=model_id, user_id=ids.ravi, activity="report")
        return {"change_set_id": 2}

    monkeypatch.setattr(tasks, "_sync_model", admin_frees_then_colleague_takes)
    assert _run(ids.model, "job-forced") == {"change_set_id": 2}
    assert _lock(factory, ids.model) == (ids.ravi, None)


def test_job_on_a_model_with_no_lock_runs_without_error(committed, monkeypatch):
    factory, ids = committed
    monkeypatch.setattr(tasks, "_sync_model", lambda model_id, filing_id: {"change_set_id": 3})
    assert _run(ids.model, "job-free") == {"change_set_id": 3}
    assert _lock(factory, ids.model) is None


def test_direct_call_without_a_job_id_leaves_locks_alone(committed, monkeypatch):
    """`analekh sync` calls the task in-process with no job id: it has no lock to give back."""
    factory, ids = committed
    with factory.begin() as s:
        acquire(s, model_id=ids.model, user_id=ids.ana, activity="report")
    monkeypatch.setattr(tasks, "_sync_model", lambda model_id, filing_id: {"change_set_id": 4})
    assert tasks.sync_model(ids.model, 1) == {"change_set_id": 4}
    assert _lock(factory, ids.model) == (ids.ana, None)


def test_a_failing_release_does_not_hide_the_jobs_result(committed, monkeypatch, caplog):
    factory, ids = committed
    _queued(factory, ids.model, ids.ana, "job-relfail")

    def broken_release(*a: Any, **k: Any) -> bool:
        raise ConnectionError("database went away")

    monkeypatch.setattr("analekh.locks.release_for_job", broken_release)
    monkeypatch.setattr(tasks, "_sync_model", lambda model_id, filing_id: {"change_set_id": 5})
    assert _run(ids.model, "job-relfail") == {"change_set_id": 5}
    assert "could not release the lock" in caplog.text


# --- cancel ---------------------------------------------------------------------------------------


def test_revoked_sync_job_gives_its_lock_back(committed):
    """A job cancelled before it starts (or killed while running) never reaches its own
    `finally`: the worker's revoke signal gives the lock back instead."""
    factory, ids = committed
    _queued(factory, ids.model, ids.ana, "job-revoked")
    # what the worker sends: the task object as sender, its message as a Context (request.py)
    tasks.release_revoked_sync(
        sender=tasks.sync_model,
        request=_context("job-revoked", tasks.sync_model.name, [ids.model, 1]),
        terminated=False,
        signum=None,
        expired=False,
    )
    assert _lock(factory, ids.model) is None


def test_revoke_through_the_real_signal_gives_the_lock_back(committed):
    from celery.signals import task_revoked

    factory, ids = committed
    _queued(factory, ids.model, ids.ana, "job-signal")
    task_revoked.send(
        sender=tasks.sync_model,
        request=_context("job-signal", tasks.sync_model.name, [ids.model, 1]),
        terminated=True,
        signum=15,
        expired=False,
    )
    assert _lock(factory, ids.model) is None


def test_revoke_of_another_task_or_older_job_changes_nothing(committed):
    factory, ids = committed
    _queued(factory, ids.model, ids.ana, "job-live")
    other = _context("job-live", tasks.backfill.name, [ids.model])
    older = _context("job-gone", tasks.sync_model.name, [ids.model, 1])
    tasks.release_revoked_sync(sender=tasks.backfill, request=other)
    tasks.release_revoked_sync(sender=tasks.sync_model, request=older)
    tasks.release_revoked_sync(sender=tasks.sync_model, request=None)
    assert _lock(factory, ids.model) == (ids.ana, "job-live")


def _context(job_id: str, name: str, args: list[Any]) -> Any:
    from celery.app.task import Context

    return Context({"id": job_id, "task": name, "args": args, "kwargs": {}})
