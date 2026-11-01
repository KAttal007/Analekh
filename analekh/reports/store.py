"""Versioned storage of a thread's draft.

The first draft and the approved draft are stored in full; versions between are stored as the unit
changes against the version before (old and new text of each changed unit, so a change can be read
either way). Bodies are gzipped JSON in object storage, keyed by thread, version and hash; the
database holds the index row and the hash of the body, checked on every read (fail closed).
"""

import gzip
import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from analekh.db.models import ReportThread, ReportVersion
from analekh.ingest.storage import ObjectStore, sha256, unpack
from analekh.reports.draft import Draft, parse_draft, to_json


class StaleVersion(Exception):
    """The save was made against a version that is no longer the current one."""


class ThreadFrozen(Exception):
    """The thread is approved or published; its draft no longer changes."""


class VersionCorrupt(Exception):
    """A stored body no longer matches its recorded hash."""


def _dump(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _diff(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    ou, nu = old["units"], new["units"]
    changes = []
    for i in range(max(len(ou), len(nu))):
        before = ou[i] if i < len(ou) else None
        after = nu[i] if i < len(nu) else None
        if before != after:
            changes.append({"i": i, "before": before, "after": after})
    return {"kind": "patch", "length": len(nu), "changes": changes}


def _apply(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    units: list[Any] = list(base["units"])
    del units[patch["length"] :]
    units.extend([None] * (patch["length"] - len(units)))
    for ch in patch["changes"]:
        if ch["i"] < patch["length"]:
            units[ch["i"]] = ch["after"]
    return {**base, "units": units}


def _read(store: ObjectStore, row: ReportVersion) -> dict[str, Any]:
    raw = unpack(store.get(row.storage_key))
    if sha256(raw) != row.body_sha256:
        raise VersionCorrupt("stored version does not match its hash")
    body: dict[str, Any] = json.loads(raw)
    return body


def load_draft(db: Session, store: ObjectStore, thread: ReportThread, version_no: int | None = None) -> Draft:
    """The draft at `version_no` (default: the current one), rebuilt from the nearest full version."""
    target = thread.current_version if version_no is None else version_no
    rows = list(db.scalars(select(ReportVersion).where(ReportVersion.thread_id == thread.id, ReportVersion.version_no <= target).order_by(ReportVersion.version_no)))
    if not rows or rows[-1].version_no != target:
        raise LookupError("no such version")
    start = max(i for i, r in enumerate(rows) if r.full)
    current: dict[str, Any] = _read(store, rows[start])["draft"]
    for row in rows[start + 1 :]:
        current = _apply(current, _read(store, row))
    return parse_draft(current)


def save_version(
    db: Session,
    store: ObjectStore,
    thread: ReportThread,
    draft: Draft,
    trigger: str,
    parent_no: int,
    by_user_id: str | None,
) -> ReportVersion:
    """Save `draft` as the next version. `parent_no` is the version the editor was looking at; if it is
    no longer current the save is refused (StaleVersion). Saving the current draft again changes nothing."""
    db.flush()  # a pending status change must not be lost by the reload below
    db.refresh(thread, with_for_update=True)  # one writer at a time, even across processes
    if thread.status != "drafting":
        raise ThreadFrozen("the thread is no longer being drafted")
    if parent_no != thread.current_version:
        raise StaleVersion("the draft has changed since you opened it")
    new = to_json(draft)
    if trigger != "approved" and thread.current_version and to_json(load_draft(db, store, thread)) == new:
        return db.scalars(select(ReportVersion).where(ReportVersion.thread_id == thread.id, ReportVersion.version_no == thread.current_version)).one()
    number = thread.current_version + 1
    full = number == 1 or trigger == "approved"
    body = {"kind": "full", "draft": new} if full else _diff(to_json(load_draft(db, store, thread)), new)
    raw = _dump(body)
    digest = sha256(raw)
    key = f"reports/{thread.id}/v{number}-{digest[:12]}.json.gz"
    store.put(key, gzip.compress(raw, mtime=0))
    row = ReportVersion(
        thread_id=thread.id,
        version_no=number,
        parent_no=parent_no or None,
        trigger=trigger,
        by_user_id=by_user_id,
        storage_key=key,
        body_sha256=digest,
        full=full,
    )
    db.add(row)
    thread.current_version = number
    thread.updated_at = func.now()
    db.flush()
    return row
