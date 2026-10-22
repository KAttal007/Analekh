"""The one upload-size rule (auth design, section 7). Every route that accepts a file reads it
through `read_limited`, so a limit set in the app covers every upload, now and later.

It applies to new uploads only; stored files are never touched when the limit changes.
"""

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from analekh.config import get_settings
from analekh.db.models import AppSetting

KEY = "max_upload_bytes"
CHUNK = 1024 * 1024
MB = 1024 * 1024


def get_max_upload_bytes(db: Session) -> int:
    """The limit in bytes: the admin's value, else the default; never above the ceiling."""
    cfg = get_settings()
    row = db.get(AppSetting, KEY)
    value = int(row.value["bytes"]) if row is not None else cfg.max_upload_default_bytes
    return min(value, cfg.max_upload_ceiling_bytes)


def mb(size: int) -> str:
    """Whole megabytes where exact, else one decimal: 25 -> "25", 26.2 -> "26.2"."""
    value = size / MB
    return f"{value:.0f}" if value == int(value) else f"{value:.1f}"


def read_limited(db: Session, upload: UploadFile) -> bytes:
    """Read an upload, refusing one over the limit. Reading stops just past the limit, so a file
    whose declared size is wrong cannot make the server read all of it."""
    limit = get_max_upload_bytes(db)
    parts: list[bytes] = []
    total = 0
    while True:
        chunk = upload.file.read(CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            size = upload.size if upload.size is not None else total
            raise HTTPException(
                413, f"This file is {mb(size)} MB; the limit is {mb(limit)} MB. Ask your admin."
            )
        parts.append(chunk)
    return b"".join(parts)
