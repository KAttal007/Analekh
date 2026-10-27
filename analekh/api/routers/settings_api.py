"""Settings an admin edits in the app: the upload limit (auth design, section 7)."""

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from analekh.api.deps import DB, AdminUser, CurrentUser
from analekh.api.uploads import KEY, get_max_upload_bytes, mb
from analekh.config import get_settings
from analekh.db.models import AppSetting, AuditEntry

router = APIRouter(prefix="/settings", tags=["settings"])


class UploadLimitOut(BaseModel):
    bytes: int
    ceiling_bytes: int
    min_bytes: int
    updated_by: str | None
    updated_at: datetime | None
    # Not part of upload limit: the one settings reply every signed-in user reads, so web's lock
    # polling interval and idle-reminder wait ride along (settings.lock_poll_seconds,
    # idle_reminder_minutes).
    lock_poll_seconds: int
    idle_reminder_minutes: int


class UploadLimitIn(BaseModel):
    bytes: int


def _out(db: DB) -> UploadLimitOut:
    cfg = get_settings()
    row = db.get(AppSetting, KEY)
    return UploadLimitOut(
        bytes=get_max_upload_bytes(db),
        ceiling_bytes=cfg.max_upload_ceiling_bytes,
        min_bytes=cfg.min_upload_bytes,
        updated_by=row.updated_by if row else None,
        updated_at=row.updated_at if row else None,
        lock_poll_seconds=cfg.lock_poll_seconds,
        idle_reminder_minutes=cfg.idle_reminder_minutes,
    )


@router.get("/upload-limit", response_model=UploadLimitOut)
def read_upload_limit(db: DB, _: CurrentUser) -> UploadLimitOut:
    return _out(db)


@router.put("/upload-limit", response_model=UploadLimitOut)
def set_upload_limit(body: UploadLimitIn, db: DB, admin: AdminUser) -> UploadLimitOut:
    cfg = get_settings()
    if not cfg.min_upload_bytes <= body.bytes <= cfg.max_upload_ceiling_bytes:
        raise HTTPException(
            422,
            f"The limit must be between {mb(cfg.min_upload_bytes)} MB and "
            f"{mb(cfg.max_upload_ceiling_bytes)} MB.",
        )
    before = get_max_upload_bytes(db)
    row = db.get(AppSetting, KEY)
    if row is None:
        db.add(AppSetting(key=KEY, value={"bytes": body.bytes}, updated_by=admin.id))
    else:
        row.value = {"bytes": body.bytes}
        row.updated_by = admin.id
        row.updated_at = datetime.now().astimezone()
    db.add(
        AuditEntry(
            user_id=admin.id,
            action="upload_limit_changed",
            detail={"from": before, "to": body.bytes},
        )
    )
    db.commit()
    return _out(db)
