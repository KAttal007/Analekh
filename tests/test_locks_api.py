"""Per-model locks at the start endpoints (model-locks stage 2, task 3): a colleague's update,
build or report start is refused with 423 while someone else works on the model."""

from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from analekh.api.deps import get_store
from analekh.api.main import app
from analekh.auth.service import create_user
from analekh.builder.coverage import NoHistoryError
from analekh.db.models import (
    Assumption,
    ChangeItem,
    ChangeSet,
    Company,
    ModelLock,
    ModelVersion,
)
from analekh.db.session import get_session
from analekh.locks import acquire, status

GOOD = "Correct-Horse-Battery-9"
CSRF = {"X-Analekh-CSRF": "1"}


@pytest.fixture
def wired(db, store):
    app.dependency_overrides[get_session] = lambda: db
    app.dependency_overrides[get_store] = lambda: store
    yield
    app.dependency_overrides.clear()


def _signed_in(email: str) -> TestClient:
    client = TestClient(app, raise_server_exceptions=False)
    res = client.post("/auth/login", json={"email": email, "password": GOOD})
    assert res.status_code == 200
    return client


@pytest.fixture
def ana_user(db, wired):
    return create_user(db, "ana@firm.in", "Ana", "analyst", GOOD)


@pytest.fixture
def ravi_user(db, wired):
    return create_user(db, "ravi@firm.in", "Ravi", "analyst", GOOD)


@pytest.fixture
def ana(ana_user) -> TestClient:
    return _signed_in("ana@firm.in")


@pytest.fixture
def ravi(ravi_user) -> TestClient:
    return _signed_in("ravi@firm.in")


class FakeTask:
    """Stands in for a Celery task: records what was queued, runs nothing."""

    def __init__(self) -> None:
        self.calls: list[tuple[tuple[Any, ...], str | None]] = []

    def apply_async(self, args: tuple[Any, ...] = (), task_id: str | None = None) -> Any:
        self.calls.append((tuple(args), task_id))
        return SimpleNamespace(id=task_id or "auto", status="PENDING")

    def delay(self, *args: Any) -> Any:
        return self.apply_async(args)


@pytest.fixture
def queue(monkeypatch) -> FakeTask:
    from analekh.jobs import health

    task = FakeTask()
    monkeypatch.setattr("analekh.jobs.tasks.sync_model", task)
    monkeypatch.setattr(health, "queue_available", lambda *a, **k: True)
    return task


def _holder(db, model_id: int) -> tuple[str, str] | None:
    """Who holds the model's lock and why, read now (the row is gone once the work ends)."""
    lock = status(db, model_id=model_id)
    return None if lock is None else (lock.user_id, lock.activity)


def _assert_locked_reply(r, *, holder: str, activity: str) -> None:
    assert r.status_code == 423
    detail = r.json()["detail"]
    assert set(detail) == {"code", "holder_name", "taken_at", "activity"}
    assert detail["code"] == "model_locked"
    assert detail["holder_name"] == holder
    assert detail["activity"] == activity
    datetime.fromisoformat(detail["taken_at"])
    assert "@" not in r.text  # no one's email travels with the refusal


# --- sync (queued: activity "update", the job id is kept on the lock) -----------------------------


def test_sync_refused_when_locked_by_colleague(ana, ravi, model, queue, db):
    first = ana.post(f"/models/{model.id}/sync", json={"filing_id": 1}, headers=CSRF)
    assert first.status_code == 200
    r = ravi.post(f"/models/{model.id}/sync", json={"filing_id": 1}, headers=CSRF)
    _assert_locked_reply(r, holder="Ana", activity="update")
    assert len(queue.calls) == 1  # the refused start queued nothing


def test_sync_records_the_job_on_the_lock(ana, ana_user, model, queue, db):
    r = ana.post(f"/models/{model.id}/sync", json={"filing_id": 7}, headers=CSRF)
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    lock = status(db, model_id=model.id)
    assert lock is not None
    assert (lock.user_id, lock.activity, lock.job_id) == (ana_user.id, "update", job_id)
    assert queue.calls == [((model.id, 7), job_id)]  # the job runs under the id on the lock


def test_holder_can_start_sync_again_and_the_new_job_is_recorded(ana, model, queue, db):
    one = ana.post(f"/models/{model.id}/sync", json={"filing_id": 1}, headers=CSRF)
    two = ana.post(f"/models/{model.id}/sync", json={"filing_id": 2}, headers=CSRF)
    assert one.status_code == two.status_code == 200
    assert one.json()["job_id"] != two.json()["job_id"]
    lock = status(db, model_id=model.id)
    assert lock is not None and lock.job_id == two.json()["job_id"]


def test_sync_lets_go_when_the_queue_is_down(ana, model, monkeypatch, db):
    from analekh.jobs import health

    monkeypatch.setattr("analekh.jobs.tasks.sync_model", FakeTask())
    monkeypatch.setattr(health, "queue_available", lambda *a, **k: False)
    r = ana.post(f"/models/{model.id}/sync", json={"filing_id": 1}, headers=CSRF)
    assert r.status_code == 503
    assert status(db, model_id=model.id) is None


def test_sync_of_unknown_model_is_404_and_takes_no_lock(ana, queue, db):
    r = ana.post("/models/987654321/sync", json={"filing_id": 1}, headers=CSRF)
    assert r.status_code == 404
    assert queue.calls == []


def test_signed_out_request_gets_401_not_423(ana_user, model, queue, db):
    acquire(db, model_id=model.id, user_id=ana_user.id, activity="update")
    anon = TestClient(app, raise_server_exceptions=False)
    r = anon.post(f"/models/{model.id}/sync", json={"filing_id": 1}, headers=CSRF)
    assert r.status_code == 401
    assert queue.calls == []


# --- reports (inline: activity "report", given back when the report is done) ----------------------


@pytest.fixture
def fake_report(monkeypatch):
    """No Claude: run_report returns a grounded text, or calls `hook` first when one is set."""
    seen: dict[str, Any] = {"hook": None}

    class FakeClaude:
        model = "fake-model"

        def __init__(self, *a: Any, **k: Any) -> None:
            pass

    def fake_run_report(*a: Any, **k: Any) -> Any:
        if seen["hook"] is not None:
            seen["hook"]()
        return SimpleNamespace(
            text="Draft.",
            blocked=False,
            tool_calls=[],
            grounding=SimpleNamespace(unmatched=[]),
        )

    monkeypatch.setattr("analekh.genai.client.Claude", FakeClaude)
    monkeypatch.setattr("analekh.genai.reports.run_report", fake_run_report)
    return seen


def _report(client: TestClient, symbol: str = "FIXTCO", model_id: int | None = None):
    body: dict[str, Any] = {"symbol": symbol, "kind": "flash", "period_end": "2026-09-30"}
    if model_id is not None:
        body["model_id"] = model_id
    return client.post("/reports", json=body, headers=CSRF)


def test_report_start_refused_when_locked(ana_user, ravi, model, fake_report, db):
    acquire(db, model_id=model.id, user_id=ana_user.id, activity="update")
    _assert_locked_reply(_report(ravi, model_id=model.id), holder="Ana", activity="update")
    # without a model id the report still reads the company's model
    _assert_locked_reply(_report(ravi), holder="Ana", activity="update")


def test_report_holds_the_lock_while_it_runs_then_lets_go(ravi, ravi_user, model, fake_report, db):
    during: list[Any] = []
    fake_report["hook"] = lambda: during.append(_holder(db, model.id))
    r = _report(ravi, model_id=model.id)
    assert r.status_code == 200
    assert during == [(ravi_user.id, "report")]
    assert status(db, model_id=model.id) is None


def test_report_that_fails_still_lets_go(ravi, model, fake_report, db):
    def boom() -> None:
        raise RuntimeError("the model read failed")

    fake_report["hook"] = boom
    r = _report(ravi, model_id=model.id)
    assert r.status_code == 500
    assert status(db, model_id=model.id) is None


def test_holder_can_run_a_report_and_keeps_the_lock(ana, ana_user, model, fake_report, db):
    acquire(db, model_id=model.id, user_id=ana_user.id, activity="update", job_id="job-1")
    r = _report(ana, model_id=model.id)
    assert r.status_code == 200
    lock = status(db, model_id=model.id)  # the running update's lock is not given away
    assert lock is not None and (lock.activity, lock.job_id) == ("update", "job-1")


def test_report_end_leaves_a_lock_its_holder_handed_to_an_update_job(ravi, ravi_user, model, fake_report, db):
    """Same user, two tabs: a report runs, then a sync takes the lock over for its job. The
    report's end must not free the model under the running update."""
    from analekh.locks import attach_job

    def sync_meanwhile() -> None:  # what POST /models/{id}/sync does to the lock
        acquire(db, model_id=model.id, user_id=ravi_user.id, activity="update", job_id="job-9")
        attach_job(db, model_id=model.id, user_id=ravi_user.id, job_id="job-9", activity="update")

    fake_report["hook"] = sync_meanwhile
    assert _report(ravi, model_id=model.id).status_code == 200
    lock = status(db, model_id=model.id)
    assert lock is not None
    assert (lock.user_id, lock.activity, lock.job_id) == (ravi_user.id, "update", "job-9")


def test_report_on_a_company_without_a_model_takes_no_lock(ravi, fake_report, db):
    db.add(Company(nse_symbol="NOMODCO", name="No Model Co Limited", isin="INE000N01019"))
    db.flush()
    counts: list[int] = []
    fake_report["hook"] = lambda: counts.append(db.scalar(select(func.count(ModelLock.model_id))))
    r = _report(ravi, symbol="NOMODCO")
    assert r.status_code == 200
    assert counts == [0]


# --- build (inline: activity "build") -------------------------------------------------------------


@pytest.fixture
def no_templates(monkeypatch):
    """Skip the template machinery: the build itself is replaced in each test."""
    import analekh.api.routers.models as models_router

    monkeypatch.setattr(models_router, "default_for", lambda *a, **k: SimpleNamespace(status="active"))
    return models_router


def test_build_refused_when_locked(ana_user, ravi, model, no_templates, monkeypatch, db):
    started: list[bool] = []
    monkeypatch.setattr(no_templates, "start_coverage", lambda *a, **k: started.append(True))
    acquire(db, model_id=model.id, user_id=ana_user.id, activity="update")
    r = ravi.post("/coverage", json={"symbol": "FIXTCO"}, headers=CSRF)
    _assert_locked_reply(r, holder="Ana", activity="update")
    assert started == []


def test_build_holds_the_company_model_then_lets_go_on_failure(ravi, ravi_user, model, no_templates, monkeypatch, db):
    during: list[Any] = []

    def fake_start(*a: Any, **k: Any) -> Any:
        during.append(_holder(db, model.id))
        raise NoHistoryError("no quarterly results stored for FIXTCO")

    monkeypatch.setattr(no_templates, "start_coverage", fake_start)
    r = ravi.post("/coverage", json={"symbol": "FIXTCO"}, headers=CSRF)
    assert r.status_code == 409
    assert during == [(ravi_user.id, "build")]
    assert status(db, model_id=model.id) is None


def test_finalize_refused_when_locked(ana_user, ravi, model, monkeypatch, db):
    import analekh.api.routers.models as models_router

    ran: list[bool] = []
    monkeypatch.setattr(models_router, "finalize_build", lambda *a, **k: ran.append(True))
    acquire(db, model_id=model.id, user_id=ana_user.id, activity="report")
    r = ravi.post(f"/models/{model.id}/finalize", headers=CSRF)
    _assert_locked_reply(r, holder="Ana", activity="report")
    assert ran == []


def test_finalize_holds_the_lock_while_it_runs(ravi, ravi_user, model, monkeypatch, db):
    import analekh.api.routers.models as models_router

    during: list[Any] = []

    def fake_finalize(*a: Any, **k: Any) -> Any:
        during.append(_holder(db, model.id))
        return SimpleNamespace(
            build=SimpleNamespace(status="built"),
            checks=SimpleNamespace(as_dict=lambda: {"passed": True}),
            version=SimpleNamespace(version=1),
        )

    monkeypatch.setattr(models_router, "finalize_build", fake_finalize)
    r = ravi.post(f"/models/{model.id}/finalize", headers=CSRF)
    assert r.status_code == 200 and r.json()["version"] == 1
    assert during == [(ravi_user.id, "build")]
    assert status(db, model_id=model.id) is None


def test_assumption_decisions_refused_when_locked(ana_user, ravi, model, db):
    acquire(db, model_id=model.id, user_id=ana_user.id, activity="update")
    r = ravi.post(f"/models/{model.id}/assumptions/decisions", json={"accept_all": True}, headers=CSRF)
    _assert_locked_reply(r, holder="Ana", activity="update")


def test_assumption_decisions_let_go_after(ravi, model, db):
    r = ravi.post(f"/models/{model.id}/assumptions/decisions", json={"accept_all": True}, headers=CSRF)
    assert r.status_code == 200
    assert status(db, model_id=model.id) is None


def test_assumption_decision_on_an_already_decided_row_is_refused(ravi, model, db):
    """A stale page (rows shown pending after a colleague decided them) cannot overwrite."""
    row = Assumption(
        model_id=model.id,
        driver="growth",
        proposed_value=Decimal("0.15"),
        decision="edited",
        final_value=Decimal("0.12"),
    )
    db.add(row)
    db.flush()
    r = ravi.post(
        f"/models/{model.id}/assumptions/decisions",
        json={"decisions": [{"id": row.id, "decision": "accepted"}], "accept_all": False},
        headers=CSRF,
    )
    assert r.status_code == 409
    db.refresh(row)
    assert (row.decision, row.final_value) == ("edited", Decimal("0.12"))


# --- change sets (the write step of an update: activity "update") ------------------------------


@pytest.fixture
def change_set(model, db) -> ChangeSet:
    cs = ChangeSet(model_id=model.id, base_version=1, status="proposed")
    db.add(cs)
    db.flush()
    db.add(ChangeItem(change_set_id=cs.id, kind="actual_write", sheet="Data", cell="J3", new_value="9"))
    db.flush()
    db.refresh(cs)
    return cs


def _pending_item(cs: ChangeSet) -> int:
    return cs.items[0].id


def test_change_set_decisions_refused_when_locked(ana_user, ravi, model, change_set, db):
    acquire(db, model_id=model.id, user_id=ana_user.id, activity="build")
    r = ravi.post(
        f"/change-sets/{change_set.id}/decisions",
        json={"decisions": [], "accept_kinds": ["actual_write"]},
        headers=CSRF,
    )
    _assert_locked_reply(r, holder="Ana", activity="build")
    db.refresh(change_set.items[0])
    assert change_set.items[0].decision == "pending"


def test_change_set_decisions_by_the_holder_keep_the_lock(ana, ana_user, model, change_set, db):
    acquire(db, model_id=model.id, user_id=ana_user.id, activity="update")
    r = ana.post(
        f"/change-sets/{change_set.id}/decisions",
        json={"decisions": [], "accept_kinds": ["actual_write"]},
        headers=CSRF,
    )
    assert r.status_code == 200 and r.json()["status"] == "approved"
    assert _holder(db, model.id) == (ana_user.id, "update")


def test_change_set_decisions_on_a_free_model_let_go_after(ravi, model, change_set, db):
    r = ravi.post(
        f"/change-sets/{change_set.id}/decisions",
        json={"decisions": [{"item_id": _pending_item(change_set), "decision": "skipped"}]},
        headers=CSRF,
    )
    assert r.status_code == 200
    assert status(db, model_id=model.id) is None


def test_change_set_decision_on_an_already_decided_item_is_refused(ravi, change_set, db):
    item = change_set.items[0]
    item.decision, item.final_value = "edited", "7"
    db.flush()
    r = ravi.post(
        f"/change-sets/{change_set.id}/decisions",
        json={"decisions": [{"item_id": item.id, "decision": "accepted"}]},
        headers=CSRF,
    )
    assert r.status_code == 409
    db.refresh(item)
    assert (item.decision, item.final_value) == ("edited", "7")


def test_change_set_apply_refused_when_locked(ana_user, ravi, model, change_set, db):
    change_set.status = "approved"
    db.flush()
    acquire(db, model_id=model.id, user_id=ana_user.id, activity="build")
    r = ravi.post(f"/change-sets/{change_set.id}/apply", headers=CSRF)
    _assert_locked_reply(r, holder="Ana", activity="build")
    count = db.scalar(select(func.count()).select_from(ModelVersion))
    assert count == 0
    db.refresh(change_set)
    assert change_set.status == "approved"


def test_change_set_apply_holds_the_lock_while_it_runs(ravi, ravi_user, model, change_set, store, monkeypatch, db):
    import analekh.api.routers.change_sets as cs_router

    store.put("models/base.xlsx", b"base", "application/octet-stream")
    db.add(ModelVersion(model_id=model.id, version=1, storage_key="models/base.xlsx"))
    item = change_set.items[0]
    item.decision, item.final_value = "accepted", "9"
    change_set.status = "approved"
    db.flush()
    during: list[Any] = []

    def fake_apply(data: bytes, approved: Any) -> bytes:
        during.append(_holder(db, model.id))
        return b"written"

    monkeypatch.setattr(cs_router, "apply_headless", fake_apply)
    monkeypatch.setattr(cs_router, "recalc_file", lambda b, reference=None: b)
    monkeypatch.setattr(cs_router, "load", lambda b: None)
    monkeypatch.setattr(cs_router, "fingerprint", lambda wb: "fp")
    r = ravi.post(f"/change-sets/{change_set.id}/apply", headers=CSRF)
    assert r.status_code == 200 and r.json()["version"] == 2
    assert during == [(ravi_user.id, "update")]
    assert status(db, model_id=model.id) is None


def _approve_on_versions(db, store, model, change_set, *, versions: int, base: int) -> None:
    """Give the model `versions` saved versions and approve the change set drafted on `base`."""
    for v in range(1, versions + 1):
        store.put(f"models/v{v}.xlsx", b"base", "application/octet-stream")
        db.add(ModelVersion(model_id=model.id, version=v, storage_key=f"models/v{v}.xlsx"))
    item = change_set.items[0]
    item.decision, item.final_value = "accepted", "9"
    change_set.base_version, change_set.status = base, "approved"
    db.flush()


def _fake_headless(monkeypatch) -> None:
    import analekh.api.routers.change_sets as cs_router

    monkeypatch.setattr(cs_router, "apply_headless", lambda data, approved: b"written")
    monkeypatch.setattr(cs_router, "recalc_file", lambda b, reference=None: b)
    monkeypatch.setattr(cs_router, "load", lambda b: None)
    monkeypatch.setattr(cs_router, "fingerprint", lambda wb: "fp")


def test_change_set_apply_on_a_stale_base_is_refused(ravi, model, change_set, store, monkeypatch, db):
    """Drafted on v1, then a build or another change set saved v2: applying it would derive v3
    from v1 and drop v2's work, so it is refused and nothing is written."""
    _approve_on_versions(db, store, model, change_set, versions=2, base=1)
    _fake_headless(monkeypatch)
    r = ravi.post(f"/change-sets/{change_set.id}/apply", headers=CSRF)
    assert r.status_code == 409
    assert r.json()["detail"] == {
        "code": "change_set_stale",
        "message": "The model has changed since this change set was drafted. Draft a new update.",
        "base_version": 1,
        "latest_version": 2,
    }
    count = db.scalar(select(func.count()).select_from(ModelVersion).where(ModelVersion.model_id == model.id))
    assert count == 2
    db.refresh(change_set)
    assert change_set.status == "approved"
    assert status(db, model_id=model.id) is None


def test_change_set_apply_on_the_latest_base_still_applies(ravi, model, change_set, store, monkeypatch, db):
    _approve_on_versions(db, store, model, change_set, versions=2, base=2)
    _fake_headless(monkeypatch)
    r = ravi.post(f"/change-sets/{change_set.id}/apply", headers=CSRF)
    assert r.status_code == 200 and r.json()["version"] == 3
    db.refresh(change_set)
    assert change_set.status == "applied"
    assert status(db, model_id=model.id) is None


def test_apply_recalc_unavailable_is_503_and_saves_nothing(ravi, model, change_set, store, monkeypatch, db):
    """The recalc service is down: no version is saved (its cached values would be stale), the
    lock is released and the change set stays approved, so Apply can be clicked again."""
    import analekh.api.routers.change_sets as cs_router
    from analekh.workbook.recalc import RecalcUnavailable

    _approve_on_versions(db, store, model, change_set, versions=1, base=1)
    _fake_headless(monkeypatch)

    def down(workbook: bytes, reference: bytes | None = None) -> bytes:
        raise RecalcUnavailable("recalc service unavailable: ConnectError")

    monkeypatch.setattr(cs_router, "recalc_file", down)
    puts: list[str] = []
    real_put = store.put
    monkeypatch.setattr(store, "put", lambda key, *a, **kw: (puts.append(key), real_put(key, *a, **kw))[1])
    r = ravi.post(f"/change-sets/{change_set.id}/apply", headers=CSRF)
    assert r.status_code == 503
    assert r.json()["detail"] == {
        "code": "recalc_unavailable",
        "message": "Recalculation is unavailable right now. Try Apply again in a few minutes, or apply from Excel with the Analekh bridge.",
    }
    assert puts == []  # store.put was never called
    versions = db.scalar(select(func.count()).select_from(ModelVersion).where(ModelVersion.model_id == model.id))
    assert versions == 1  # no new model_versions row
    db.refresh(change_set)
    assert change_set.status == "approved"
    assert status(db, model_id=model.id) is None  # no model_locks row left behind


def test_apply_cannot_compute_is_422_lists_cells_and_saves_nothing(ravi, model, change_set, store, monkeypatch, db):
    """The model uses a function LibreOffice cannot run (a VBA UDF): 422 naming the cells, no
    version saved, the lock released and the change set still approved."""
    import analekh.api.routers.change_sets as cs_router
    from analekh.workbook.recalc import RecalcCannotCompute

    _approve_on_versions(db, store, model, change_set, versions=1, base=1)
    _fake_headless(monkeypatch)
    cells = [f"Sheet1!E{n}" for n in range(2, 14)]  # 12 cells: the reply names only the first 10

    def cannot(workbook: bytes, reference: bytes | None = None) -> bytes:
        raise RecalcCannotCompute(cells)

    monkeypatch.setattr(cs_router, "recalc_file", cannot)
    puts: list[str] = []
    real_put = store.put
    monkeypatch.setattr(store, "put", lambda key, *a, **kw: (puts.append(key), real_put(key, *a, **kw))[1])
    r = ravi.post(f"/change-sets/{change_set.id}/apply", headers=CSRF)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["code"] == "recalc_cannot_compute"
    assert detail["cells"] == cells[:10]
    assert detail["total"] == 12
    assert "Sheet1!E2" in detail["message"] and "and more" in detail["message"]
    assert "Excel with the Analekh bridge" in detail["message"]
    assert puts == []
    versions = db.scalar(select(func.count()).select_from(ModelVersion).where(ModelVersion.model_id == model.id))
    assert versions == 1
    db.refresh(change_set)
    assert change_set.status == "approved"
    assert status(db, model_id=model.id) is None


# --- the real request session (commit at the end, roll back on error) ----------------------------


@pytest.fixture
def real_session(engine, store, monkeypatch):
    """The API's own get_session/session_scope on the test database, not the test's rolled-back
    session: what is committed here is real, so the fixture removes it afterwards."""
    from sqlalchemy import delete
    from sqlalchemy.orm import sessionmaker

    import analekh.db.session as session_module
    from analekh.db.models import AuditEntry, Model, Report

    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(session_module, "_session_factory", lambda: factory)
    app.dependency_overrides[get_store] = lambda: store
    with factory.begin() as s:
        s.execute(delete(Company).where(Company.nse_symbol == "REALCO"))
        create_user(s, "reala@firm.in", "Real Ana", "analyst", GOOD)
        create_user(s, "realb@firm.in", "Real Ravi", "analyst", GOOD)
        company = Company(nse_symbol="REALCO", name="Real Co Limited", isin="INE000R01011")
        s.add(company)
        s.flush()
        workbook = Model(company_id=company.id, name="Real Co model", origin="built")
        s.add(workbook)
        s.flush()
        ids = SimpleNamespace(model=workbook.id, company=company.id)
    try:
        yield factory, ids
    finally:
        app.dependency_overrides.clear()
        from analekh.db.models import User

        with factory.begin() as s:
            s.execute(delete(ModelLock).where(ModelLock.model_id == ids.model))
            s.execute(delete(Report).where(Report.company_id == ids.company))
            s.execute(delete(Model).where(Model.id == ids.model))
            s.execute(delete(Company).where(Company.id == ids.company))
            users = list(s.scalars(select(User.id).where(User.email.in_(["reala@firm.in", "realb@firm.in"]))))
            s.execute(delete(AuditEntry).where(AuditEntry.user_id.in_(users)))
            s.execute(delete(User).where(User.id.in_(users)))


def _seen_from_another_session(factory, model_id: int) -> tuple[str, str, str | None] | None:
    with factory() as other:
        lock = status(other, model_id=model_id)
        return None if lock is None else (lock.activity, lock.user_id, lock.job_id)


def test_real_session_report_lock_is_visible_to_others_then_gone(real_session, fake_report):
    factory, ids = real_session
    during: list[Any] = []
    fake_report["hook"] = lambda: during.append(_seen_from_another_session(factory, ids.model))
    ana = _signed_in("reala@firm.in")
    assert _report(ana, symbol="REALCO", model_id=ids.model).status_code == 200
    assert during[0] is not None and during[0][0] == "report"  # committed while the work ran
    assert _seen_from_another_session(factory, ids.model) is None


def test_real_session_failed_report_commits_only_the_release(real_session, fake_report):
    from analekh.db.models import Report

    factory, ids = real_session

    def boom() -> None:
        raise RuntimeError("the model read failed")

    fake_report["hook"] = boom
    ana = _signed_in("reala@firm.in")
    assert _report(ana, symbol="REALCO", model_id=ids.model).status_code == 500
    assert _seen_from_another_session(factory, ids.model) is None
    with factory() as other:
        assert other.scalar(select(func.count(Report.id)).where(Report.company_id == ids.company)) == 0


def test_real_session_colleague_refused_and_sync_lock_survives_the_request(real_session, fake_report, queue):
    factory, ids = real_session
    ana = _signed_in("reala@firm.in")
    ravi = _signed_in("realb@firm.in")
    r = ana.post(f"/models/{ids.model}/sync", json={"filing_id": 1}, headers=CSRF)
    assert r.status_code == 200
    seen = _seen_from_another_session(factory, ids.model)
    assert seen is not None and seen[0] == "update" and seen[2] == r.json()["job_id"]
    _assert_locked_reply(_report(ravi, symbol="REALCO", model_id=ids.model), holder="Real Ana", activity="update")
    seen_after = _seen_from_another_session(factory, ids.model)
    assert seen_after == seen  # the refusal's rollback left the holder's lock alone


@pytest.fixture
def real_change_set(real_session, store, monkeypatch):
    """An approved change set on the real session's model, plus a `holding` that lets a colleague
    commit `status` from another session after the request loaded the set, before the lock."""
    from sqlalchemy import delete, update

    import analekh.api.routers.change_sets as cs_router

    factory, ids = real_session
    store.put("models/real-base.xlsx", b"base", "application/octet-stream")
    with factory.begin() as s:
        s.add(ModelVersion(model_id=ids.model, version=1, storage_key="models/real-base.xlsx"))
        cs = ChangeSet(model_id=ids.model, base_version=1, status="approved")
        s.add(cs)
        s.flush()
        s.add(
            ChangeItem(
                change_set_id=cs.id,
                kind="actual_write",
                sheet="Data",
                cell="J3",
                new_value="9",
                decision="accepted",
                final_value="9",
            )
        )
        cs_id = cs.id
    real_holding = cs_router.holding
    meanwhile: dict[str, str | None] = {"status": None}

    @contextmanager
    def racing_holding(session, **kw):
        if meanwhile["status"] is not None:
            with factory.begin() as other:
                other.execute(update(ChangeSet).where(ChangeSet.id == cs_id).values(status=meanwhile["status"]))
        with real_holding(session, **kw):
            yield

    monkeypatch.setattr(cs_router, "holding", racing_holding)
    monkeypatch.setattr(cs_router, "apply_headless", lambda data, approved: b"written")
    monkeypatch.setattr(cs_router, "recalc_file", lambda b, reference=None: b)
    monkeypatch.setattr(cs_router, "load", lambda b: None)
    monkeypatch.setattr(cs_router, "fingerprint", lambda wb: "fp")
    try:
        yield factory, ids, cs_id, meanwhile
    finally:
        with factory.begin() as s:
            s.execute(delete(ChangeItem).where(ChangeItem.change_set_id == cs_id))
            s.execute(delete(ChangeSet).where(ChangeSet.id == cs_id))
            s.execute(delete(ModelVersion).where(ModelVersion.model_id == ids.model))


def _versions(factory, model_id: int) -> int:
    with factory() as other:
        return other.scalar(select(func.count()).select_from(ModelVersion).where(ModelVersion.model_id == model_id))


def test_real_session_second_apply_after_a_concurrent_one_is_refused(real_change_set):
    """The set was loaded as approved, then a colleague's apply finished before the lock was
    taken: the status read before the lock is stale and must not let a second apply through."""
    factory, ids, cs_id, meanwhile = real_change_set
    meanwhile["status"] = "applied"
    ana = _signed_in("reala@firm.in")
    r = ana.post(f"/change-sets/{cs_id}/apply", headers=CSRF)
    assert r.status_code == 409
    assert _versions(factory, ids.model) == 1  # no second model_versions row
    assert _seen_from_another_session(factory, ids.model) is None


def test_real_session_decision_after_a_concurrent_apply_is_refused(real_change_set):
    factory, ids, cs_id, meanwhile = real_change_set
    meanwhile["status"] = "applied"
    ana = _signed_in("reala@firm.in")
    r = ana.post(f"/change-sets/{cs_id}/decisions", json={"decisions": []}, headers=CSRF)
    assert r.status_code == 409
    with factory() as other:
        assert other.get(ChangeSet, cs_id).status == "applied"


# --- service helper -------------------------------------------------------------------------------


def test_attach_job_moves_the_holders_lock_to_the_new_job(db, analyst, analyst2, model):
    from analekh.locks import attach_job

    acquire(db, model_id=model.id, user_id=analyst.id, activity="report", job_id="job-1")
    again = acquire(db, model_id=model.id, user_id=analyst.id, activity="update", job_id="job-2")
    assert again.job_id == "job-1"  # a re-acquire keeps the old job
    assert attach_job(db, model_id=model.id, user_id=analyst.id, job_id="job-2", activity="update")
    lock = status(db, model_id=model.id)
    assert lock is not None and (lock.job_id, lock.activity) == ("job-2", "update")
    # only the holder can
    assert not attach_job(db, model_id=model.id, user_id=analyst2.id, job_id="job-3", activity="update")
    lock = status(db, model_id=model.id)
    assert lock is not None and lock.job_id == "job-2"


# --- lock API: status, holder release, my locks, admin release (task 5) ---------------------------


@pytest.fixture
def boss_user(db, wired):
    return create_user(db, "boss@firm.in", "Boss", "admin", GOOD)


@pytest.fixture
def boss(boss_user) -> TestClient:
    return _signed_in("boss@firm.in")


@pytest.fixture
def model2(db, model):
    from analekh.db.models import Model

    workbook = Model(company_id=model.company_id, name="Fixture Co model 2", origin="built")
    db.add(workbook)
    db.flush()
    return workbook


UNKNOWN = 987654321


def test_status_shows_holder_name_to_colleague(ana_user, ravi, model, db):
    acquire(db, model_id=model.id, user_id=ana_user.id, activity="update")
    r = ravi.get(f"/models/{model.id}/lock")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {
        "model_id",
        "holder_id",
        "holder_name",
        "activity",
        "taken_at",
        "mine",
        "job_running",
    }
    assert body["model_id"] == model.id
    assert body["holder_id"] == ana_user.id
    assert body["holder_name"] == "Ana"
    assert body["activity"] == "update"
    assert body["mine"] is False
    assert body["job_running"] is False  # no job id on this lock
    datetime.fromisoformat(body["taken_at"])
    assert "@" not in r.text  # the holder's email never travels


def test_status_mine_for_holder_not_for_admin(ana, ana_user, boss, model, db):
    acquire(db, model_id=model.id, user_id=ana_user.id, activity="report")
    assert ana.get(f"/models/{model.id}/lock").json()["mine"] is True
    seen_by_admin = boss.get(f"/models/{model.id}/lock").json()
    assert seen_by_admin["mine"] is False and seen_by_admin["holder_name"] == "Ana"


def test_status_of_free_model_is_null(ravi, model):
    r = ravi.get(f"/models/{model.id}/lock")
    assert r.status_code == 200
    assert r.json() is None


def test_status_of_unknown_model_is_404(ravi):
    assert ravi.get(f"/models/{UNKNOWN}/lock").status_code == 404


def test_holder_releases_own_lock(ana, ana_user, model, db):
    acquire(db, model_id=model.id, user_id=ana_user.id, activity="update")
    r = ana.post(f"/models/{model.id}/lock/release", headers=CSRF)
    assert r.status_code == 204
    assert status(db, model_id=model.id) is None


def test_holder_may_release_a_lock_attached_to_a_running_job(ana, ana_user, model, db):
    from analekh.locks import release_for_job

    acquire(db, model_id=model.id, user_id=ana_user.id, activity="update", job_id="job-1")
    assert ana.post(f"/models/{model.id}/lock/release", headers=CSRF).status_code == 204
    assert status(db, model_id=model.id) is None
    assert release_for_job(db, model_id=model.id, job_id="job-1") is False  # the job's end: no-op


def test_non_holder_cannot_release(ana_user, ravi, model, db):
    acquire(db, model_id=model.id, user_id=ana_user.id, activity="update")
    r = ravi.post(f"/models/{model.id}/lock/release", headers=CSRF)
    assert r.status_code == 403
    lock = status(db, model_id=model.id)
    assert lock is not None and lock.user_id == ana_user.id


def test_admin_cannot_use_the_holder_route_on_a_colleagues_lock(ana_user, boss, model, db):
    acquire(db, model_id=model.id, user_id=ana_user.id, activity="update")
    assert boss.post(f"/models/{model.id}/lock/release", headers=CSRF).status_code == 403
    assert status(db, model_id=model.id) is not None


def test_holder_release_on_free_model_is_204(ana, model, db):
    assert ana.post(f"/models/{model.id}/lock/release", headers=CSRF).status_code == 204
    assert status(db, model_id=model.id) is None


def test_holder_release_on_unknown_model_is_404(ana):
    assert ana.post(f"/models/{UNKNOWN}/lock/release", headers=CSRF).status_code == 404


def test_admin_release_names_holder_in_audit(ana_user, boss, boss_user, model, db):
    from analekh.db.models import AuditEntry

    acquire(db, model_id=model.id, user_id=ana_user.id, activity="update", job_id="job-1")
    r = boss.post(f"/admin/locks/{model.id}/release", headers=CSRF)
    assert r.status_code == 204
    assert status(db, model_id=model.id) is None
    entries = list(db.scalars(select(AuditEntry).where(AuditEntry.action == "lock.release", AuditEntry.user_id == boss_user.id)))
    assert len(entries) == 1
    assert entries[0].detail["holder_id"] == ana_user.id
    assert entries[0].detail["model_id"] == model.id


def test_admin_release_refused_for_non_admin(ana_user, ravi, model, db):
    acquire(db, model_id=model.id, user_id=ana_user.id, activity="update")
    assert ravi.post(f"/admin/locks/{model.id}/release", headers=CSRF).status_code == 403
    assert status(db, model_id=model.id) is not None


def test_admin_release_refused_for_the_holder_too(ana, ana_user, model, db):
    acquire(db, model_id=model.id, user_id=ana_user.id, activity="update")
    assert ana.post(f"/admin/locks/{model.id}/release", headers=CSRF).status_code == 403


def test_admin_release_on_free_model_is_204_and_audits_nothing(boss, boss_user, model, db):
    from analekh.db.models import AuditEntry

    assert boss.post(f"/admin/locks/{model.id}/release", headers=CSRF).status_code == 204
    count = db.scalar(select(func.count(AuditEntry.id)).where(AuditEntry.action == "lock.release", AuditEntry.user_id == boss_user.id))
    assert count == 0


def test_admin_release_on_unknown_model_is_404(boss):
    assert boss.post(f"/admin/locks/{UNKNOWN}/release", headers=CSRF).status_code == 404


# --- admin lock list (task 9) ---------------------------------------------------------------------


def test_admin_lock_list_requires_admin(ana, ana_user, boss, model, db):
    acquire(db, model_id=model.id, user_id=ana_user.id, activity="update")
    assert ana.get("/admin/locks").status_code == 403
    assert boss.get("/admin/locks").status_code == 200


def test_admin_lock_list_shows_everyones_locks_with_names(ana_user, ravi_user, boss, model, model2, db):
    acquire(db, model_id=model.id, user_id=ana_user.id, activity="update", job_id="job-1")
    acquire(db, model_id=model2.id, user_id=ravi_user.id, activity="report")
    r = boss.get("/admin/locks")
    assert r.status_code == 200
    body = r.json()
    assert [(x["model_id"], x["holder_name"], x["activity"], x["job_running"], x["mine"]) for x in body] == [(model.id, "Ana", "update", True, False), (model2.id, "Ravi", "report", False, False)]
    first = body[0]
    assert first["holder_id"] == ana_user.id
    assert first["model_name"] == "Fixture Co model"
    assert first["company_symbol"] == "FIXTCO"
    assert first["company_name"] == "Fixture Co Limited"
    assert body[1]["model_name"] == "Fixture Co model 2"
    datetime.fromisoformat(first["taken_at"])
    assert "@" not in r.text  # holders are named, never emailed


def test_admin_lock_list_marks_the_admins_own_lock(boss, boss_user, model, db):
    acquire(db, model_id=model.id, user_id=boss_user.id, activity="build")
    body = boss.get("/admin/locks").json()
    assert [(x["holder_name"], x["mine"]) for x in body] == [("Boss", True)]


def test_admin_lock_list_empty(boss, model):
    r = boss.get("/admin/locks")
    assert r.status_code == 200 and r.json() == []


def test_me_locks_lists_only_mine(ana, ana_user, ravi, ravi_user, model, model2, db):
    acquire(db, model_id=model.id, user_id=ana_user.id, activity="update")
    acquire(db, model_id=model2.id, user_id=ravi_user.id, activity="report")
    mine = ana.get("/me/locks")
    assert mine.status_code == 200
    body = mine.json()
    assert [(x["model_id"], x["holder_name"], x["mine"]) for x in body] == [(model.id, "Ana", True)]
    assert "@" not in mine.text
    theirs = ravi.get("/me/locks").json()
    assert [x["model_id"] for x in theirs] == [model2.id]


def test_me_locks_empty(ravi):
    r = ravi.get("/me/locks")
    assert r.status_code == 200 and r.json() == []


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/models/{id}/lock"),
        ("post", "/models/{id}/lock/release"),
        ("get", "/me/locks"),
        ("post", "/admin/locks/{id}/release"),
        ("get", "/admin/locks"),
    ],
)
def test_lock_routes_need_sign_in(ana_user, model, db, method, path):
    acquire(db, model_id=model.id, user_id=ana_user.id, activity="update")
    anon = TestClient(app, raise_server_exceptions=False)
    r = getattr(anon, method)(path.format(id=model.id), headers=CSRF)
    assert r.status_code == 401
    assert status(db, model_id=model.id) is not None


def test_me_locks_says_whether_a_job_is_running(ana, ana_user, model, model2, db):
    """The idle reminder stays quiet while one of the user's updates is still running."""
    acquire(db, model_id=model.id, user_id=ana_user.id, activity="update", job_id="job-1")
    acquire(db, model_id=model2.id, user_id=ana_user.id, activity="report")
    body = ana.get("/me/locks").json()
    assert {x["model_id"]: x["job_running"] for x in body} == {model.id: True, model2.id: False}


def test_idle_reminder_minutes_defaults_to_30_and_is_exposed(ana):
    """The web reminds an idle holder after this long; it reads the figure, never hard-codes it."""
    from analekh.config import get_settings

    assert get_settings().idle_reminder_minutes == 30
    res = ana.get("/settings/upload-limit")
    assert res.status_code == 200
    assert res.json()["idle_reminder_minutes"] == get_settings().idle_reminder_minutes
