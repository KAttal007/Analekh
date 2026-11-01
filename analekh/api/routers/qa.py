"""Q&A threads: a multi-turn chat over one company's filings. Owner-only, like report threads;
someone else's thread answers 404. One question at a time (409 while the AI answers)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from analekh.api import schemas
from analekh.api.deps import DB, User, company_or_404, job
from analekh.config import get_settings
from analekh.db.models import Company, QaMessage, QaThread
from analekh.genai.qa_chat import QaBusy, QaNotFound, claim, get_owned, is_busy, release

router = APIRouter(tags=["qa"])


class QaStart(BaseModel):
    symbol: Annotated[str, Field(min_length=1, max_length=40)]


class QaAsk(BaseModel):
    question: Annotated[str, Field(min_length=1)]


def _summary(t: QaThread, c: Company) -> schemas.QaSummary:
    return schemas.QaSummary(id=t.id, symbol=c.nse_symbol, company_name=c.name, title=t.title, busy=is_busy(t), updated_at=t.updated_at)


def _owned(db: DB, qa_id: int, user: str) -> QaThread:
    try:
        return get_owned(db, qa_id, user)
    except QaNotFound:
        raise HTTPException(404, "Chat not found.") from None


@router.post("/qa/threads")
def start_qa(body: QaStart, db: DB, user: User) -> schemas.QaSummary:
    company = company_or_404(db, body.symbol)
    t = QaThread(owner_id=user, company_id=company.id)
    db.add(t)
    db.flush()
    db.refresh(t)
    return _summary(t, company)


@router.get("/qa/threads")
def my_qa(db: DB, user: User) -> list[schemas.QaSummary]:
    rows = db.execute(select(QaThread, Company).join(Company, Company.id == QaThread.company_id).where(QaThread.owner_id == user).order_by(QaThread.updated_at.desc()).limit(200)).all()
    return [_summary(t, c) for t, c in rows]


@router.get("/qa/threads/{qa_id}")
def get_qa(qa_id: int, db: DB, user: User) -> schemas.QaOut:
    t = _owned(db, qa_id, user)
    company = db.get(Company, t.company_id)
    assert company is not None
    msgs = list(db.scalars(select(QaMessage).where(QaMessage.thread_id == t.id).order_by(QaMessage.id.desc()).limit(get_settings().chat_page_messages)))
    return schemas.QaOut(**_summary(t, company).model_dump(), messages=[schemas.QaMessageOut.model_validate(m) for m in reversed(msgs)])


@router.post("/qa/threads/{qa_id}/messages")
def ask(qa_id: int, body: QaAsk, db: DB, user: User) -> schemas.JobStarted:
    if len(body.question) > get_settings().qa_question_max_chars:
        raise HTTPException(422, "That question is too long.")
    job_id = uuid.uuid4().hex
    try:
        claim(db, qa_id, user, job_id)
    except QaNotFound:
        raise HTTPException(404, "Chat not found.") from None
    except QaBusy:
        raise HTTPException(409, {"code": "thread_busy", "message": "The AI is still answering."}) from None
    db.commit()
    from analekh.jobs import report_tasks

    try:
        job(report_tasks.run_qa_turn, qa_id, body.question, user, task_id=job_id)
    except HTTPException:
        release(db, qa_id, job_id)
        db.commit()
        raise
    return schemas.JobStarted(job_id=job_id)
