"""Lessons the AI has learnt (design: lessons). An analyst sees and manages their own; everyone sees
the firm's; only admins change a firm lesson or promote an analyst's lesson to the firm. A lesson
someone else owns answers 404, exactly like a missing one."""

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from analekh.api import schemas
from analekh.api.deps import DB, AdminUser, CurrentUser
from analekh.db.models import Lesson
from analekh.reports.mask import mask_text

router = APIRouter(tags=["lessons"])


class LessonPatch(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=300)
    status: Literal["active", "retired"] | None = None


def _out(row: Lesson, user_id: str) -> schemas.LessonOut:
    return schemas.LessonOut(
        id=row.id,
        text=row.text,
        scope=row.scope,
        status=row.status,
        test_kind=row.test_kind,
        test_spec=row.test_spec,
        strength=row.strength,
        source_thread_id=row.source_thread_id if row.owner_id == user_id else None,
        mine=row.owner_id == user_id and row.scope == "analyst",
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _editable(db: DB, lesson_id: int, user: CurrentUser) -> Lesson:
    row = db.get(Lesson, lesson_id)
    if row is None or not ((row.scope == "analyst" and row.owner_id == user.id) or (row.scope == "firm" and user.role == "admin")):
        raise HTTPException(404, "Lesson not found.")
    return row


@router.get("/lessons")
def list_lessons(db: DB, user: CurrentUser) -> list[schemas.LessonOut]:
    rows = db.scalars(select(Lesson).where((Lesson.scope == "firm") | (Lesson.owner_id == user.id)).order_by(Lesson.status, Lesson.strength.desc(), Lesson.id).limit(500))
    return [_out(r, user.id) for r in rows]


@router.patch("/lessons/{lesson_id}")
def edit_lesson(lesson_id: int, body: LessonPatch, db: DB, user: CurrentUser) -> schemas.LessonOut:
    row = _editable(db, lesson_id, user)
    if body.text is not None:
        if mask_text(body.text).hits:
            raise HTTPException(422, "A lesson cannot be about ratings or target prices.")
        row.text = body.text.strip()
    if body.status is not None:
        row.status = body.status
    row.updated_at = datetime.now(UTC)
    db.flush()
    return _out(row, user.id)


@router.delete("/lessons/{lesson_id}", status_code=204)
def delete_lesson(lesson_id: int, db: DB, user: CurrentUser) -> None:
    db.delete(_editable(db, lesson_id, user))
    db.flush()


@router.post("/lessons/{lesson_id}/promote")
def promote_lesson(lesson_id: int, db: DB, admin: AdminUser) -> schemas.LessonOut:
    """Make an analyst's lesson apply to every analyst in the firm."""
    row = db.get(Lesson, lesson_id)
    if row is None:
        raise HTTPException(404, "Lesson not found.")
    row.scope = "firm"
    row.updated_at = datetime.now(UTC)
    db.flush()
    return _out(row, admin.id)
