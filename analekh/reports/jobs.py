"""The work behind a thread's AI jobs, as plain functions (the Celery wrappers are in
analekh/jobs/report_tasks.py). Each releases the draft when it ends, success or not, and never writes
the cause of a failure into the chat (no draft text or model output in logs or errors, rule 11)."""

import structlog
from sqlalchemy.orm import Session

from analekh.db.models import Company, ReportThread, ThreadMessage
from analekh.ingest.storage import ObjectStore
from analekh.reports.chat import Selection, add_ai_message, run_turn
from analekh.reports.draft import Block, Draft, Paragraph, Placeholder, Unit
from analekh.reports.lessons import active_rules, example_reports, run_lesson_test
from analekh.reports.outlines import outline
from analekh.reports.sections import draft_section
from analekh.reports.store import save_version
from analekh.reports.threads import get_owned, release

log = structlog.get_logger()

NOT_DRAFTED = "This section was not drafted because some figures could not be sourced. Ask the AI to try it again."
RATING_UNIT = "Rating, target price and guidance"
FAILED_REPLY = "The AI could not finish that. Nothing was changed. Try again."


def do_chat_turn(
    db: Session,
    store: ObjectStore,
    claude: object,
    executor: object,
    *,
    thread_id: int,
    message: str,
    selection: Selection | None,
    user_id: str,
    job_id: str,
) -> None:
    thread = get_owned(db, thread_id, user_id)
    db.refresh(thread)  # the claim was written by a plain UPDATE; never trust a cached copy
    if thread.busy_job_id != job_id:  # started too late: the claim expired and a newer job holds the draft
        log.info("chat_turn_superseded", thread_id=thread_id)
        return
    try:
        with db.begin_nested():  # a failed turn undoes only its own work
            run_turn(db, store, claude, executor, thread, message, selection, user_id, active_rules(db, user_id))
    except Exception as exc:  # noqa: BLE001 - any failure frees the draft and tells the analyst
        log.warning("chat_turn_failed", thread_id=thread_id, error_type=type(exc).__name__)
        thread = get_owned(db, thread_id, user_id)
        db.add(ThreadMessage(thread_id=thread.id, role="analyst", body=message))
        db.add(ThreadMessage(thread_id=thread.id, role="ai", body=FAILED_REPLY, meta={"failed": True}))
    finally:
        release(db, thread_id, job_id)


def do_first_draft(db: Session, store: ObjectStore, claude: object, executor: object, *, thread_id: int, user_id: str, job_id: str) -> None:
    thread = get_owned(db, thread_id, user_id)
    db.refresh(thread)  # the claim was written by a plain UPDATE; never trust a cached copy
    if thread.busy_job_id != job_id:
        log.info("first_draft_superseded", thread_id=thread_id)
        return
    try:
        with db.begin_nested():
            _first_draft(db, store, claude, executor, thread, user_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("first_draft_failed", thread_id=thread_id, error_type=type(exc).__name__)
        thread = get_owned(db, thread_id, user_id)
        db.add(ThreadMessage(thread_id=thread.id, role="ai", body=FAILED_REPLY, meta={"failed": True}))
    finally:
        release(db, thread_id, job_id)


def _first_draft(db: Session, store: ObjectStore, claude: object, executor: object, thread: ReportThread, user_id: str) -> None:
    company = db.get(Company, thread.company_id)
    assert company is not None
    period = thread.quarter_end.isoformat() if thread.quarter_end else "the latest quarter"
    rules = active_rules(db, user_id)
    lessons = [r.text for r in rules]
    examples = example_reports(db, store, user_id, thread.report_type, thread.id)
    shown = ("Earlier reports by this analyst, for tone and structure only (never copy their figures):\n" + "\n---\n".join(examples)) if examples else None
    units: list[Unit] = []
    blocked: list[dict[str, object]] = []
    calls: list[dict[str, object]] = []
    results: list[object] = []
    exchanges: list[dict[str, object]] = []
    for index, title in enumerate(outline(thread.report_type, thread.format)):
        feedback: str | None = None
        for _attempt in range(2):  # one retry when the section breaks a lesson
            extra = "\n\n".join(x for x in (shown, feedback) if x) or None
            res = draft_section(claude, executor, company=company.nse_symbol, report_type=thread.report_type, period_end=period, title=title, model_id=thread.model_id, lessons=lessons, extra=extra)
            calls += res.tool_calls
            results += res.results
            exchanges += res.exchanges
            broken = [r for r in rules if r.kind in ("phrase", "structure") and res.unit is not None and not run_lesson_test(r, res.unit).passed]
            if not broken:
                break
            feedback = "Your last version broke the analyst's rules. Write it again and follow them:\n" + "\n".join(f"- {r.text}" for r in broken)
        if res.unit is None or broken:
            blocked.append({"unit": index, "unmatched": res.unmatched, "style": res.style, "lessons": [r.id for r in broken]})
            units.append(Unit(title=title, blocks=[Paragraph(type="paragraph", text=NOT_DRAFTED)]))
        else:
            units.append(res.unit)
    marks: list[Block] = [Placeholder(type="placeholder", kind=k) for k in ("rating", "target", "guidance")]
    units.append(Unit(title=RATING_UNIT, blocks=marks))
    version = save_version(db, store, thread, Draft(schema_version=1, format=thread.format, units=units), "first_draft", 0, None)  # type: ignore[arg-type]
    body = "Here is the first draft." + (f" {len(blocked)} section(s) could not be drafted." if blocked else "")
    add_ai_message(
        db,
        store,
        thread,
        body=body,
        meta={"version_no": version.version_no, "blocked": blocked, "changed_units": list(range(len(units)))},
        model_used=getattr(claude, "model", None),
        prompt=f"first draft:{thread.id}",
        tool_calls=calls,  # type: ignore[arg-type]
        results=results,
        exchanges=exchanges,  # type: ignore[arg-type]
    )
