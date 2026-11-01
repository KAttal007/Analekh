"""Upgrade check against past reports, and the JSONL export (Task 13)."""

import json
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from analekh.db.models import Company, Lesson, LessonCheck
from analekh.reports.build import build_docx
from analekh.reports.chat import add_ai_message
from analekh.reports.draft import parse_draft
from analekh.reports.export import export_jsonl
from analekh.reports.publish import publish
from analekh.reports.store import save_version
from analekh.reports.tag import ReportTag, write_report_tag
from analekh.reports.threads import create_thread
from analekh.reports.upgrade import ReplayExecutor, check_candidate

CALC = {"expression": "a/b*100", "inputs": [{"name": "a", "value": 1}, {"name": "b", "value": 8}]}


class Model:
    """Calls calc with `args`, then writes `text`, for every section."""

    def __init__(self, name: str, text: str, args: dict = CALC):
        self.model, self.text, self.args, self.turn = name, text, args, 0

    def create(self, purpose, **kwargs):
        self.turn += 1
        if self.turn % 2 == 1:
            block = SimpleNamespace(type="tool_use", id="t", name="calc", input=self.args)
            return SimpleNamespace(text="", message=SimpleNamespace(stop_reason="tool_use", content=[block]), input_tokens=1, output_tokens=1)
        msg = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=self.text)])
        return SimpleNamespace(text=self.text, message=msg, input_tokens=1, output_tokens=1)


def _draft(text: str):
    return parse_draft({"schema_version": 1, "format": "word", "units": [{"title": "Results highlights", "blocks": [{"type": "paragraph", "text": text}]}]})


@pytest.fixture
def published(db, store, analyst):
    co = Company(nse_symbol="UPCO", name="Up Co Limited", isin="INE000U01011")
    db.add(co)
    db.flush()
    thread = create_thread(db, analyst.id, co.id, "quarterly", "word", "standalone", date(2026, 9, 30))
    save_version(db, store, thread, _draft("Margin was 12.5%."), "first_draft", 0, None)
    add_ai_message(
        db, store, thread, body="Here is the first draft.", meta={}, model_used="old", prompt="p", tool_calls=[], results=[], exchanges=[{"tool": "calc", "input": CALC, "result": {"result": "12.5"}}]
    )
    save_version(db, store, thread, _draft("Margins steady at 12.5%. We rate it Buy, TP 900."), "analyst_edit", 1, analyst.id)
    save_version(db, store, thread, _draft("Margins steady at 12.5%."), "approved", 2, analyst.id)
    thread.status = "approved"
    db.flush()
    final = write_report_tag(build_docx(_draft("Margins steady at 12.5%. We rate it Buy."), None), ReportTag(thread.id, 3))
    publish(db, store, analyst.id, final, "final.docx", "upload", thread_id=thread.id)
    thread.published_at = datetime.now(UTC)
    db.flush()
    return thread


def test_replay_answers_recorded_calls_and_counts_new_ones():
    ex = ReplayExecutor([{"tool": "calc", "input": CALC, "result": {"result": "12.5"}}])
    assert ex.run("calc", CALC) == {"result": "12.5"}
    with pytest.raises(ValueError):
        ex.run("calc", {"expression": "a", "inputs": []})
    assert ex.new_data == 1


def test_an_equal_candidate_passes_and_the_check_is_stored(db, store, published):
    res = check_candidate(db, store, Model("cur", "Margin was 12.5% [calc]."), Model("new", "Margin held at 12.5% [calc]."), [published])
    assert res.verdict == "pass" and res.worse_on == []
    assert db.get(LessonCheck, res.check_id).candidate_model == "new"


def test_a_candidate_with_more_grounding_rejections_fails(db, store, published):
    res = check_candidate(db, store, Model("cur", "Margin was 12.5% [calc]."), Model("new", "Margin was 14.0%."), [published])
    assert res.verdict == "fail" and "grounding_rejections" in res.worse_on


def test_data_the_record_lacks_is_counted_not_failed(db, store, published):
    other = {"expression": "a*2", "inputs": [{"name": "a", "value": 1}]}
    res = check_candidate(db, store, Model("cur", "Steady quarter."), Model("new", "Steady quarter.", other), [published])
    assert res.candidate["new_data"] >= 1 and res.verdict == "pass"


def test_losing_a_lesson_the_current_model_keeps_fails_but_one_both_fail_does_not(db, store, analyst, published):
    db.add(Lesson(scope="analyst", owner_id=analyst.id, text="Never call margins robust", test_kind="phrase", test_spec={"banned": ["robust"]}))
    db.add(Lesson(scope="firm", text="Always mention NIM", test_kind="phrase", test_spec={"required": ["NIM"]}))
    db.flush()
    lost = check_candidate(db, store, Model("cur", "Steady margins [calc]."), Model("new", "Robust margins [calc]."), [published])
    assert lost.verdict == "fail" and len(lost.lessons_lost) == 1
    assert len(lost.lessons_failed_by_both) == 1  # NIM: neither mentions it, reported only
    kept = check_candidate(db, store, Model("cur", "Steady margins [calc]."), Model("new", "Calm margins [calc]."), [published])
    assert kept.verdict == "pass"


def test_export_has_every_pair_type_and_no_rating(db, store, published, tmp_path):
    out = tmp_path / "export.jsonl"
    n = export_jsonl(db, store, out)
    lines = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    assert lines[0]["schema_version"] == 1 and n == len(lines) - 1
    assert {r["type"] for r in lines[1:]} == {"first_draft", "analyst_edit", "final"}
    body = out.read_text(encoding="utf-8")
    assert "Buy" not in body and "900" not in body


def test_export_can_mask_every_number(db, store, published, tmp_path):
    out = tmp_path / "export.jsonl"
    export_jsonl(db, store, out, mask_numbers=True)
    pairs = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()[1:]]
    assert all("12.5" not in json.dumps(p) for p in pairs)
    assert any("<n>" in json.dumps(p) for p in pairs)
