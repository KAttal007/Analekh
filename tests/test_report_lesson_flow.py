"""Lessons applied while drafting: one retry, then flagged; the analyst's explicit ask wins (Task 12)."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

from analekh.db.models import Company, Lesson, ThreadMessage
from analekh.genai.tools import ToolExecutor
from analekh.reports.build import build_docx
from analekh.reports.chat import run_turn
from analekh.reports.draft import parse_draft
from analekh.reports.jobs import do_first_draft
from analekh.reports.lessons import Rule
from analekh.reports.publish import publish
from analekh.reports.store import load_draft, save_version
from analekh.reports.tag import ReportTag, write_report_tag
from analekh.reports.threads import claim, create_thread

ROBUST = Rule(11, "Never call margins robust", "phrase", {"banned": ["robust"]})


class SeqClaude:
    """Answers each model call with the next scripted text (no tool calls)."""

    model = "fake"

    def __init__(self, *finals: str):
        self.finals = list(finals)
        self.prompts: list[str] = []

    def create(self, purpose, **kwargs):
        self.prompts.append(str(kwargs.get("messages")))
        text = self.finals.pop(0) if len(self.finals) > 1 else self.finals[0]
        msg = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)])
        return SimpleNamespace(text=text, message=msg, input_tokens=1, output_tokens=1)


def _change(markdown: str) -> str:
    return json.dumps({"reply": "Done.", "changes": [{"unit": 0, "markdown": markdown}]})


@pytest.fixture
def thread(db, store, analyst):
    co = Company(nse_symbol="FLOWCO", name="Flow Co Limited", isin="INE000F01029")
    db.add(co)
    db.flush()
    th = create_thread(db, analyst.id, co.id, "quarterly", "word", "standalone", date(2026, 9, 30))
    draft = parse_draft({"schema_version": 1, "format": "word", "units": [{"title": "Results highlights", "blocks": [{"type": "paragraph", "text": "Old."}]}]})
    save_version(db, store, th, draft, "first_draft", 0, None)
    return th


def _turn(db, store, thread, analyst, claude, message="tighten it"):
    return run_turn(db, store, claude, ToolExecutor(session=None), thread, message, None, analyst.id, [ROBUST])


def test_a_lesson_broken_once_is_retried_and_then_inserted(db, store, thread, analyst):
    claude = SeqClaude(_change("Robust margins."), _change("Steady margins."))
    res = _turn(db, store, thread, analyst, claude)
    assert res.changed_units == [0] and res.blocked == []
    assert load_draft(db, store, thread).units[0].blocks[0].text == "Steady margins."
    assert "broke the analyst's rules" in claude.prompts[1]


def test_a_lesson_broken_twice_is_flagged_not_inserted(db, store, thread, analyst):
    res = _turn(db, store, thread, analyst, SeqClaude(_change("Robust margins.")))
    assert res.changed_units == [] and res.blocked[0].reasons == ["lesson:11"]
    assert load_draft(db, store, thread).units[0].blocks[0].text == "Old."


def test_when_the_analyst_asks_for_the_banned_word_the_analyst_wins(db, store, thread, analyst):
    res = _turn(db, store, thread, analyst, SeqClaude(_change("Robust margins.")), message="call the margins robust here")
    assert res.changed_units == [0] and res.conflicts == [11]
    ai = db.query(ThreadMessage).filter_by(thread_id=thread.id, role="ai").one()
    assert ai.meta["conflicts"] == [11]


def test_first_draft_uses_lessons_retries_and_shows_masked_examples(db, store, analyst):
    co = Company(nse_symbol="FLOW2", name="Flow Two Limited", isin="INE000F01037")
    db.add(co)
    db.flush()
    db.add(Lesson(scope="analyst", owner_id=analyst.id, text="Never call margins robust", test_kind="phrase", test_spec={"banned": ["robust"]}))
    old = create_thread(db, analyst.id, co.id, "quarterly", "word", "standalone", date(2026, 6, 30))
    d = parse_draft({"schema_version": 1, "format": "word", "units": [{"title": "Results highlights", "blocks": [{"type": "paragraph", "text": "Past."}]}]})
    save_version(db, store, old, d, "first_draft", 0, None)
    save_version(db, store, old, d, "approved", 1, analyst.id)
    old.status = "approved"
    db.flush()
    past = parse_draft({"schema_version": 1, "format": "word", "units": [{"title": "Results highlights", "blocks": [{"type": "paragraph", "text": "Our house view. We rate it Buy with TP 900."}]}]})
    publish(db, store, analyst.id, write_report_tag(build_docx(past, None), ReportTag(old.id, 2)), "final.docx", "upload", thread_id=old.id)

    new = create_thread(db, analyst.id, co.id, "quarterly", "word", "standalone", date(2026, 9, 30))
    claim(db, new.id, analyst.id, 0, "job-1")
    claude = SeqClaude("Robust margins.", "Steady margins.")
    do_first_draft(db, store, claude, ToolExecutor(session=None), thread_id=new.id, user_id=analyst.id, job_id="job-1")
    first_prompt = claude.prompts[0]
    assert "Never call margins robust" in first_prompt and "Our house view." in first_prompt
    assert "Buy" not in first_prompt and "900" not in first_prompt
    db.refresh(new)
    assert load_draft(db, store, new).units[0].blocks[0].text == "Steady margins."
