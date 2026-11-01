"""Multi-turn Q&A over a company's filings (design doc 11.1, 19.1; report chat design).

Each answer runs the grounded tool loop with the question and the thread's earlier turns. An answer
with a number no tool returned is withheld and its numbers shown (rule 3), as in the report chat.
Page citations such as [filing:4 page:7] are collected for the page to link. One question at a time
per thread: the thread is claimed while the AI answers. Q&A never feeds lessons.
"""

import re
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from analekh.config import get_settings
from analekh.db.models import Company, QaMessage, QaThread
from analekh.genai.reports import PROMPTS, SYSTEM, run_report
from analekh.reports.sections import style_problems

log = structlog.get_logger()
_CITE = re.compile(r"\[filing:(\d+) page:(\d+)\]")
WITHHELD = "Answer withheld: it contained numbers that could not be sourced."
FAILED = "The AI could not answer that. Try again."


class QaNotFound(Exception):
    pass


class QaBusy(Exception):
    pass


def _busy_for() -> timedelta:
    cfg = get_settings()
    return timedelta(seconds=cfg.chat_turn_timeout_s + cfg.chat_busy_grace_s)


def is_busy(t: QaThread) -> bool:
    return t.busy_since is not None and datetime.now(UTC) - t.busy_since < _busy_for()


def get_owned(db: Session, qa_id: int, owner_id: str) -> QaThread:
    t = db.scalars(select(QaThread).where(QaThread.id == qa_id, QaThread.owner_id == owner_id)).one_or_none()
    if t is None:
        raise QaNotFound
    return t


def claim(db: Session, qa_id: int, owner_id: str, job_id: str) -> None:
    res = db.execute(
        update(QaThread)
        .where(QaThread.id == qa_id, QaThread.owner_id == owner_id, or_(QaThread.busy_since.is_(None), QaThread.busy_since < func.now() - _busy_for()))
        .values(busy_since=func.now(), busy_job_id=job_id)
        .execution_options(synchronize_session=False)
    )
    if res.rowcount == 1:  # type: ignore[attr-defined]
        return
    get_owned(db, qa_id, owner_id)  # raises QaNotFound for someone else's thread
    raise QaBusy


def release(db: Session, qa_id: int, job_id: str) -> None:
    db.execute(update(QaThread).where(QaThread.id == qa_id, QaThread.busy_job_id == job_id).values(busy_since=None, busy_job_id=None).execution_options(synchronize_session=False))


def citations(text: str) -> list[dict[str, int]]:
    seen: dict[tuple[int, int], None] = {}
    for m in _CITE.finditer(text):
        seen[(int(m.group(1)), int(m.group(2)))] = None
    return [{"filing_id": f, "page": p} for f, p in seen]


def qa_turn(db: Session, claude: Any, executor: Any, thread: QaThread, question: str) -> QaMessage:
    company = db.get(Company, thread.company_id)
    assert company is not None
    rows = list(db.scalars(select(QaMessage).where(QaMessage.thread_id == thread.id).order_by(QaMessage.id.desc()).limit(get_settings().chat_history_messages)))
    history = "\n".join(f"{'Analyst' if m.role == 'analyst' else 'You'}: {m.body}" for m in reversed(rows))
    db.add(QaMessage(thread_id=thread.id, role="analyst", body=question))
    prompt = PROMPTS["qa"].format(question=question, company=company.nse_symbol)
    if history:
        prompt = f"Earlier in this chat:\n{history}\n\nNow:\n{prompt}"
    run = run_report(claude, executor, "qa", prompt=prompt, system_text=SYSTEM)
    problems = style_problems(run.text)
    blocked = run.blocked or bool(problems)
    meta = {"blocked": blocked, "unmatched": run.grounding.unmatched, "citations": [] if blocked else citations(run.text)}
    answer = QaMessage(thread_id=thread.id, role="ai", body=WITHHELD if blocked else run.text, meta=meta, model_used=getattr(claude, "model", None))
    db.add(answer)
    if not thread.title:
        thread.title = question[:120]
    thread.updated_at = datetime.now(UTC)
    db.flush()
    return answer


def do_qa_turn(db: Session, claude: Any, executor: Any, *, qa_id: int, question: str, user_id: str, job_id: str) -> None:
    thread = get_owned(db, qa_id, user_id)
    db.refresh(thread)
    if thread.busy_job_id != job_id:
        log.info("qa_turn_superseded", qa_id=qa_id)
        return
    try:
        with db.begin_nested():
            qa_turn(db, claude, executor, thread, question)
    except Exception as exc:  # noqa: BLE001
        log.warning("qa_turn_failed", qa_id=qa_id, error_type=type(exc).__name__)
        db.add(QaMessage(thread_id=qa_id, role="analyst", body=question))
        db.add(QaMessage(thread_id=qa_id, role="ai", body=FAILED, meta={"failed": True}))
    finally:
        release(db, qa_id, job_id)
