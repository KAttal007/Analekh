"""The upgrade check: may a candidate model replace the current one? (design: moving to a new model)

Both models redraft the first draft of past published reports. Each sees the same data: a tool call
the report made is answered from its recorded result; a call never recorded is answered live (when
allowed) and counted as `new_data`, reported but never a failure. Stored threads are never changed.

The candidate passes when it is no worse than the current model on every count (grounding
rejections, style problems, missing sections) and passes every lesson test the current model
passes. A lesson the current model already fails is reported, not blocking. Analyst lessons are
tested only on that analyst's reports, firm lessons on all. The current model judges 'judged'
lessons for both, never the candidate.
"""

import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from analekh.db.models import Company, LessonCheck, ReportThread, ThreadMessage
from analekh.ingest.storage import ObjectStore, unpack
from analekh.reports.draft import Draft, Unit
from analekh.reports.lessons import Judge, active_rules, run_lesson_test
from analekh.reports.outlines import outline
from analekh.reports.sections import draft_section

COUNTS = ("grounding_rejections", "style_problems", "missing_sections")


def _key(name: str, args: Any) -> str:
    return json.dumps([name, args], sort_keys=True, default=str)


class ReplayExecutor:
    """Answers recorded tool calls from the record; others live (if a live executor is given)."""

    def __init__(self, exchanges: list[dict[str, Any]], live: Any | None = None) -> None:
        self.recorded = {_key(e["tool"], e["input"]): e["result"] for e in exchanges}
        self.live = live
        self.new_data = 0

    def run(self, name: str, args: dict[str, Any]) -> Any:
        key = _key(name, args)
        if key in self.recorded:
            return self.recorded[key]
        self.new_data += 1
        if self.live is None:
            raise ValueError("this data was not recorded for the report")
        return self.live.run(name, args)


@dataclass
class Score:
    grounding_rejections: int = 0
    style_problems: int = 0
    missing_sections: int = 0
    new_data: int = 0
    passes: set[tuple[int, int]] = field(default_factory=set)  # (lesson id, thread id)
    tested: set[tuple[int, int]] = field(default_factory=set)


def first_draft_exchanges(db: Session, store: ObjectStore, thread: ReportThread) -> list[dict[str, Any]]:
    """The tool exchanges recorded when the thread's first draft was made."""
    key = db.scalars(select(ThreadMessage.trace_key).where(ThreadMessage.thread_id == thread.id, ThreadMessage.role == "ai", ThreadMessage.trace_key.is_not(None)).order_by(ThreadMessage.id)).first()
    if key is None:
        return []
    exchanges: list[dict[str, Any]] = json.loads(unpack(store.get(key))).get("exchanges", [])
    return exchanges


def score_model(db: Session, store: ObjectStore, claude: Any, threads: list[ReportThread], judge: Judge | None, live: Any | None) -> Score:
    score = Score()
    for thread in threads:
        company = db.get(Company, thread.company_id)
        assert company is not None
        rules = active_rules(db, thread.owner_id)
        executor = ReplayExecutor(first_draft_exchanges(db, store, thread), live)
        period = thread.quarter_end.isoformat() if thread.quarter_end else "the latest quarter"
        units: list[Unit] = []
        for title in outline(thread.report_type, thread.format):
            res = draft_section(claude, executor, company=company.nse_symbol, report_type=thread.report_type, period_end=period, title=title, model_id=thread.model_id, lessons=[r.text for r in rules])
            score.grounding_rejections += 1 if res.unmatched else 0
            score.style_problems += len(res.style)
            if res.unit is None:
                score.missing_sections += 1
            else:
                units.append(res.unit)
        score.new_data += executor.new_data
        draft = Draft(schema_version=1, format=thread.format, units=units)  # type: ignore[arg-type]
        for rule in rules:
            result = run_lesson_test(rule, draft, judge)
            if result.skipped:
                continue
            score.tested.add((rule.id, thread.id))
            if result.passed:
                score.passes.add((rule.id, thread.id))
    return score


@dataclass(frozen=True)
class CheckResult:
    verdict: str  # pass, fail
    current: dict[str, int]
    candidate: dict[str, int]
    worse_on: list[str]
    lessons_lost: list[tuple[int, int]]
    lessons_failed_by_both: list[tuple[int, int]]
    check_id: int


def _counts(s: Score) -> dict[str, int]:
    return {"grounding_rejections": s.grounding_rejections, "style_problems": s.style_problems, "missing_sections": s.missing_sections, "new_data": s.new_data}


def pick_threads(db: Session, limit: int) -> list[ReportThread]:
    """The firm's most recently published reports."""
    return list(db.scalars(select(ReportThread).where(ReportThread.status == "published").order_by(ReportThread.published_at.desc()).limit(limit)))


def check_candidate(
    db: Session,
    store: ObjectStore,
    current: Any,
    candidate: Any,
    threads: list[ReportThread],
    *,
    judge: Judge | None = None,
    live: Any | None = None,
) -> CheckResult:
    cur = score_model(db, store, current, threads, judge, live)
    cand = score_model(db, store, candidate, threads, judge, live)
    worse = [c for c in COUNTS if getattr(cand, c) > getattr(cur, c)]
    lost = sorted(cur.passes - cand.passes)
    both_failed = sorted((cur.tested - cur.passes) & (cand.tested - cand.passes))
    verdict = "pass" if not worse and not lost else "fail"
    results = {"current": _counts(cur), "candidate": _counts(cand), "worse_on": worse, "lessons_lost": lost, "lessons_failed_by_both": both_failed, "threads": [t.id for t in threads]}
    row = LessonCheck(current_model=str(getattr(current, "model", "?")), candidate_model=str(getattr(candidate, "model", "?")), threads_used=len(threads), results=results, verdict=verdict)
    db.add(row)
    db.flush()
    return CheckResult(verdict, _counts(cur), _counts(cand), worse, lost, both_failed, row.id)
