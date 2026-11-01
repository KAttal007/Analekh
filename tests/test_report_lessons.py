"""Lessons: tests that enforce them, proposals from a published report, duplicates (Task 11)."""

from datetime import date

import pytest

from analekh.db.models import Company, Lesson
from analekh.reports.build import build_docx
from analekh.reports.draft import parse_draft
from analekh.reports.lessons import Proposal, Rule, add_or_strengthen, learn_from_published, propose_lessons, run_lesson_test
from analekh.reports.publish import publish
from analekh.reports.store import save_version
from analekh.reports.tag import ReportTag, write_report_tag
from analekh.reports.threads import create_thread


def _draft(text="Net interest margin rose.", points=8, titles=("Results highlights",)):
    labels = [f"Q{i}" for i in range(points)]
    units = [{"title": t, "blocks": [{"type": "paragraph", "text": text}]} for t in titles]
    units[0]["blocks"].append({"type": "chart", "chart_type": "bar", "title": "PAT", "labels": labels, "series": [{"name": "PAT", "values": ["1"] * points, "sources": ["fact:1"]}]})
    return parse_draft({"schema_version": 1, "format": "word", "units": units})


def test_phrase_lesson_catches_a_banned_word_whole_words_only():
    rule = Rule(1, "Never call margins robust", "phrase", {"banned": ["robust"]})
    assert not run_lesson_test(rule, _draft("Robust margins this quarter.")).passed
    assert run_lesson_test(rule, _draft("Robustness held.")).passed


def test_required_phrase_only_applies_to_a_whole_draft():
    rule = Rule(2, "Always mention NIM", "phrase", {"required": ["NIM"]})
    assert not run_lesson_test(rule, _draft("Margins rose.")).passed
    assert run_lesson_test(rule, _draft("Margins rose.").units[0]).passed  # a single unit is not checked for it


def test_structure_lesson_on_chart_points_and_sections():
    eight = Rule(3, "Charts show eight quarters", "structure", {"min_chart_points": 8})
    assert not run_lesson_test(eight, _draft(points=6)).passed
    assert run_lesson_test(eight, _draft(points=8)).passed
    risks = Rule(4, "Always a risks section", "structure", {"required_sections": ["Risks"]})
    assert not run_lesson_test(risks, _draft()).passed
    assert run_lesson_test(risks, _draft(titles=("Results highlights", "Risks"))).passed


def test_judged_lesson_uses_the_judge_or_is_skipped():
    rule = Rule(5, "Lead with the margin story", "judged", {"rubric": "Does it lead with margins?"})
    assert run_lesson_test(rule, _draft()).skipped
    assert not run_lesson_test(rule, _draft(), judge=lambda rubric, text: False).passed


class FakeClaude:
    model = "fake"
    small_model = "fake-small"

    def __init__(self, lessons):
        self.lessons = lessons
        self.seen: list[str] = []

    def create_json(self, purpose, schema, **kwargs):
        self.seen.append(kwargs["messages"][0]["content"])
        return {"lessons": self.lessons}


def _raw(text, kind="phrase", banned=(), required=(), sections=(), points=None, rubric=""):
    return {"text": text, "test_kind": kind, "banned": list(banned), "required": list(required), "required_sections": list(sections), "min_chart_points": points, "rubric": rubric}


def test_proposals_are_cleaned_and_never_teach_a_rating():
    claude = FakeClaude(
        [
            _raw("Never call margins robust", banned=["robust"]),
            _raw("Always rate it Buy", banned=["sell"]),  # a rating lesson: dropped
            _raw("Phrase rule with no phrase"),  # no test: dropped
            _raw("Charts show eight quarters", kind="structure", points=8),
            _raw("Lead with the margin story", kind="judged", rubric="Does it lead with margins?"),
        ]
    )
    found = propose_lessons(claude, first_draft="We upgrade to Buy, TP 900.", requests=["make it shorter"], approved="a", published="b", existing=[])
    assert [p.text for p in found] == ["Never call margins robust", "Charts show eight quarters", "Lead with the margin story"]
    assert "Buy" not in claude.seen[0] and "900" not in claude.seen[0]  # masked before the model saw it


def test_a_repeat_strengthens_the_lesson_instead_of_adding_one(db, analyst):
    first = add_or_strengthen(db, analyst.id, Proposal("Never call margins robust", "phrase", {"banned": ["robust"]}), None)
    again = add_or_strengthen(db, analyst.id, Proposal("Never call margins ROBUST!", "phrase", {"banned": ["robust"]}), None)
    assert again.id == first.id and again.strength == 2
    assert db.query(Lesson).filter_by(owner_id=analyst.id).count() == 1


@pytest.fixture
def published(db, store, analyst):
    co = Company(nse_symbol="LEARNCO", name="Learn Co Limited", isin="INE000L01011")
    db.add(co)
    db.flush()
    thread = create_thread(db, analyst.id, co.id, "quarterly", "word", "standalone", date(2026, 9, 30))
    draft = _draft()
    save_version(db, store, thread, draft, "first_draft", 0, None)
    save_version(db, store, thread, _draft("Margins steady."), "approved", 1, analyst.id)
    thread.status = "approved"
    db.flush()
    final = build_docx(_draft("Margins steady. We rate it Buy."), None)
    return thread, publish(db, store, analyst.id, write_report_tag(final, ReportTag(thread.id, 2)), "final.docx", "upload", thread_id=thread.id)


def test_learning_from_a_published_report_adds_lessons_for_its_analyst(db, store, analyst, published):
    thread, pf = published
    claude = FakeClaude([_raw("Keep paragraphs short", kind="judged", rubric="Are paragraphs short?")])
    added = learn_from_published(db, store, claude, pf.id)
    assert [(lesson.text, lesson.owner_id, lesson.source_thread_id) for lesson in added] == [("Keep paragraphs short", analyst.id, thread.id)]
    assert "Buy" not in claude.seen[0]
