"""Report thread tables (migration 0019; design: report chat record)."""

import pytest
from sqlalchemy.exc import IntegrityError

from analekh.db.models import Company, Lesson, ReportThread, ThreadMessage


def _thread(db, owner, company: Company, **overrides) -> ReportThread:
    fields = {
        "owner_id": owner.id,
        "company_id": company.id,
        "report_type": "quarterly",
        "format": "word",
        "basis": "standalone",
    }
    fields.update(overrides)
    thread = ReportThread(**fields)
    db.add(thread)
    db.flush()
    return thread


@pytest.fixture
def company(db) -> Company:
    co = Company(nse_symbol="THREADCO", name="Thread Co Limited", isin="INE000T01011")
    db.add(co)
    db.flush()
    return co


def test_new_thread_starts_drafting_at_version_zero(db, analyst, company):
    thread = _thread(db, analyst, company)
    assert thread.status == "drafting"
    assert thread.current_version == 0
    assert thread.created_at is not None


def test_status_outside_the_three_states_is_refused(db, analyst, company):
    with pytest.raises(IntegrityError):
        _thread(db, analyst, company, status="done")


def test_format_outside_word_and_ppt_is_refused(db, analyst, company):
    with pytest.raises(IntegrityError):
        _thread(db, analyst, company, format="pdf")


def test_owner_is_required(db, company):
    db.add(ReportThread(company_id=company.id, report_type="quarterly", format="word", basis="both", owner_id=None))
    with pytest.raises(IntegrityError):
        db.flush()


def test_message_role_is_analyst_or_ai(db, analyst, company):
    thread = _thread(db, analyst, company)
    db.add(ThreadMessage(thread_id=thread.id, role="robot", body="hi"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_analyst_lesson_needs_an_owner(db, company):
    db.add(Lesson(scope="analyst", owner_id=None, text="Never say robust", test_kind="phrase", test_spec={"words": ["robust"]}))
    with pytest.raises(IntegrityError):
        db.flush()


def test_firm_lesson_needs_no_owner(db):
    db.add(Lesson(scope="firm", owner_id=None, text="Charts show eight quarters", test_kind="structure", test_spec={"min_points": 8}))
    db.flush()
