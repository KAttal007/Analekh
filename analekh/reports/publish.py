"""The publish step, shared by the upload route and the Word/PowerPoint add-in (design: publish routes).

The file must be safe to read (office_read.py), match the thread's format, and carry the tag of a
thread the user owns that is approved or already published. A file with no tag is accepted only on
the thread's own page and only once the analyst confirms it belongs there. Someone else's tag reads
exactly like an unknown one. The original bytes are kept as received, macro part included.
"""

import gzip
import json
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from analekh.db.models import PublishedFile, ReportThread
from analekh.ingest.storage import ObjectStore, sha256
from analekh.reports.office_read import read_package
from analekh.reports.ooxml import PackageRefused
from analekh.reports.tag import read_report_tag
from analekh.reports.threads import ThreadNotFound, get_owned
from analekh.templates.files import FILE_TYPES, suffix_of

FORMATS = {"word": (".docx", ".docm"), "ppt": (".pptx", ".pptm")}
ROUTES = ("upload", "addin")


class PublishRefused(ValueError):
    """Why a file was not published. `message` is safe to show; it never repeats file content."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _thread(db: Session, owner_id: str, thread_id: int | None, tagged: int | None, confirmed: bool) -> ReportThread:
    if thread_id is None:
        if tagged is None:
            raise PublishRefused("no_tag", "This file has no Analekh report tag. Publish it from its report's page.")
        thread_id = tagged
    elif tagged is None and not confirmed:
        raise PublishRefused("no_tag", "This file has no Analekh report tag. Confirm it belongs to this report.")
    elif tagged is not None and tagged != thread_id:
        raise PublishRefused("tag_mismatch", "This file belongs to another report.")
    try:
        return get_owned(db, thread_id, owner_id, for_update=True)
    except ThreadNotFound:
        raise PublishRefused("tag_mismatch", "This file belongs to another report.") from None


def publish(
    db: Session,
    store: ObjectStore,
    owner_id: str,
    data: bytes,
    filename: str | None,
    route: str,
    *,
    thread_id: int | None = None,
    confirmed: bool = False,
) -> PublishedFile:
    if route not in ROUTES:
        raise ValueError("unknown publish route")
    suffix = suffix_of(filename)
    try:
        text = read_package(data, filename)  # type, limits and safe parsing first
        tag = read_report_tag(data)
    except PackageRefused as exc:
        raise PublishRefused("unusable", str(exc)) from None
    thread = _thread(db, owner_id, thread_id, tag.thread_id if tag else None, confirmed)
    if thread.status not in ("approved", "published"):
        raise PublishRefused("not_approved", "Approve the draft before publishing.")
    if suffix not in FORMATS[thread.format]:
        want = " or ".join(FORMATS[thread.format])
        raise PublishRefused("wrong_format", f"This report is published as {want}.")
    digest = sha256(data)
    key = f"published/{thread.id}/{digest}{suffix}"
    store.put(key, data, FILE_TYPES[suffix].mime)
    text_key = f"published/{thread.id}/{digest}.text.json.gz"
    store.put(text_key, gzip.compress(json.dumps(asdict(text)).encode(), mtime=0))
    row = PublishedFile(
        thread_id=thread.id,
        file_sha256=digest,
        storage_key=key,
        original_name=(filename or "")[-200:],
        extension=suffix,
        has_macros=text.has_macros,
        route=route,
        uploaded_by_id=owner_id,
        text_key=text_key,
    )
    db.add(row)
    thread.status = "published"
    thread.published_at = datetime.now(UTC)
    db.flush()
    return row
