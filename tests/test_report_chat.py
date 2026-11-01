"""One chat turn: the analyst asks, the AI changes the draft (design: the flow)."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

from analekh.db.models import Company, ThreadMessage
from analekh.genai.tools import ToolExecutor
from analekh.reports.chat import Selection, run_turn, thread_results
from analekh.reports.draft import Bullets, Chart, Paragraph, Placeholder, parse_draft, to_json
from analekh.reports.sourced import unsourced_numbers
from analekh.reports.store import load_draft, save_version
from analekh.reports.threads import create_thread


class FakeClaude:
    """Optionally runs a calc first (1/8 = 12.5), then answers with `final`."""

    model = "fake"

    def __init__(self, final: dict | str, calc_first: bool = True):
        self.final = final if isinstance(final, str) else json.dumps(final)
        self.calc_first = calc_first
        self.turn = 0
        self.prompts: list[str] = []

    def create(self, purpose, **kwargs):
        self.turn += 1
        self.prompts.append(str(kwargs.get("messages")))
        if self.calc_first and self.turn == 1:
            block = SimpleNamespace(
                type="tool_use",
                id="t1",
                name="calc",
                input={"expression": "a/b*100", "inputs": [{"name": "a", "value": 1}, {"name": "b", "value": 8}]},
            )
            msg = SimpleNamespace(stop_reason="tool_use", content=[block])
            return SimpleNamespace(text="", message=msg, input_tokens=10, output_tokens=5)
        msg = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=self.final)])
        return SimpleNamespace(text=self.final, message=msg, input_tokens=10, output_tokens=5)


@pytest.fixture
def thread(db, store, analyst):
    co = Company(nse_symbol="CHATCO", name="Chat Co Limited", isin="INE000C01011")
    db.add(co)
    db.flush()
    th = create_thread(db, analyst.id, co.id, "quarterly", "word", "both", quarter_end=date(2026, 9, 30))
    draft = parse_draft(
        {
            "schema_version": 1,
            "format": "word",
            "units": [
                {"title": "Results highlights", "blocks": [{"type": "paragraph", "text": "Old text."}]},
                {
                    "title": "Investment rationale",
                    "blocks": [
                        {"type": "paragraph", "text": "Old rationale."},
                        {"type": "chart", "chart_type": "bar", "title": "PAT", "labels": ["Q1"], "series": [{"name": "PAT", "values": ["1"], "sources": ["fact:1"]}]},
                        {"type": "placeholder", "kind": "rating"},
                    ],
                },
            ],
        }
    )
    save_version(db, store, th, draft, "first_draft", 0, None)
    return th


def _turn(db, store, thread, analyst, final, message="make it crisper", selection=None, calc_first=True, lessons=()):
    claude = FakeClaude(final, calc_first)
    res = run_turn(db, store, claude, ToolExecutor(session=None), thread, message, selection, analyst.id, lessons)
    return res, claude


def test_grounded_change_writes_a_new_version(db, store, thread, analyst):
    final = {"reply": "Tightened it.", "changes": [{"unit": 0, "markdown": "Margin was 12.5% [calc].\n\n- Costs flat."}]}
    res, _ = _turn(db, store, thread, analyst, final, selection=Selection(unit=0))
    assert res.changed_units == [0] and res.version_no == 2 and not res.blocked
    assert res.reply == "Tightened it."
    draft = load_draft(db, store, thread)
    assert isinstance(draft.units[0].blocks[0], Paragraph) and isinstance(draft.units[0].blocks[1], Bullets)
    assert draft.units[0].title == "Results highlights"
    roles = [m.role for m in db.query(ThreadMessage).filter_by(thread_id=thread.id).order_by(ThreadMessage.id)]
    assert roles == ["analyst", "ai"]


def test_unmatched_number_is_not_inserted(db, store, thread, analyst):
    final = {"reply": "Done.", "changes": [{"unit": 0, "markdown": "Margin was 14.0%."}]}
    res, _ = _turn(db, store, thread, analyst, final)
    assert res.changed_units == [] and res.version_no is None
    assert res.blocked[0].unmatched == ["14.0%"]
    assert thread.current_version == 1


def test_rewriting_a_unit_keeps_its_placeholder_and_chart(db, store, thread, analyst):
    final = {"reply": "Rewrote.", "changes": [{"unit": 1, "markdown": "New rationale."}]}
    _turn(db, store, thread, analyst, final, calc_first=False)
    blocks = load_draft(db, store, thread).units[1].blocks
    assert isinstance(blocks[0], Paragraph) and blocks[0].text == "New rationale."
    assert any(isinstance(b, Chart) for b in blocks)
    assert any(isinstance(b, Placeholder) and b.kind == "rating" for b in blocks)


def test_keep_charts_false_drops_them_but_never_the_placeholder(db, store, thread, analyst):
    final = {"reply": "Removed chart.", "changes": [{"unit": 1, "markdown": "Only text.", "keep_charts": False}]}
    _turn(db, store, thread, analyst, final, calc_first=False)
    blocks = load_draft(db, store, thread).units[1].blocks
    assert not any(isinstance(b, Chart) for b in blocks)
    assert any(isinstance(b, Placeholder) for b in blocks)


def test_a_rating_written_by_the_ai_is_blocked(db, store, thread, analyst):
    final = {"reply": "Added.", "changes": [{"unit": 1, "markdown": "We rate it Buy."}]}
    res, _ = _turn(db, store, thread, analyst, final, calc_first=False)
    assert res.changed_units == [] and "rating" in res.blocked[0].reasons


def test_change_outside_the_selection_is_blocked(db, store, thread, analyst):
    final = {"reply": "Done.", "changes": [{"unit": 1, "markdown": "Other text."}]}
    res, _ = _turn(db, store, thread, analyst, final, selection=Selection(unit=0), calc_first=False)
    assert res.changed_units == [] and "outside_selection" in res.blocked[0].reasons


def test_unit_index_past_the_end_adds_a_unit_but_beyond_that_is_refused(db, store, thread, analyst):
    ok = {"reply": "Added.", "changes": [{"unit": 2, "title": "Risks", "markdown": "Some risk."}]}
    res, _ = _turn(db, store, thread, analyst, ok, calc_first=False)
    assert res.changed_units == [2]
    assert [u.title for u in load_draft(db, store, thread).units][-1] == "Risks"
    bad = {"reply": "Added.", "changes": [{"unit": 9, "title": "Far", "markdown": "x"}]}
    res2, _ = _turn(db, store, thread, analyst, bad, calc_first=False)
    assert res2.changed_units == [] and "bad_unit" in res2.blocked[0].reasons


def test_reply_with_an_unsourced_number_is_withheld(db, store, thread, analyst):
    final = {"reply": "Margins hit 77.7% now.", "changes": []}
    res, _ = _turn(db, store, thread, analyst, final, calc_first=False)
    assert res.reply_blocked and res.reply_unmatched == ["77.7%"]
    stored = db.query(ThreadMessage).filter_by(thread_id=thread.id, role="ai").one()
    assert "77.7" not in stored.body


def test_a_reply_that_is_not_json_is_still_shown_and_changes_nothing(db, store, thread, analyst):
    res, _ = _turn(db, store, thread, analyst, "Sure, here is some advice.", calc_first=False)
    assert res.reply == "Sure, here is some advice." and res.changed_units == []


def test_lessons_and_history_reach_the_prompt(db, store, thread, analyst):
    _, first = _turn(db, store, thread, analyst, {"reply": "ok", "changes": []}, message="first ask", calc_first=False, lessons=("Lead with NIM",))
    assert "Lead with NIM" in first.prompts[0]
    _, second = _turn(db, store, thread, analyst, {"reply": "ok", "changes": []}, message="second ask", calc_first=False)
    assert "first ask" in second.prompts[0]


def test_tool_results_of_every_turn_are_kept_for_the_sourced_check(db, store, thread, analyst):
    final = {"reply": "Margin was 12.5% [calc].", "changes": []}
    _turn(db, store, thread, analyst, final)
    results = thread_results(db, store, thread)
    assert unsourced_numbers(db, thread, "Margin was 12.5%.", results) == []
    assert unsourced_numbers(db, thread, "Margin was 99.9%.", results) == ["99.9%"]
    assert to_json(load_draft(db, store, thread))["units"][0]["title"] == "Results highlights"
