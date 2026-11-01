"""Multi-turn Q&A threads (Task 14): owner-only, one question at a time, grounded answers."""

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from analekh.api.deps import get_store
from analekh.api.main import app
from analekh.auth.service import create_user
from analekh.config import get_settings
from analekh.db.models import Company, QaMessage, QaThread
from analekh.db.session import get_session
from analekh.genai.qa_chat import FAILED, WITHHELD, claim, do_qa_turn, qa_turn
from analekh.genai.tools import ToolExecutor

GOOD = "Correct-Horse-Battery-9"
CSRF = {"X-Analekh-CSRF": "1"}


class FakeTask:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[Any, ...], str | None]] = []

    def apply_async(self, args=(), task_id=None):
        self.calls.append((tuple(args), task_id))
        return SimpleNamespace(id=task_id or "auto", status="PENDING")


@pytest.fixture
def wired(db, store, monkeypatch):
    from analekh.jobs import health

    app.dependency_overrides[get_session] = lambda: db
    app.dependency_overrides[get_store] = lambda: store
    task = FakeTask()
    monkeypatch.setattr("analekh.jobs.report_tasks.run_qa_turn", task)
    monkeypatch.setattr(health, "queue_available", lambda *a, **k: True)
    yield task
    app.dependency_overrides.clear()


def _client(email: str) -> TestClient:
    c = TestClient(app, raise_server_exceptions=False)
    assert c.post("/auth/login", json={"email": email, "password": GOOD}).status_code == 200
    return c


@pytest.fixture
def setup(db, wired):
    create_user(db, "ana@firm.in", "Ana", "analyst", GOOD)
    create_user(db, "ravi@firm.in", "Ravi", "analyst", GOOD)
    db.add(Company(nse_symbol="QACO", name="Qa Co Limited", isin="INE000Q01011"))
    db.flush()
    return {"ana": _client("ana@firm.in"), "ravi": _client("ravi@firm.in"), "task": wired}


def test_a_chat_is_started_listed_and_private(setup):
    ana, ravi = setup["ana"], setup["ravi"]
    qa = ana.post("/qa/threads", json={"symbol": "QACO"}, headers=CSRF).json()
    assert qa["symbol"] == "QACO" and qa["busy"] is False
    assert [t["id"] for t in ana.get("/qa/threads").json()] == [qa["id"]]
    assert ravi.get("/qa/threads").json() == []
    assert ravi.get(f"/qa/threads/{qa['id']}").status_code == 404
    assert ravi.post(f"/qa/threads/{qa['id']}/messages", json={"question": "x"}, headers=CSRF).status_code == 404


def test_one_question_at_a_time_and_a_length_limit(setup):
    ana = setup["ana"]
    qa = ana.post("/qa/threads", json={"symbol": "QACO"}, headers=CSRF).json()
    assert ana.post(f"/qa/threads/{qa['id']}/messages", json={"question": "What was NIM?"}, headers=CSRF).status_code == 200
    busy = ana.post(f"/qa/threads/{qa['id']}/messages", json={"question": "And again?"}, headers=CSRF)
    assert busy.status_code == 409 and len(setup["task"].calls) == 1
    long = "x" * (get_settings().qa_question_max_chars + 1)
    assert ana.post(f"/qa/threads/{qa['id']}/messages", json={"question": long}, headers=CSRF).status_code == 422


class FakeClaude:
    model = "fake"

    def __init__(self, text: str):
        self.text, self.turn, self.prompts = text, 0, []

    def create(self, purpose, **kwargs):
        self.turn += 1
        self.prompts.append(str(kwargs.get("messages")))
        if self.turn % 2 == 1:
            block = SimpleNamespace(type="tool_use", id="t", name="calc", input={"expression": "a/b*100", "inputs": [{"name": "a", "value": 1}, {"name": "b", "value": 8}]})
            return SimpleNamespace(text="", message=SimpleNamespace(stop_reason="tool_use", content=[block]), input_tokens=1, output_tokens=1)
        msg = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=self.text)])
        return SimpleNamespace(text=self.text, message=msg, input_tokens=1, output_tokens=1)


@pytest.fixture
def thread(db, analyst):
    co = Company(nse_symbol="QACO2", name="Qa Two Limited", isin="INE000Q01029")
    db.add(co)
    db.flush()
    t = QaThread(owner_id=analyst.id, company_id=co.id)
    db.add(t)
    db.flush()
    return t


def test_a_grounded_answer_keeps_its_page_citations_and_history_reaches_the_next_question(db, thread):
    first = qa_turn(db, FakeClaude("NIM was 12.5% [calc] per the deck [filing:4 page:7]."), ToolExecutor(session=None), thread, "What was NIM?")
    assert first.meta["blocked"] is False and first.meta["citations"] == [{"filing_id": 4, "page": 7}]
    assert thread.title == "What was NIM?"
    claude = FakeClaude("Same as before [calc] 12.5%.")
    qa_turn(db, claude, ToolExecutor(session=None), thread, "And last quarter?")
    assert "What was NIM?" in claude.prompts[0]


def test_an_ungrounded_answer_is_withheld_with_its_numbers(db, thread):
    ans = qa_turn(db, FakeClaude("NIM was 14.0%."), ToolExecutor(session=None), thread, "What was NIM?")
    assert ans.body == WITHHELD and ans.meta["unmatched"] == ["14.0%"] and ans.meta["citations"] == []


def test_a_failed_answer_frees_the_chat(db, thread, analyst):
    class Boom:
        model = "boom"

        def create(self, *a, **k):
            raise RuntimeError("no")

    claim(db, thread.id, analyst.id, "job-1")
    do_qa_turn(db, Boom(), ToolExecutor(session=None), qa_id=thread.id, question="Q?", user_id=analyst.id, job_id="job-1")
    db.refresh(thread)
    assert thread.busy_since is None
    assert db.query(QaMessage).filter_by(thread_id=thread.id, role="ai").one().body == FAILED
