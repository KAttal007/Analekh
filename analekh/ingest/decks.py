"""Investor presentations of lenders: NSE's announcements list, then the deck, then its ratios.

Rule 1 (amended 2026-10-31, owner-approved): ONE request per watcher run to
`/api/corporate-announcements` (subject "Investor Presentation", no symbol), then one PDF per new
deck of a bank or NBFC we cover, from `nsearchives`, via PoliteClient. Run by the results watcher
itself, so it follows the same schedule (analekh.seasons). No page is crawled.

Safe by construction: the list is parsed, never executed; a deck URL must be an https PDF under
`nsearchives.nseindia.com/corporate/` (PoliteClient re-checks every hop); size and page limits come
from settings; the file must start with %PDF; a failure marks that deck and moves on; a refusal
from NSE stops the run; nothing is logged but symbols and counts.
"""

import json
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode, urlparse

import pymupdf
from sqlalchemy import select
from sqlalchemy.orm import Session

from analekh.config import get_settings
from analekh.db.models import Company, InvestorDeck, ReportedRatio
from analekh.decks.ratios import Ratio, read_deck
from analekh.ingest.feeds import IST
from analekh.ingest.http import PoliteClient, refused
from analekh.ingest.storage import ObjectStore

LIST_URL = "https://www.nseindia.com/api/corporate-announcements"
PAGE_URL = "https://www.nseindia.com/companies-listing/corporate-filings-announcements"
SUBJECT = "Investor Presentation"
DECK_HOST = "nsearchives.nseindia.com"
DECK_PREFIX = "/corporate/"
LENDER_TAXONOMIES = ("banking", "nbfc")


@dataclass(frozen=True)
class Announcement:
    symbol: str
    url: str
    broadcast_at: datetime | None  # UTC

    @classmethod
    def from_row(cls, row: dict) -> "Announcement | None":
        url = str(row.get("attchmntFile") or "").strip()
        parts = urlparse(url)
        if parts.scheme != "https" or parts.hostname != DECK_HOST or not parts.path.startswith(DECK_PREFIX) or not parts.path.lower().endswith(".pdf"):
            return None
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol:
            return None
        try:
            when: datetime | None = datetime.strptime(str(row.get("an_dt") or "").strip(), "%d-%b-%Y %H:%M:%S").replace(tzinfo=IST).astimezone(UTC)
        except ValueError:
            when = None
        return cls(symbol, url, when)


@dataclass
class DeckRun:
    listed: int = 0
    new: int = 0
    read: int = 0
    ratios: int = 0
    skipped: int = 0
    failed: int = 0
    deferred: int = 0  # new decks left for the next run (decks_per_run)
    stopped: str | None = None
    errors: list[str] = field(default_factory=list)


def list_announcements(client: PoliteClient) -> list[Announcement]:
    query = urlencode({"index": "equities", "reqXbrl": "false", "subject": SUBJECT})
    result = client.get(f"{LIST_URL}?{query}", headers={"Accept": "application/json", "Referer": PAGE_URL})
    rows = json.loads(result.content)
    if not isinstance(rows, list):
        return []
    found = (Announcement.from_row(r) for r in rows if isinstance(r, dict))
    return [a for a in found if a is not None]


def _store_ratios(session: Session, deck: InvestorDeck, ratios: list[Ratio], ids: dict[str, int]) -> int:
    stored = 0
    for r in ratios:
        company_id = ids.get(r.symbol)
        if company_id is None:
            continue
        row = session.scalar(
            select(ReportedRatio).where(
                ReportedRatio.company_id == company_id,
                ReportedRatio.period_end == r.period_end,
                ReportedRatio.metric == r.metric,
                ReportedRatio.basis == r.basis,
            )
        )
        if row is None:
            session.add(ReportedRatio(company_id=company_id, period_end=r.period_end, metric=r.metric, basis=r.basis, value=r.value, deck_id=deck.id, page=r.page, layer=r.layer))
        else:
            older = session.get(InvestorDeck, row.deck_id)
            if older is not None and older.broadcast_at and deck.broadcast_at and older.broadcast_at > deck.broadcast_at:
                continue  # a newer deck already holds this quarter
            row.value, row.deck_id, row.page, row.layer = r.value, deck.id, r.page, r.layer
            row.updated_at = datetime.now(UTC)
        stored += 1
    return stored


def _read(
    session: Session,
    store: ObjectStore,
    client: PoliteClient,
    ann: Announcement,
    company: Company,
    names: dict[str, str],
    ids: dict[str, int],
    deck: InvestorDeck | None = None,
) -> InvestorDeck:
    s = get_settings()
    if deck is None:
        deck = InvestorDeck(company_id=company.id, url=ann.url, broadcast_at=ann.broadcast_at, status="failed")
        session.add(deck)
    data = client.get(ann.url).content
    deck.file_sha256 = sha256(data).hexdigest()
    if not data.startswith(b"%PDF") or len(data) > s.deck_max_bytes:
        deck.status, deck.note = "skipped", "not a PDF or over the size limit"
        session.flush()
        return deck
    store.put(f"decks/{deck.file_sha256}.pdf", data, "application/pdf")
    with tempfile.TemporaryDirectory(prefix="deck-") as tmp:
        path = Path(tmp) / "deck.pdf"
        path.write_bytes(data)
        with pymupdf.open(path) as doc:
            pages = len(doc)
        if pages > s.deck_max_pages:
            deck.status, deck.note = "skipped", f"{pages} pages (limit {s.deck_max_pages})"
            session.flush()
            return deck
        ratios = read_deck(path, company.nse_symbol, names)
    session.flush()
    deck.ratios = _store_ratios(session, deck, ratios, ids)
    deck.status = "read" if deck.ratios else "no_ratios"
    return deck


def fetch_new_decks(session: Session, store: ObjectStore, client: PoliteClient) -> DeckRun:
    """New decks of covered lenders from ONE list request; each is read once and the ratios stored."""
    out = DeckRun()
    listed = list_announcements(client)
    out.listed = len(listed)
    companies = list(session.scalars(select(Company)))
    lenders = {c.nse_symbol: c for c in companies if c.results_taxonomy in LENDER_TAXONOMIES and c.is_active}
    known = {d.url: d for d in session.scalars(select(InvestorDeck).where(InvestorDeck.url.in_([a.url for a in listed])))}
    # a deck that failed is tried again on the next run; every other status is final
    todo = [a for a in listed if a.symbol in lenders and (a.url not in known or known[a.url].status == "failed")]
    todo.sort(key=lambda a: a.broadcast_at or datetime.min.replace(tzinfo=UTC))  # oldest first: a newer deck then wins
    out.new = len(todo)
    limit = get_settings().decks_per_run
    out.deferred = max(0, len(todo) - limit)
    names = {c.nse_symbol: c.name for c in companies}
    ids = {c.nse_symbol: c.id for c in companies}
    for ann in todo[:limit]:
        company = lenders[ann.symbol]
        try:
            with session.begin_nested():
                deck = _read(session, store, client, ann, company, names, ids, known.get(ann.url))
        except Exception as exc:
            if refused(exc):
                out.stopped = f"{ann.symbol}: {type(exc).__name__}"
                break
            out.failed += 1
            out.errors.append(f"{ann.symbol}: {type(exc).__name__}")
            if ann.url in known:
                known[ann.url].note = type(exc).__name__
            else:
                known[ann.url] = InvestorDeck(company_id=company.id, url=ann.url, broadcast_at=ann.broadcast_at, status="failed", note=type(exc).__name__)
                session.add(known[ann.url])
            session.flush()
            continue
        if deck.status == "skipped":
            out.skipped += 1
        else:
            out.read += 1
            out.ratios += deck.ratios
    return out
