"""Daily watcher for SEBI's RHP and Prospectus lists. Only smid 11 (RHP) and 12 (Prospectus) are
requested; smid 10 (DRHP) is never fetched (owner, 29 October). Newest page only; entry pages and
PDFs are fetched once per new filing. Every request goes through PoliteClient's allow-list.

Stops the whole run on a 403, 429 or transport failure (refused()): never retries across entries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from analekh.db.models import IpoDocument, IpoIssue
from analekh.ingest.http import PoliteClient, refused
from analekh.ingest.storage import ObjectStore, sha256, storage_key
from analekh.ipo.listing import issue_stem, parse_list, pdf_url

LIST_BASE = "https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=3&ssid=15"
STAGE_SMID = {"rhp": 11, "prospectus": 12}
_STAGE_SUFFIX = re.compile(r"\s*[–-]?\s*(red herring prospectus|rhp|prospectus)\s*$", re.IGNORECASE)


@dataclass
class WatchResult:
    new: int = 0
    skipped: int = 0
    failed: int = 0
    stopped: str | None = None


def list_url(stage: str) -> str:
    return f"{LIST_BASE}&smid={STAGE_SMID[stage]}"


def _legal_name(title: str) -> str:
    return _STAGE_SUFFIX.sub("", title).strip(" -–")


def _issue_for(session: Session, title: str) -> IpoIssue:
    stem = issue_stem(title)
    issue = session.scalar(select(IpoIssue).where(IpoIssue.stem == stem))
    if issue is None:
        issue = IpoIssue(stem=stem, name=_legal_name(title))
        session.add(issue)
        session.flush()
    return issue


def _text(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def watch(session: Session, store: ObjectStore, client: PoliteClient) -> WatchResult:
    result = WatchResult()
    for stage in STAGE_SMID:
        try:
            listing = client.get(list_url(stage))
        except Exception as exc:  # noqa: BLE001 - classified below
            if refused(exc):
                result.stopped = str(exc)
                return result
            result.failed += 1
            continue
        for entry in parse_list(_text(listing.content), stage):
            if session.scalar(select(IpoDocument.id).where(IpoDocument.sebi_id == entry.sebi_id)):
                result.skipped += 1
                continue
            try:
                entry_html = _text(client.get(entry.entry_url).content)
                found_pdf = pdf_url(entry_html, entry.entry_url)
                data = client.get(found_pdf).content
            except Exception as exc:  # noqa: BLE001
                if refused(exc):
                    result.stopped = str(exc)
                    return result
                result.failed += 1
                continue
            digest = sha256(data)
            if session.scalar(select(IpoDocument.id).where(IpoDocument.file_sha256 == digest)):
                result.skipped += 1
                continue
            key = storage_key("ipo", digest, "pdf")
            if not store.exists(key):
                store.put(key, data, "application/pdf")
            issue = _issue_for(session, entry.title)
            session.add(
                IpoDocument(
                    issue_id=issue.id,
                    stage=stage,
                    sebi_id=entry.sebi_id,
                    entry_url=entry.entry_url,
                    pdf_url=found_pdf,
                    file_sha256=digest,
                    storage_key=key,
                    filed_on=entry.filed_on,
                    status="new",
                )
            )
            session.flush()
            result.new += 1
    return result
