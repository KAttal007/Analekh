"""Report thread routes and jobs: one writer at a time, owner checks, approval (design: report chat)."""

import json
from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from analekh.api.deps import get_store
from analekh.api.main import app
from analekh.auth.service import create_user
from analekh.config import get_settings
from analekh.db.models import Company, ReportThread, ThreadMessage
from analekh.db.session import get_session
from analekh.genai.tools import ToolExecutor
from analekh.reports.chat import Selection
from analekh.reports.draft import parse_draft
from analekh.reports.jobs import FAILED_REPLY, NOT_DRAFTED, RATING_UNIT, do_chat_turn, do_first_draft
from analekh.reports.ooxml import OLE_MAGIC as OLE
from analekh.reports.store import load_draft, save_version

GOOD = "Correct-Horse-Battery-9"
CSRF = {"X-Analekh-CSRF": "1"}


@pytest.fixture
def wired(db, store):
    app.dependency_overrides[get_session] = lambda: db
    app.dependency_overrides[get_store] = lambda: store
    yield
    app.dependency_overrides.clear()


def _client(email: str) -> TestClient:
    client = TestClient(app, raise_server_exceptions=False)
    assert client.post("/auth/login", json={"email": email, "password": GOOD}).status_code == 200
    return client


@pytest.fixture
def ana_user(db, wired):
    return create_user(db, "ana@firm.in", "Ana", "analyst", GOOD)


@pytest.fixture
def ravi_user(db, wired):
    return create_user(db, "ravi@firm.in", "Ravi", "analyst", GOOD)


@pytest.fixture
def ana(ana_user) -> TestClient:
    return _client("ana@firm.in")


@pytest.fixture
def ravi(ravi_user) -> TestClient:
    return _client("ravi@firm.in")


class FakeTask:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[Any, ...], str | None]] = []

    def apply_async(self, args: tuple[Any, ...] = (), task_id: str | None = None) -> Any:
        self.calls.append((tuple(args), task_id))
        return SimpleNamespace(id=task_id or "auto", status="PENDING")

    def delay(self, *args: Any) -> Any:
        return self.apply_async(args)


@pytest.fixture
def queue(monkeypatch) -> dict[str, FakeTask]:
    from analekh.jobs import health

    tasks = {"first": FakeTask(), "turn": FakeTask(), "learn": FakeTask()}
    monkeypatch.setattr("analekh.jobs.report_tasks.learn_from_publish", tasks["learn"])
    monkeypatch.setattr("analekh.jobs.report_tasks.generate_first_draft", tasks["first"])
    monkeypatch.setattr("analekh.jobs.report_tasks.run_chat_turn", tasks["turn"])
    monkeypatch.setattr(health, "queue_available", lambda *a, **k: True)
    return tasks


@pytest.fixture
def company(db) -> Company:
    co = Company(nse_symbol="APICO", name="Api Co Limited", isin="INE000A01011")
    db.add(co)
    db.flush()
    return co


def _start(client: TestClient, **over) -> Any:
    body = {"symbol": "APICO", "report_type": "quarterly", "format": "word", "basis": "standalone", "quarter_end": "2026-09-30", **over}
    return client.post("/threads", json=body, headers=CSRF)


def _draft(*bodies: str) -> dict:
    return {
        "schema_version": 1,
        "format": "word",
        "units": [{"title": f"Section {i}", "blocks": [{"type": "paragraph", "text": b}]} for i, b in enumerate(bodies)],
    }


def _ready(db, store, ana_user, company, bodies=("one", "two")) -> ReportThread:
    """A thread with a first draft and no AI job running."""
    from analekh.reports.threads import create_thread

    thread = create_thread(db, ana_user.id, company.id, "quarterly", "word", "standalone", date(2026, 9, 30))
    save_version(db, store, thread, parse_draft(_draft(*bodies)), "first_draft", 0, None)
    return thread


# --- starting a thread ----------------------------------------------------------------------------


def test_start_claims_the_draft_and_queues_the_first_draft(ana, ana_user, company, queue, db):
    res = _start(ana)
    assert res.status_code == 200
    body = res.json()
    thread = db.get(ReportThread, body["thread_id"])
    assert thread.busy_job_id == body["job_id"]
    assert queue["first"].calls == [((thread.id, ana_user.id), body["job_id"])]


def test_an_initiating_report_needs_a_model(ana, company, queue):
    assert _start(ana, report_type="initiating").status_code == 422


def test_unknown_company_is_404(ana, queue):
    assert _start(ana, symbol="NOPE").status_code == 404


def test_queue_down_leaves_no_thread_behind(ana, company, monkeypatch, db):
    from analekh.jobs import health

    monkeypatch.setattr(health, "queue_available", lambda *a, **k: False)
    assert _start(ana).status_code == 503
    assert db.query(ReportThread).count() == 0


# --- one writer, owner checks ---------------------------------------------------------------------


def test_someone_elses_thread_is_404_on_every_route(ana, ravi, ana_user, company, store, queue, db):
    thread = _ready(db, store, ana_user, company)
    tid = thread.id
    assert ravi.get(f"/threads/{tid}").status_code == 404
    assert ravi.post(f"/threads/{tid}/messages", json={"message": "hi", "base_version": 1}, headers=CSRF).status_code == 404
    assert ravi.put(f"/threads/{tid}/draft", json={"base_version": 1, "draft": _draft("x")}, headers=CSRF).status_code == 404
    assert ravi.post(f"/threads/{tid}/approve", json={"base_version": 1}, headers=CSRF).status_code == 404
    assert ravi.get("/threads").json() == []
    assert [t["id"] for t in ana.get("/threads").json()] == [tid]


def test_a_message_while_the_ai_is_writing_is_409(ana, ana_user, company, store, queue, db):
    thread = _ready(db, store, ana_user, company)
    first = ana.post(f"/threads/{thread.id}/messages", json={"message": "tighten", "base_version": 1}, headers=CSRF)
    assert first.status_code == 200 and len(queue["turn"].calls) == 1
    second = ana.post(f"/threads/{thread.id}/messages", json={"message": "again", "base_version": 1}, headers=CSRF)
    assert second.status_code == 409 and second.json()["detail"]["code"] == "thread_busy"
    assert len(queue["turn"].calls) == 1


def test_typing_while_the_ai_is_writing_is_refused(ana, ana_user, company, store, queue, db):
    thread = _ready(db, store, ana_user, company)
    ana.post(f"/threads/{thread.id}/messages", json={"message": "tighten", "base_version": 1}, headers=CSRF)
    res = ana.put(f"/threads/{thread.id}/draft", json={"base_version": 1, "draft": _draft("typed", "two")}, headers=CSRF)
    assert res.status_code == 409 and res.json()["detail"]["code"] == "thread_busy"


def test_a_stale_base_version_is_409(ana, ana_user, company, store, queue, db):
    thread = _ready(db, store, ana_user, company)
    res = ana.post(f"/threads/{thread.id}/messages", json={"message": "x", "base_version": 0}, headers=CSRF)
    assert res.status_code == 409 and res.json()["detail"]["code"] == "stale_version"
    res = ana.put(f"/threads/{thread.id}/draft", json={"base_version": 0, "draft": _draft("x", "y")}, headers=CSRF)
    assert res.status_code == 409 and res.json()["detail"]["code"] == "stale_version"


def test_a_message_over_the_limit_is_422(ana, ana_user, company, store, queue, db):
    thread = _ready(db, store, ana_user, company)
    long = "x" * (get_settings().chat_message_max_chars + 1)
    assert ana.post(f"/threads/{thread.id}/messages", json={"message": long, "base_version": 1}, headers=CSRF).status_code == 422


def test_queue_down_frees_the_draft_again(ana, ana_user, company, store, monkeypatch, db):
    from analekh.jobs import health

    thread = _ready(db, store, ana_user, company)
    monkeypatch.setattr(health, "queue_available", lambda *a, **k: False)
    assert ana.post(f"/threads/{thread.id}/messages", json={"message": "x", "base_version": 1}, headers=CSRF).status_code == 503
    db.refresh(thread)
    assert thread.busy_since is None


# --- typed edits and approval ---------------------------------------------------------------------


def test_a_typed_edit_saves_a_version_and_marks_unsourced_numbers(ana, ana_user, company, store, queue, db):
    thread = _ready(db, store, ana_user, company)
    res = ana.put(f"/threads/{thread.id}/draft", json={"base_version": 1, "draft": _draft("Margins hit 18.2% now.", "two")}, headers=CSRF)
    assert res.status_code == 200
    assert res.json() == {"version_no": 2, "unsourced": ["18.2%"]}
    assert load_draft(db, store, thread).units[0].blocks[0].text == "Margins hit 18.2% now."


def test_an_invalid_or_mismatched_draft_is_422(ana, ana_user, company, store, queue, db):
    thread = _ready(db, store, ana_user, company)
    bad = {"schema_version": 1, "format": "word", "units": [{"title": "x", "blocks": [{"type": "script"}]}]}
    assert ana.put(f"/threads/{thread.id}/draft", json={"base_version": 1, "draft": bad}, headers=CSRF).status_code == 422
    ppt = {**_draft("a"), "format": "ppt"}
    assert ana.put(f"/threads/{thread.id}/draft", json={"base_version": 1, "draft": ppt}, headers=CSRF).status_code == 422


def test_approving_freezes_the_thread(ana, ana_user, company, store, queue, db):
    thread = _ready(db, store, ana_user, company)
    res = ana.post(f"/threads/{thread.id}/approve", json={"base_version": 1}, headers=CSRF)
    assert res.status_code == 200 and res.json() == {"version_no": 2, "unsourced_count": 0}
    db.refresh(thread)
    assert thread.status == "approved" and thread.approved_at is not None
    for call in (
        lambda: ana.put(f"/threads/{thread.id}/draft", json={"base_version": 2, "draft": _draft("late", "two")}, headers=CSRF),
        lambda: ana.post(f"/threads/{thread.id}/messages", json={"message": "x", "base_version": 2}, headers=CSRF),
        lambda: ana.post(f"/threads/{thread.id}/approve", json={"base_version": 2}, headers=CSRF),
    ):
        res = call()
        assert res.status_code == 409 and res.json()["detail"]["code"] == "thread_frozen"


def test_approving_with_no_draft_yet_is_refused(ana, ana_user, company, queue, db):
    started = _start(ana).json()
    res = ana.post(f"/threads/{started['thread_id']}/approve", json={"base_version": 0}, headers=CSRF)
    assert res.status_code == 409


def test_get_thread_returns_draft_messages_and_busy_flag(ana, ana_user, company, store, queue, db):
    thread = _ready(db, store, ana_user, company)
    db.add(ThreadMessage(thread_id=thread.id, role="ai", body="Here is the first draft."))
    db.flush()
    body = ana.get(f"/threads/{thread.id}").json()
    assert body["current_version"] == 1 and body["busy"] is False and body["symbol"] == "APICO"
    assert len(body["draft"]["units"]) == 2
    assert [m["body"] for m in body["messages"]] == ["Here is the first draft."]


# --- the job functions ----------------------------------------------------------------------------


class FakeClaude:
    model = "fake"

    def __init__(self, final: str, calc_first: bool = True):
        self.final, self.calc_first, self.turn = final, calc_first, 0

    def create(self, purpose, **kwargs):
        self.turn += 1
        if self.calc_first and self.turn % 2 == 1:
            block = SimpleNamespace(type="tool_use", id="t", name="calc", input={"expression": "a/b*100", "inputs": [{"name": "a", "value": 1}, {"name": "b", "value": 8}]})
            return SimpleNamespace(text="", message=SimpleNamespace(stop_reason="tool_use", content=[block]), input_tokens=1, output_tokens=1)
        msg = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=self.final)])
        return SimpleNamespace(text=self.final, message=msg, input_tokens=1, output_tokens=1)


class Exploding:
    model = "boom"

    def create(self, *a, **k):
        raise RuntimeError("secret draft text must not reach the chat")


def test_first_draft_has_every_outline_section_and_the_rating_placeholders(db, store, ana_user, company):
    from analekh.reports.threads import claim, create_thread

    thread = create_thread(db, ana_user.id, company.id, "quarterly", "word", "standalone", date(2026, 9, 30))
    claim(db, thread.id, ana_user.id, 0, "job-1")
    do_first_draft(db, store, FakeClaude("Margin was 12.5% [calc]."), ToolExecutor(session=None), thread_id=thread.id, user_id=ana_user.id, job_id="job-1")
    db.refresh(thread)
    draft = load_draft(db, store, thread)
    assert [u.title for u in draft.units] == ["Results highlights", "Concall highlights", "Risks and future guidance", "Investment rationale", RATING_UNIT]
    assert [b.kind for b in draft.units[-1].blocks] == ["rating", "target", "guidance"]
    assert thread.busy_since is None and thread.current_version == 1
    msg = db.query(ThreadMessage).filter_by(thread_id=thread.id).one()
    assert msg.role == "ai" and msg.meta["blocked"] == []


def test_a_section_that_fails_grounding_is_marked_not_dropped(db, store, ana_user, company):
    from analekh.reports.threads import claim, create_thread

    thread = create_thread(db, ana_user.id, company.id, "quarterly", "word", "standalone")
    claim(db, thread.id, ana_user.id, 0, "job-1")
    do_first_draft(db, store, FakeClaude("Margin was 14.0%."), ToolExecutor(session=None), thread_id=thread.id, user_id=ana_user.id, job_id="job-1")
    db.refresh(thread)
    draft = load_draft(db, store, thread)
    assert draft.units[0].blocks[0].text == NOT_DRAFTED
    msg = db.query(ThreadMessage).filter_by(thread_id=thread.id).one()
    assert len(msg.meta["blocked"]) == 4 and msg.meta["blocked"][0]["unmatched"] == ["14.0%"]


def test_a_failed_chat_turn_frees_the_draft_and_tells_the_analyst_plainly(db, store, ana_user, company):
    from analekh.reports.threads import claim

    thread = _ready(db, store, ana_user, company)
    claim(db, thread.id, ana_user.id, 1, "job-9")
    do_chat_turn(db, store, Exploding(), ToolExecutor(session=None), thread_id=thread.id, message="tighten", selection=Selection(unit=0), user_id=ana_user.id, job_id="job-9")
    db.refresh(thread)
    assert thread.busy_since is None and thread.current_version == 1
    ai = db.query(ThreadMessage).filter_by(thread_id=thread.id, role="ai").one()
    assert ai.body == FAILED_REPLY and "secret" not in json.dumps(ai.meta)


def test_the_approved_file_downloads_with_its_thread_tag(ana, ravi, ana_user, company, store, queue, db):
    from analekh.reports.tag import ReportTag, read_report_tag

    thread = _ready(db, store, ana_user, company)
    assert ana.get(f"/threads/{thread.id}/file").status_code == 409
    ana.post(f"/threads/{thread.id}/approve", json={"base_version": 1}, headers=CSRF)
    res = ana.get(f"/threads/{thread.id}/file")
    assert res.status_code == 200
    assert res.headers["content-disposition"] == 'attachment; filename="APICO-quarterly-2026-09-30.docx"'
    assert read_report_tag(res.content) == ReportTag(thread.id, 2)
    assert ravi.get(f"/threads/{thread.id}/file").status_code == 404


def test_the_file_is_built_on_the_sectors_active_template(ana, ana_user, company, store, queue, db):
    import io

    from docx import Document

    from analekh.db.models import Template
    from analekh.reports.build import MARKER

    company.sector = "Banks"
    tmpl = Document()
    for text in ("House cover", MARKER, "House disclaimer"):
        tmpl.add_paragraph(text)
    raw = io.BytesIO()
    tmpl.save(raw)
    store.put("templates/test/house.docx", raw.getvalue())
    db.add(Template(owner=ana_user.id, name="House", sectors=["Banks"], storage_key="templates/test/house.docx", status="active", kind="word_report"))
    db.flush()
    thread = _ready(db, store, ana_user, company)
    ana.post(f"/threads/{thread.id}/approve", json={"base_version": 1}, headers=CSRF)
    res = ana.get(f"/threads/{thread.id}/file")
    texts = [p.text for p in Document(io.BytesIO(res.content)).paragraphs if p.text]
    assert texts[0] == "House cover" and texts[-1] == "House disclaimer" and "Section 0" in texts


def _approved_file(ana, db, store, ana_user, company):
    thread = _ready(db, store, ana_user, company)
    ana.post(f"/threads/{thread.id}/approve", json={"base_version": 1}, headers=CSRF)
    return thread, ana.get(f"/threads/{thread.id}/file").content


def test_publishing_from_the_reports_page(ana, ravi, ana_user, company, store, queue, db):
    thread, data = _approved_file(ana, db, store, ana_user, company)
    files = {"file": ("final.docx", data, "application/octet-stream")}
    assert ravi.post(f"/threads/{thread.id}/publish", files=files, headers=CSRF).status_code == 404
    res = ana.post(f"/threads/{thread.id}/publish", files=files, headers=CSRF)
    assert res.status_code == 200 and res.json()["has_macros"] is False and res.json()["route"] == "upload"
    db.refresh(thread)
    assert thread.status == "published"
    assert queue["learn"].calls == [((res.json()["id"],), None)]


def test_publishing_by_tag_and_the_refusals_carry_a_code(ana, ravi, ana_user, company, store, queue, db):
    thread, data = _approved_file(ana, db, store, ana_user, company)
    refused = ravi.post("/publish", files={"file": ("final.docx", data, "application/octet-stream")}, headers=CSRF)
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "tag_mismatch"
    bad = ana.post("/publish", files={"file": ("final.docx", OLE + b"junk", "application/octet-stream")}, headers=CSRF)
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "unusable"
    ok = ana.post("/publish", files={"file": ("final.docx", data, "application/octet-stream")}, headers=CSRF)
    assert ok.status_code == 200 and ok.json()["thread_id"] == thread.id and ok.json()["route"] == "addin"


def test_a_file_over_the_upload_limit_is_413(ana, ana_user, company, store, queue, db, monkeypatch):
    thread, data = _approved_file(ana, db, store, ana_user, company)
    monkeypatch.setattr("analekh.api.uploads.get_max_upload_bytes", lambda db: 100)
    res = ana.post(f"/threads/{thread.id}/publish", files={"file": ("final.docx", data, "application/octet-stream")}, headers=CSRF)
    assert res.status_code == 413


def test_a_job_that_starts_after_its_claim_was_taken_over_does_nothing(db, store, ana_user, company):
    from analekh.reports.threads import claim

    thread = _ready(db, store, ana_user, company)
    claim(db, thread.id, ana_user.id, 1, "job-new")  # a newer job holds the draft
    do_chat_turn(db, store, Exploding(), ToolExecutor(session=None), thread_id=thread.id, message="late", selection=None, user_id=ana_user.id, job_id="job-old")
    db.refresh(thread)
    assert thread.busy_job_id == "job-new"
    assert db.query(ThreadMessage).filter_by(thread_id=thread.id).count() == 0


def test_an_earlier_version_can_be_read_for_undo_by_its_owner_only(ana, ravi, ana_user, company, store, queue, db):
    thread = _ready(db, store, ana_user, company)
    ana.put(f"/threads/{thread.id}/draft", json={"base_version": 1, "draft": _draft("changed", "two")}, headers=CSRF)
    res = ana.get(f"/threads/{thread.id}/versions/1")
    assert res.status_code == 200 and res.json()["draft"]["units"][0]["blocks"][0]["text"] == "one"
    assert ana.get(f"/threads/{thread.id}/versions/9").status_code == 404
    assert ravi.get(f"/threads/{thread.id}/versions/1").status_code == 404
