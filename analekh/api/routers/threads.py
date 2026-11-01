"""Report threads: draft in chat, typed edits, approval (design: report chat).

Every route is reached only by a signed-in user (main.py) and every thread is looked up by its
owner, so someone else's thread answers 404 exactly like a missing one. The AI works in a background
job; while it runs the draft is read-only (409 thread_busy)."""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import select

from analekh.api import schemas
from analekh.api.deps import DB, Store, User, company_or_404, job
from analekh.api.uploads import read_limited
from analekh.config import get_settings
from analekh.db.models import Company, Model, ReportThread, ThreadMessage
from analekh.reports.build import build_file
from analekh.reports.chat import thread_results
from analekh.reports.draft import DraftError, draft_text, parse_draft, to_json
from analekh.reports.ooxml import PackageRefused
from analekh.reports.publish import PublishRefused, publish
from analekh.reports.sourced import unsourced_numbers
from analekh.reports.store import StaleVersion, ThreadFrozen, load_draft, save_version
from analekh.reports.threads import ThreadBusy, ThreadNotFound, claim, create_thread, get_owned, is_busy, release

log = structlog.get_logger()
router = APIRouter(tags=["threads"])


@contextmanager
def _errors() -> Iterator[None]:
    try:
        yield
    except ThreadNotFound:
        raise HTTPException(404, "Report not found.") from None
    except ThreadBusy:
        raise HTTPException(409, {"code": "thread_busy", "message": "The AI is still writing."}) from None
    except StaleVersion:
        raise HTTPException(409, {"code": "stale_version", "message": "The draft has changed since you opened it."}) from None
    except ThreadFrozen:
        raise HTTPException(409, {"code": "thread_frozen", "message": "This report is approved and can no longer be edited here."}) from None
    except DraftError as exc:
        raise HTTPException(422, str(exc)) from None


def _summary(db: DB, t: ReportThread, company: Company) -> schemas.ThreadSummary:
    return schemas.ThreadSummary(
        id=t.id,
        symbol=company.nse_symbol,
        company_name=company.name,
        report_type=t.report_type,
        format=t.format,
        quarter_end=t.quarter_end,
        status=t.status,
        busy=is_busy(t),
        updated_at=t.updated_at,
    )


@router.post("/threads")
def start_thread(body: schemas.ThreadCreate, db: DB, user: User) -> schemas.ThreadStarted:
    """Start a report and queue its first draft. An initiating report needs the analyst's model."""
    company = company_or_404(db, body.symbol)
    if body.report_type == "initiating" and body.model_id is None:
        raise HTTPException(422, "An initiating report needs your model (model_id).")
    if body.model_id is not None:
        model = db.get(Model, body.model_id)
        if model is None or model.company_id != company.id:
            raise HTTPException(404, "Model not found for this company.")
    thread = create_thread(db, user, company.id, body.report_type, body.format, body.basis, body.quarter_end, body.model_id)
    job_id = uuid.uuid4().hex
    with _errors():
        claim(db, thread.id, user, 0, job_id)
    db.commit()  # the claim must be visible before the job can start
    from analekh.jobs import report_tasks

    try:
        job(report_tasks.generate_first_draft, thread.id, user, task_id=job_id)
    except HTTPException:  # queue is down: leave nothing half-made
        db.delete(thread)
        db.commit()
        raise
    return schemas.ThreadStarted(thread_id=thread.id, job_id=job_id)


@router.get("/threads")
def my_threads(db: DB, user: User) -> list[schemas.ThreadSummary]:
    rows = db.execute(select(ReportThread, Company).join(Company, Company.id == ReportThread.company_id).where(ReportThread.owner_id == user).order_by(ReportThread.updated_at.desc()).limit(200)).all()
    return [_summary(db, t, c) for t, c in rows]


@router.get("/threads/{thread_id}")
def get_thread(thread_id: int, db: DB, store: Store, user: User) -> schemas.ThreadOut:
    with _errors():
        thread = get_owned(db, thread_id, user)
    company = db.get(Company, thread.company_id)
    assert company is not None
    draft = None
    unsourced: list[str] = []
    if thread.current_version:
        loaded = load_draft(db, store, thread)
        draft = to_json(loaded)
        unsourced = unsourced_numbers(db, thread, draft_text(loaded), thread_results(db, store, thread))
    msgs = list(db.scalars(select(ThreadMessage).where(ThreadMessage.thread_id == thread.id).order_by(ThreadMessage.id.desc()).limit(get_settings().chat_page_messages)))
    return schemas.ThreadOut(
        **_summary(db, thread, company).model_dump(),
        basis=thread.basis,
        current_version=thread.current_version,
        draft=draft,
        unsourced=unsourced,
        messages=[schemas.ThreadMessageOut.model_validate(m) for m in reversed(msgs)],
    )


@router.post("/threads/{thread_id}/messages")
def send_message(thread_id: int, body: schemas.MessageIn, db: DB, user: User) -> schemas.JobStarted:
    """Ask the AI about the draft or to change it. The draft is locked until the reply is finished."""
    if len(body.message) > get_settings().chat_message_max_chars:
        raise HTTPException(422, "That message is too long.")
    job_id = uuid.uuid4().hex
    with _errors():
        claim(db, thread_id, user, body.base_version, job_id)
    db.commit()
    from analekh.jobs import report_tasks

    selection = body.selection.model_dump() if body.selection else None
    try:
        job(report_tasks.run_chat_turn, thread_id, body.message, selection, user, task_id=job_id)
    except HTTPException:
        release(db, thread_id, job_id)
        db.commit()
        raise
    return schemas.JobStarted(job_id=job_id)


@router.put("/threads/{thread_id}/draft")
def save_draft(thread_id: int, body: schemas.DraftIn, db: DB, store: Store, user: User) -> schemas.DraftSaved:
    """The analyst's own edit. Numbers that match no source are returned for marking, not refused."""
    with _errors():
        thread = get_owned(db, thread_id, user, for_update=True)
        if is_busy(thread):
            raise ThreadBusy
        draft = parse_draft(body.draft)
        if draft.format != thread.format:
            raise DraftError("the draft's format does not match the report")
        row = save_version(db, store, thread, draft, "analyst_edit", body.base_version, user)
        unsourced = unsourced_numbers(db, thread, draft_text(draft), thread_results(db, store, thread))
    return schemas.DraftSaved(version_no=row.version_no, unsourced=unsourced)


@router.post("/threads/{thread_id}/approve")
def approve(thread_id: int, body: schemas.ApproveIn, db: DB, store: Store, user: User) -> schemas.Approved:
    """Freeze the draft. From here the analyst works in the file."""
    with _errors():
        thread = get_owned(db, thread_id, user, for_update=True)
        if is_busy(thread):
            raise ThreadBusy
        if thread.current_version == 0:
            raise HTTPException(409, {"code": "nothing_to_approve", "message": "There is no draft yet."})
        draft = load_draft(db, store, thread)
        row = save_version(db, store, thread, draft, "approved", body.base_version, user)
        count = len(unsourced_numbers(db, thread, draft_text(draft), thread_results(db, store, thread)))
        thread.status = "approved"
        thread.approved_at = datetime.now(UTC)
        db.flush()
    return schemas.Approved(version_no=row.version_no, unsourced_count=count)


@router.get("/threads/{thread_id}/file")
def download_file(thread_id: int, db: DB, store: Store, user: User) -> Response:
    """The approved draft as a Word or PowerPoint file, on the sector's template when there is one."""
    with _errors():
        thread = get_owned(db, thread_id, user)
    if thread.status not in ("approved", "published"):
        raise HTTPException(409, {"code": "not_approved", "message": "Approve the draft first."})
    try:
        built = build_file(db, store, thread)
    except PackageRefused as exc:
        raise HTTPException(409, {"code": "template_unusable", "message": f"The template for this sector could not be used. {exc}"}) from None
    headers = {"Content-Disposition": f'attachment; filename="{built.filename}"', "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
    return Response(built.data, media_type=built.mime, headers=headers)


def _learn(db: DB, published_id: int) -> None:
    """Queue the lesson job. Publishing never fails because the queue is down; `analekh ai learn` reruns it."""
    db.commit()  # the job reads the published file in its own session
    from analekh.jobs import report_tasks

    try:
        job(report_tasks.learn_from_publish, published_id)
    except HTTPException:
        log.warning("learning_not_queued", published_id=published_id)


def _published(fn):  # type: ignore[no-untyped-def]
    try:
        return fn()
    except PublishRefused as exc:
        raise HTTPException(422, {"code": exc.code, "message": exc.message}) from None


@router.post("/threads/{thread_id}/publish")
def publish_upload(
    thread_id: int,
    db: DB,
    store: Store,
    user: User,
    file: Annotated[UploadFile, File()],
    confirmed: Annotated[bool, Form()] = False,
) -> schemas.PublishedOut:
    """Publish the final file from the report's page. A file without the report tag needs `confirmed`."""
    with _errors():
        get_owned(db, thread_id, user)  # someone else's report is a 404 before anything is read
    data = read_limited(db, file)
    row = _published(lambda: publish(db, store, user, data, file.filename, "upload", thread_id=thread_id, confirmed=confirmed))
    _learn(db, row.id)
    return schemas.PublishedOut.model_validate(row)


@router.post("/publish")
def publish_tagged(db: DB, store: Store, user: User, file: Annotated[UploadFile, File()]) -> schemas.PublishedOut:
    """Publish a file that carries its report tag (the Word and PowerPoint add-in's route)."""
    data = read_limited(db, file)
    row = _published(lambda: publish(db, store, user, data, file.filename, "addin"))
    _learn(db, row.id)
    return schemas.PublishedOut.model_validate(row)


@router.get("/threads/{thread_id}/versions/{version_no}")
def get_version(thread_id: int, version_no: int, db: DB, store: Store, user: User) -> schemas.VersionOut:
    """An earlier state of the draft, for one-click undo of an AI change."""
    with _errors():
        thread = get_owned(db, thread_id, user)
    if not 1 <= version_no <= thread.current_version:
        raise HTTPException(404, "No such version.")
    return schemas.VersionOut(version_no=version_no, draft=to_json(load_draft(db, store, thread, version_no)))
