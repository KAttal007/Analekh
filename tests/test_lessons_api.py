"""Lessons routes: own lessons, firm lessons, admin-only promotion (design: lessons)."""

import pytest
from fastapi.testclient import TestClient

from analekh.api.deps import get_store
from analekh.api.main import app
from analekh.auth.service import create_user
from analekh.db.models import Lesson
from analekh.db.session import get_session

GOOD = "Correct-Horse-Battery-9"
CSRF = {"X-Analekh-CSRF": "1"}


@pytest.fixture
def wired(db, store):
    app.dependency_overrides[get_session] = lambda: db
    app.dependency_overrides[get_store] = lambda: store
    yield
    app.dependency_overrides.clear()


def _client(email: str) -> TestClient:
    c = TestClient(app, raise_server_exceptions=False)
    assert c.post("/auth/login", json={"email": email, "password": GOOD}).status_code == 200
    return c


@pytest.fixture
def people(db, wired):
    ana = create_user(db, "ana@firm.in", "Ana", "analyst", GOOD)
    create_user(db, "ravi@firm.in", "Ravi", "analyst", GOOD)
    create_user(db, "boss@firm.in", "Boss", "admin", GOOD)
    mine = Lesson(scope="analyst", owner_id=ana.id, text="Never call margins robust", test_kind="phrase", test_spec={"banned": ["robust"]})
    firm = Lesson(scope="firm", owner_id=None, text="Charts show eight quarters", test_kind="structure", test_spec={"min_chart_points": 8})
    db.add_all([mine, firm])
    db.flush()
    return {"ana": _client("ana@firm.in"), "ravi": _client("ravi@firm.in"), "boss": _client("boss@firm.in"), "mine": mine, "firm": firm}


def test_each_analyst_sees_their_own_and_the_firms(people):
    ana = {lesson["text"]: lesson["mine"] for lesson in people["ana"].get("/lessons").json()}
    assert ana == {"Never call margins robust": True, "Charts show eight quarters": False}
    assert [lesson["text"] for lesson in people["ravi"].get("/lessons").json()] == ["Charts show eight quarters"]


def test_an_analyst_edits_and_retires_their_own_lesson(people):
    lid = people["mine"].id
    res = people["ana"].patch(f"/lessons/{lid}", json={"text": "Never call margins strong or robust", "status": "retired"}, headers=CSRF)
    assert res.status_code == 200 and res.json()["status"] == "retired"


def test_someone_elses_lesson_and_a_firm_lesson_are_404_for_an_analyst(people):
    assert people["ravi"].patch(f"/lessons/{people['mine'].id}", json={"status": "retired"}, headers=CSRF).status_code == 404
    assert people["ravi"].delete(f"/lessons/{people['mine'].id}", headers=CSRF).status_code == 404
    assert people["ana"].patch(f"/lessons/{people['firm'].id}", json={"status": "retired"}, headers=CSRF).status_code == 404


def test_a_lesson_about_ratings_is_refused(people):
    res = people["ana"].patch(f"/lessons/{people['mine'].id}", json={"text": "Always say Buy"}, headers=CSRF)
    assert res.status_code == 422


def test_only_an_admin_promotes_and_edits_firm_lessons(people):
    lid = people["mine"].id
    assert people["ana"].post(f"/lessons/{lid}/promote", headers=CSRF).status_code == 403
    res = people["boss"].post(f"/lessons/{lid}/promote", headers=CSRF)
    assert res.status_code == 200 and res.json()["scope"] == "firm"
    assert people["boss"].patch(f"/lessons/{people['firm'].id}", json={"status": "retired"}, headers=CSRF).status_code == 200


def test_an_analyst_deletes_their_own_lesson(people, db):
    assert people["ana"].delete(f"/lessons/{people['mine'].id}", headers=CSRF).status_code == 204
    assert db.get(Lesson, people["mine"].id) is None
