"""Export the record as JSONL training pairs any model can learn from (design: the record).

One header line, then one line per pair, from published reports only:

- first_draft: the report's inputs, and the AI's first draft;
- revision: the draft and the analyst's request, and the sections the AI changed (kept changes only);
- analyst_edit: the draft before and after the analyst's own typing (the strongest signal);
- final: the approved draft, and the text the analyst published.

Ratings, target prices and guidance are always masked (rule 8). `mask_numbers` also replaces every
number with <n>, for style training: facts are never trained into weights (AI.md section 1).
"""

import json
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from analekh.db.models import Company, PublishedFile, ReportThread, ReportVersion, ThreadMessage
from analekh.ingest.storage import ObjectStore
from analekh.reports.build import approved_version
from analekh.reports.draft import Draft
from analekh.reports.lessons import published_text
from analekh.reports.mask import mask_draft, mask_text
from analekh.reports.outlines import outline
from analekh.reports.sections import unit_to_markdown
from analekh.reports.store import load_draft

SCHEMA_VERSION = 1
_NUMBER = re.compile(r"(?<![\w<])\d[\d,]*(?:\.\d+)?%?")


def _md(draft: Draft, only: list[int] | None = None) -> str:
    masked = mask_draft(draft)
    units = [u for i, u in enumerate(masked.units) if only is None or i in only]
    return "\n\n".join(f"# {u.title}\n{unit_to_markdown(u)}" for u in units)


def _text(text: str, numbers: bool) -> str:
    out = mask_text(text).text
    return _NUMBER.sub("<n>", out) if numbers else out


def export_records(db: Session, store: ObjectStore, *, mask_numbers: bool = False) -> Iterator[dict[str, Any]]:
    yield {"schema_version": SCHEMA_VERSION, "kind": "analekh-export", "created_at": datetime.now(UTC).isoformat(), "numbers_masked": mask_numbers}

    def clean(s: str) -> str:
        return _NUMBER.sub("<n>", s) if mask_numbers else s

    for thread in db.scalars(select(ReportThread).where(ReportThread.status == "published").order_by(ReportThread.id)):
        company = db.get(Company, thread.company_id)
        base = {"thread_id": thread.id, "analyst": thread.owner_id, "report_type": thread.report_type, "format": thread.format}
        period = thread.quarter_end.isoformat() if thread.quarter_end else None
        yield {
            **base,
            "type": "first_draft",
            "input": {"company": company.nse_symbol if company else None, "period": period, "outline": outline(thread.report_type, thread.format)},
            "output": clean(_md(load_draft(db, store, thread, 1))),
        }
        last_request = ""
        for msg in db.scalars(select(ThreadMessage).where(ThreadMessage.thread_id == thread.id).order_by(ThreadMessage.id)):
            if msg.role == "analyst":
                last_request = msg.body
                continue
            meta = msg.meta or {}
            version, changed = meta.get("version_no"), meta.get("changed_units") or []
            if msg.role == "ai" and isinstance(version, int) and version > 1 and changed:
                before, after = load_draft(db, store, thread, version - 1), load_draft(db, store, thread, version)
                yield {**base, "type": "revision", "input": {"draft": clean(_md(before)), "request": _text(last_request, mask_numbers)}, "output": clean(_md(after, changed))}
        for v in db.scalars(select(ReportVersion).where(ReportVersion.thread_id == thread.id, ReportVersion.trigger == "analyst_edit").order_by(ReportVersion.version_no)):
            before, after = load_draft(db, store, thread, v.version_no - 1), load_draft(db, store, thread, v.version_no)
            yield {**base, "type": "analyst_edit", "input": clean(_md(before)), "output": clean(_md(after))}
        final = db.scalars(select(PublishedFile).where(PublishedFile.thread_id == thread.id).order_by(PublishedFile.id.desc())).first()
        if final is not None:
            approved = load_draft(db, store, thread, approved_version(db, thread).version_no)
            yield {**base, "type": "final", "input": clean(_md(approved)), "output": _text(published_text(store, final), mask_numbers)}


def export_jsonl(db: Session, store: ObjectStore, path: Path, *, mask_numbers: bool = False) -> int:
    """Write the export; returns the number of pairs (header line not counted)."""
    count = -1
    with path.open("w", encoding="utf-8") as fh:
        for record in export_records(db, store, mask_numbers=mask_numbers):
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count
