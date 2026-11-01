"""One writer at a time: the draft is locked while an AI job runs (owner's rule, 1 November 2026)."""

from datetime import timedelta

import pytest
from sqlalchemy import func

from analekh.config import get_settings
from analekh.db.models import Company
from analekh.reports.store import StaleVersion, ThreadFrozen
from analekh.reports.threads import ThreadBusy, ThreadNotFound, claim, create_thread, get_owned, is_busy, release


@pytest.fixture
def thread(db, analyst):
    co = Company(nse_symbol="BUSYCO", name="Busy Co Limited", isin="INE000B01011")
    db.add(co)
    db.flush()
    return create_thread(db, analyst.id, co.id, "quarterly", "word", "standalone")


def test_claim_marks_the_thread_busy(db, thread, analyst):
    claim(db, thread.id, analyst.id, 0, "job-1")
    db.refresh(thread)
    assert is_busy(thread) and thread.busy_job_id == "job-1"


def test_a_second_claim_is_refused_while_busy(db, thread, analyst):
    claim(db, thread.id, analyst.id, 0, "job-1")
    with pytest.raises(ThreadBusy):
        claim(db, thread.id, analyst.id, 0, "job-2")


def test_a_claim_on_an_old_version_is_stale(db, thread, analyst):
    thread.current_version = 3
    db.flush()
    with pytest.raises(StaleVersion):
        claim(db, thread.id, analyst.id, 2, "job-1")


def test_a_claim_on_an_approved_thread_is_frozen(db, thread, analyst):
    thread.status = "approved"
    db.flush()
    with pytest.raises(ThreadFrozen):
        claim(db, thread.id, analyst.id, 0, "job-1")


def test_only_the_job_that_claimed_can_release(db, thread, analyst):
    claim(db, thread.id, analyst.id, 0, "job-1")
    release(db, thread.id, "someone-else")
    db.refresh(thread)
    assert is_busy(thread)
    release(db, thread.id, "job-1")
    db.refresh(thread)
    assert not is_busy(thread) and thread.busy_job_id is None


def test_a_dead_job_stops_blocking_after_the_timeout(db, thread, analyst):
    cfg = get_settings()
    claim(db, thread.id, analyst.id, 0, "job-1")
    thread.busy_since = func.now() - timedelta(seconds=cfg.chat_turn_timeout_s + cfg.chat_busy_grace_s + 5)
    db.flush()
    db.refresh(thread)
    assert not is_busy(thread)
    claim(db, thread.id, analyst.id, 0, "job-2")  # no refusal
    db.refresh(thread)
    assert thread.busy_job_id == "job-2"


def test_someone_elses_thread_looks_like_it_does_not_exist(db, thread, analyst2):
    with pytest.raises(ThreadNotFound):
        get_owned(db, thread.id, analyst2.id)
    with pytest.raises(ThreadNotFound):
        claim(db, thread.id, analyst2.id, 0, "job-1")
    with pytest.raises(ThreadNotFound):
        get_owned(db, 999999, analyst2.id)
