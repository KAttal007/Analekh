"""Versioned draft store and thread lifecycle (design: the record)."""

import pytest

from analekh.db.models import Company, ReportVersion
from analekh.reports.draft import Draft, Paragraph, Unit, parse_draft, to_json
from analekh.reports.store import StaleVersion, ThreadFrozen, VersionCorrupt, load_draft, save_version
from analekh.reports.threads import create_thread


@pytest.fixture
def thread(db, analyst):
    co = Company(nse_symbol="VERSCO", name="Version Co Limited", isin="INE000V01011")
    db.add(co)
    db.flush()
    return create_thread(db, analyst.id, co.id, "quarterly", "word", "standalone")


def _draft(*bodies: str) -> Draft:
    return parse_draft(
        {
            "schema_version": 1,
            "format": "word",
            "units": [{"title": f"Section {i}", "blocks": [{"type": "paragraph", "text": body}]} for i, body in enumerate(bodies)],
        }
    )


def test_create_thread_validates_its_choices(db, analyst):
    co = Company(nse_symbol="VERSCO2", name="V2", isin="INE000V01029")
    db.add(co)
    db.flush()
    for bad in ({"report_type": "ipo"}, {"format": "pdf"}, {"basis": "weird"}):
        args = {"report_type": "quarterly", "format": "word", "basis": "both", **bad}
        with pytest.raises(ValueError):
            create_thread(db, analyst.id, co.id, **args)


def test_versions_round_trip_and_number_up(db, store, thread, analyst):
    v1 = _draft("a" * 400, "b" * 400, "c" * 400, "d" * 400)
    save_version(db, store, thread, v1, "first_draft", 0, None)
    v2 = _draft("a" * 400, "B edited", "c" * 400, "d" * 400)
    save_version(db, store, thread, v2, "analyst_edit", 1, analyst.id)
    v3 = _draft("a" * 400, "B edited", "c" * 400, "d" * 400, "new section")
    save_version(db, store, thread, v3, "ai_reply", 2, None)
    assert thread.current_version == 3
    assert to_json(load_draft(db, store, thread, 1)) == to_json(v1)
    assert to_json(load_draft(db, store, thread, 2)) == to_json(v2)
    assert to_json(load_draft(db, store, thread)) == to_json(v3)


def test_later_versions_are_smaller_than_the_first(db, store, thread, analyst):
    save_version(db, store, thread, _draft(*["x" * 500] * 6), "first_draft", 0, None)
    save_version(db, store, thread, _draft("x" * 500, "edited", *["x" * 500] * 4), "analyst_edit", 1, analyst.id)
    first, second = db.query(ReportVersion).filter_by(thread_id=thread.id).order_by(ReportVersion.version_no).all()
    assert first.full and not second.full
    assert len(store.get(second.storage_key)) < len(store.get(first.storage_key))


def test_stale_parent_is_refused(db, store, thread, analyst):
    save_version(db, store, thread, _draft("one"), "first_draft", 0, None)
    save_version(db, store, thread, _draft("two"), "analyst_edit", 1, analyst.id)
    with pytest.raises(StaleVersion):
        save_version(db, store, thread, _draft("three"), "analyst_edit", 1, analyst.id)
    assert thread.current_version == 2


def test_saving_the_same_draft_again_makes_no_new_version(db, store, thread):
    save_version(db, store, thread, _draft("one"), "first_draft", 0, None)
    same = save_version(db, store, thread, _draft("one"), "ai_reply", 1, None)
    assert same.version_no == 1 and thread.current_version == 1


def test_approved_version_is_stored_in_full_and_freezes_saves(db, store, thread, analyst):
    save_version(db, store, thread, _draft("one", "two"), "first_draft", 0, None)
    approved = save_version(db, store, thread, _draft("one", "two edited"), "approved", 1, analyst.id)
    assert approved.full
    thread.status = "approved"
    with pytest.raises(ThreadFrozen):
        save_version(db, store, thread, _draft("late"), "analyst_edit", 2, analyst.id)


def test_a_changed_stored_body_is_detected(db, store, thread):
    row = save_version(db, store, thread, _draft("one"), "first_draft", 0, None)
    path = store.root / row.storage_key
    path.write_bytes(b"{}")
    with pytest.raises(VersionCorrupt):
        load_draft(db, store, thread)


def test_shrinking_a_draft_round_trips(db, store, thread, analyst):
    save_version(db, store, thread, _draft("a", "b", "c"), "first_draft", 0, None)
    save_version(db, store, thread, _draft("a"), "ai_reply", 1, None)
    assert [u.title for u in load_draft(db, store, thread).units] == ["Section 0"]
    assert isinstance(load_draft(db, store, thread).units[0], Unit)
    assert isinstance(load_draft(db, store, thread).units[0].blocks[0], Paragraph)


def test_approving_an_unedited_draft_still_makes_a_full_version(db, store, thread, analyst):
    save_version(db, store, thread, _draft("one", "two"), "first_draft", 0, None)
    save_version(db, store, thread, _draft("one", "two edited"), "analyst_edit", 1, analyst.id)
    approved = save_version(db, store, thread, _draft("one", "two edited"), "approved", 2, analyst.id)
    assert approved.version_no == 3 and approved.full and approved.trigger == "approved"
