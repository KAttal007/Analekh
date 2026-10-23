"""One path for every results file, live or backfill: hash -> store -> parse -> validate -> facts.

Results XBRL is fetched and parsed for every company that files (design doc 9.2). Announcement
PDFs are stored for everyone (cheap) but only processed by the document pipeline for watchlist or
on-demand companies.

Re-running is idempotent: a file whose hash is already stored is skipped. A different file for an
already-stored period is a revision: its facts are inserted and the newest FILED value of each
line is the one in use (is_latest), whatever order the files were downloaded in; superseded values
stay as history (V9). Nothing is deleted.

V11 can find a filing's rupee amounts tagged in the wrong unit (100 times too small, say). When
both its signals agree, the corrected amounts are stored and the filing records the factor
(meta "scale"); the file in object storage keeps the values as filed, so revalidating always
recomputes from it and never applies a factor twice.
"""

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

import httpx
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from analekh.db.models import Company, Fact, FeedItem, Filing
from analekh.ingest.feeds import IST
from analekh.ingest.http import DisallowedHostError, PoliteClient, refused
from analekh.ingest.storage import ObjectStore, sha256, storage_key
from analekh.validate.rules import (
    MONETARY_UNITS,
    HistoryFact,
    ValidationContext,
    ValidationReport,
    validate,
)
from analekh.xbrl.elements import detect_taxonomy
from analekh.xbrl.parser import ParsedFiling, dims_hash, parse_instance, period_type

_NO_DIMS = dims_hash({})

ANNOUNCEMENT_KINDS = (
    ("transcript", ("transcript", "earnings call", "conference call")),
    ("presentation", ("investor presentation", "presentation")),
    ("annual_report", ("annual report",)),
)


class IncompleteXbrl(ValueError):
    """The file's values point to periods it never defines: NSE's older "_WEB" publications
    (up to December 2022) leave out the quarter, year-to-date and balance-sheet contexts, so
    most figures, including the basis, can't be placed. Such files are not stored (owner's
    decision 2026-10-15: history from 2023, no rebuilding of contexts by id)."""


MAIN_CONTEXTS = ("OneD", "FourD", "OneI")


class NotAPdf(ValueError):
    """The bytes NSE sent for a document are not a PDF: an error page answered with a 200, an
    empty body, or one of the XML and ZIP attachments some announcements link. Not stored."""


def check_pdf(data: bytes) -> None:
    """Raise NotAPdf unless the file starts with the PDF header (blank space before it is fine).
    Says what it looks like instead, so the failed item shows what NSE sent."""
    head = data[:1024].lstrip(b" \t\r\n\f\x00")
    if head.startswith(b"%PDF-"):
        return
    kind = (
        "empty"
        if not head
        else "xml"
        if head.startswith(b"<?xml")
        else "html"
        if head.startswith(b"<")
        else "zip"
        if head.startswith(b"PK\x03\x04")
        else "unknown"
    )
    raise NotAPdf(f"not a PDF ({kind}, {len(data)} bytes)")


@dataclass
class IngestResult:
    filing: Filing
    skipped: bool
    report: ValidationReport | None = None


def load_history(session: Session, company_id: int, consolidated: bool) -> list[HistoryFact]:
    rows = session.execute(
        select(Fact.element, Fact.period_start, Fact.period_end, Fact.value, Fact.filing_id).where(
            Fact.company_id == company_id,
            Fact.consolidated == consolidated,
            Fact.is_latest,
            Fact.dims_hash == _NO_DIMS,
            Fact.value.is_not(None),
        )
    ).all()
    return [
        HistoryFact(r.element, r.period_start, r.period_end, r.value, r.filing_id) for r in rows
    ]


def scale_meta(report: ValidationReport) -> dict | None:
    """V11's outcome for the filing's meta: corrected (with the factor) or suspect; None when the
    amounts look right."""
    v11 = next((r for r in report.results if r.rule == "V11"), None)
    if v11 is None or v11.status != "fail":
        return None
    status = v11.details.get("status")
    out = {"status": status, "message": v11.message}
    if report.scale is not None:
        out["factor"] = str(report.scale)
    return out


def ingest_results_xbrl(
    session: Session,
    store: ObjectStore,
    company: Company,
    data: bytes,
    *,
    source_url: str | None = None,
    feed_item_id: int | None = None,
    filed_at: datetime | None = None,
    revision: str | None = None,
) -> IngestResult:
    digest = sha256(data)
    existing = session.scalar(select(Filing).where(Filing.file_sha256 == digest))
    if existing is not None:
        return IngestResult(existing, skipped=True)

    parsed = parse_instance(data)
    undefined = [
        w for w in parsed.warnings if any(w.endswith(f"unknown context {c}") for c in MAIN_CONTEXTS)
    ]
    if undefined and not parsed.meta:
        raise IncompleteXbrl(f"{len(undefined)} values point to undefined periods ({undefined[0]})")
    key = storage_key("results_xbrl", digest, "xml", filed_at)
    store.put(key, data, "application/xml")

    # The filing's own line items are the strongest signal of a bank or an insurer: they correct
    # a guess from the sector or from an earlier, less telling filing.
    detected = detect_taxonomy({f.element for f in parsed.facts})
    if detected or company.results_taxonomy is None:
        company.results_taxonomy = detected or parsed.taxonomy()
    consolidated = parsed.consolidated if parsed.consolidated is not None else True
    history = load_history(session, company.id, consolidated)
    ctx = ValidationContext(
        parsed,
        company.results_taxonomy,
        filed_at.astimezone(IST).date() if filed_at else None,
        history,
        other_basis=load_history(session, company.id, not consolidated),
    )
    report = validate(ctx)
    stored = report.filing or parsed  # amounts corrected by V11, when it corrects them
    scale = scale_meta(report)

    period_end = ctx.period_end
    period_start = parsed.declared_start or next(
        (
            f.period_start
            for f in parsed.facts
            if f.period_end == period_end and period_type(f.period_start, f.period_end) == "Q"
        ),
        None,
    )
    filing = Filing(
        company_id=company.id,
        feed_item_id=feed_item_id,
        kind="results_xbrl",
        period_start=period_start,
        period_end=period_end,
        period_type=period_type(period_start, period_end) if period_end else None,
        consolidated=consolidated,
        audited=parsed.audited,
        source_url=source_url,
        file_sha256=digest,
        storage_key=key,
        filed_at=filed_at,
        status="validated",
        meta={
            "schema_ref": parsed.schema_ref,
            "declared": parsed.meta,
            "parser_warnings": parsed.warnings,
            "validation": report.as_dict(),
            "blocks_auto_apply": report.blocks_auto_apply,
            # NSE's own flag from the integrated-filing list: "Original" or "Revision".
            **({"revision": revision} if revision else {}),
            **({"scale": scale} if scale else {}),
        },
    )
    try:
        with session.begin_nested():
            session.add(filing)
            session.flush()
    except IntegrityError:
        # Another run (the scheduled worker and a manual run, say) stored this same file between
        # our check above and this insert. The file hash is unique, so theirs stands: skip ours.
        existing = session.scalar(select(Filing).where(Filing.file_sha256 == digest))
        if existing is None:
            raise
        return IngestResult(existing, skipped=True)

    for f in stored.facts:
        session.add(
            Fact(
                filing_id=filing.id,
                company_id=company.id,
                element=f.element,
                period_start=f.period_start,
                period_end=f.period_end,
                is_instant=f.is_instant,
                consolidated=consolidated,
                value=f.value,
                unit=f.unit,
                decimals=f.decimals,
                context_ref=f.context_ref,
                dimensions=f.dimensions,
                dims_hash=f.dims_hash,
                is_latest=False,  # decided below, by filing time
            )
        )
    session.flush()
    refresh_latest(session, company.id)
    return IngestResult(filing, skipped=False, report=report)


# For each line of each period (element, dates, basis, dimensions), the value in use is the one
# from the most recently FILED filing; a filing without a date counts as the oldest. Two steps, so
# no moment has two values in use for the same line.
_LATEST_SQL = """
WITH ranked AS (
    SELECT f.id,
           row_number() OVER (
               PARTITION BY f.company_id, f.consolidated, f.element, f.period_start,
                            f.period_end, f.dims_hash
               ORDER BY fl.filed_at DESC NULLS LAST, fl.id DESC
           ) = 1 AS top
    FROM facts f JOIN filings fl ON fl.id = f.filing_id
    WHERE f.company_id = :company_id
)
UPDATE facts SET is_latest = ranked.top
FROM ranked
WHERE facts.id = ranked.id AND facts.is_latest IS DISTINCT FROM ranked.top
"""


def refresh_latest(session: Session, company_id: int) -> int:
    """Re-decide which value of every line is in use for one company, by filing time (a revised
    filing beats the original even when it was downloaded first). Returns the rows changed."""
    result = session.execute(text(_LATEST_SQL), {"company_id": company_id})
    return int(getattr(result, "rowcount", 0) or 0)


def classify_announcement(title: str | None, description: str | None = None) -> str:
    text = f"{title or ''} {description or ''}".lower()
    for kind, keywords in ANNOUNCEMENT_KINDS:
        if any(k in text for k in keywords):
            return kind
    return "other"


def process_feed_item(
    session: Session, store: ObjectStore, client: PoliteClient, item: FeedItem
) -> Filing | None:
    """Fetch the file an RSS item links to and route it. Unlinked items wait for review."""
    if item.company_id is None:
        return None
    company = session.get(Company, item.company_id)
    if company is None:
        return None
    if not item.link:  # nothing to fetch: done, so it never holds a place in the queue
        item.processed_at = datetime.now().astimezone()
        return None
    if item.feed == "corporate_action":
        # Ex-date notices link to an NSE web page that rule 1 does not allow, and they are not
        # filings: close without a request.
        item.processed_at = datetime.now().astimezone()
        return None
    if item.feed != "financial_results" and urlparse(item.link).path.lower().endswith(".xml"):
        # Intimation XMLs on the other feeds are never PDFs, so storing them always fails, and
        # nothing reads them (the calendar and alerts use the feed text). Close without a request.
        item.processed_at = datetime.now().astimezone()
        return None
    # The same file can sit in several feeds or repeat within one: no second request to NSE for a
    # link already stored, or already given up on.
    stored = session.scalar(select(Filing).where(Filing.source_url == item.link).limit(1))
    failed = None
    if stored is None:
        failed = session.scalar(
            select(FeedItem.error)
            .where(
                FeedItem.link == item.link,
                FeedItem.id != item.id,
                FeedItem.processed_at.is_not(None),
                FeedItem.error.is_not(None),
            )
            .limit(1)
        )
    if stored is not None or failed is not None:
        item.processed_at = datetime.now().astimezone()
        item.error = failed
        return stored
    result = client.get(item.link)
    filing: Filing | None
    if item.feed == "financial_results":
        filing = ingest_results_xbrl(
            session,
            store,
            company,
            result.content,
            source_url=item.link,
            feed_item_id=item.id,
            filed_at=item.pub_date,
        ).filing
    else:
        filing = store_document(
            session,
            store,
            company,
            result.content,
            kind=classify_announcement(item.title, item.description),
            source_url=item.link,
            feed_item_id=item.id,
            filed_at=item.pub_date,
        )
    item.processed_at = datetime.now().astimezone()
    item.error = None
    return filing


# A feed item whose file fails this many times is given up on (processed_at set, error kept).
MAX_ATTEMPTS = 3


@dataclass
class QueueRun:
    done: int = 0
    failed: int = 0
    stopped: str | None = None  # why the run stopped early; the rest waits for the next run


def pending_feed_items(session: Session, limit: int) -> list[FeedItem]:
    """Linked items not processed yet, oldest first; items that failed before go last, so a few
    bad ones can't fill every batch."""
    return list(
        session.scalars(
            select(FeedItem)
            .where(FeedItem.processed_at.is_(None), FeedItem.company_id.is_not(None))
            .order_by(FeedItem.attempts, FeedItem.pub_date, FeedItem.id)
            .limit(limit)
        )
    )


def _gone(exc: BaseException) -> bool:
    """Failures that will be the same on every try: give up at once."""
    if isinstance(exc, DisallowedHostError | IncompleteXbrl | NotAPdf):
        return True
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (404, 410)


def process_feed_items(
    session: Session, store: ObjectStore, client: PoliteClient, items: list[FeedItem]
) -> QueueRun:
    """Each item in its own savepoint: a failure is recorded on the item and the run goes on.
    A sign that NSE is refusing us stops the run without counting against the item."""
    run = QueueRun()
    for item in items:
        try:
            with session.begin_nested():
                process_feed_item(session, store, client, item)
        except Exception as exc:
            if refused(exc):
                run.stopped = f"{item.link}: {type(exc).__name__}: {exc}"[:300]
                break
            item.attempts = (item.attempts or 0) + 1
            item.error = f"{type(exc).__name__}: {exc}"[:500]
            if _gone(exc) or item.attempts >= MAX_ATTEMPTS:
                item.processed_at = datetime.now().astimezone()
            run.failed += 1
        else:
            run.done += 1
    return run


def store_document(
    session: Session,
    store: ObjectStore,
    company: Company,
    data: bytes,
    *,
    kind: str,
    source_url: str | None = None,
    feed_item_id: int | None = None,
    filed_at: datetime | None = None,
    ext: str = "pdf",
) -> Filing:
    """Store a PDF once; the document pipeline (analekh.docs) picks it up from status 'fetched'.
    Anything else is refused before it reaches storage (NotAPdf)."""
    check_pdf(data)
    digest = sha256(data)
    existing = session.scalar(select(Filing).where(Filing.file_sha256 == digest))
    if existing is not None:
        return existing
    key = storage_key(kind, digest, ext, filed_at)
    store.put(key, data, "application/pdf")
    filing = Filing(
        company_id=company.id,
        feed_item_id=feed_item_id,
        kind=kind,
        source_url=source_url,
        file_sha256=digest,
        storage_key=key,
        filed_at=filed_at,
        status="fetched",
    )
    try:
        with session.begin_nested():
            session.add(filing)
            session.flush()
    except IntegrityError:  # stored by another run since the check above: theirs stands
        existing = session.scalar(select(Filing).where(Filing.file_sha256 == digest))
        if existing is None:
            raise
        return existing
    return filing


def _fact_key(element: str, start, end, dims: str, context: str | None) -> tuple:
    return (element, start, end, dims, context)


def rewrite_amounts(session: Session, filing: Filing, parsed: ParsedFiling, factor) -> int:
    """Set the filing's stored rupee amounts, and their precision, to the values as filed times
    factor (1 restores them). Always from the file, so it can never apply a factor twice.
    Returns rows changed."""
    from decimal import Decimal

    from analekh.validate.rules import scaled_decimals

    multiplier = Decimal(factor) if factor is not None else Decimal(1)
    filed = {
        _fact_key(f.element, f.period_start, f.period_end, f.dims_hash, f.context_ref): f
        for f in parsed.facts
        if f.unit in MONETARY_UNITS
    }
    changed = 0
    for row in session.scalars(select(Fact).where(Fact.filing_id == filing.id)):
        if row.unit not in MONETARY_UNITS:
            continue
        raw = filed.get(
            _fact_key(row.element, row.period_start, row.period_end, row.dims_hash, row.context_ref)
        )
        if raw is None:
            continue
        value = raw.value * multiplier
        decimals = scaled_decimals(raw.decimals, multiplier)
        if row.value != value or row.decimals != decimals:
            row.value, row.decimals = value, decimals
            changed += 1
    return changed


def revalidate_company(session: Session, store: ObjectStore, company: Company) -> list[Filing]:
    """Re-run detection and V1-V11 on a company's stored results files, after the rules or the
    element tables change. Reads the stored files; downloads nothing. A V11 correction that
    appears, changes or goes away rewrites the filing's amounts from the file."""
    filings = list(
        session.scalars(
            select(Filing)
            .where(Filing.company_id == company.id, Filing.kind == "results_xbrl")
            .order_by(Filing.period_end)
        )
    )
    parsed = {f.id: parse_instance(store.get(f.storage_key)) for f in filings if f.storage_key}
    detected = next(
        (t for p in parsed.values() if (t := detect_taxonomy({x.element for x in p.facts}))), None
    )
    if detected:
        company.results_taxonomy = detected
    for filing in filings:
        if filing.id not in parsed:
            continue
        history = [
            h
            for h in load_history(session, company.id, bool(filing.consolidated))
            if h.filing_id != filing.id
        ]
        filed = filing.filed_at.astimezone(IST).date() if filing.filed_at else None
        report = validate(
            ValidationContext(
                parsed[filing.id],
                company.results_taxonomy or "indas",
                filed,
                history,
                other_basis=load_history(session, company.id, not bool(filing.consolidated)),
            )
        )
        scale = scale_meta(report)
        before = ((filing.meta or {}).get("scale") or {}).get("factor")
        after = scale.get("factor") if scale else None
        if before != after or after is not None:  # idempotent: from the file, every time
            rewrite_amounts(session, filing, parsed[filing.id], after)
            session.flush()  # the next filing's checks read the corrected amounts
        meta = {k: v for k, v in (filing.meta or {}).items() if k != "scale"}
        filing.meta = {
            **meta,
            "validation": report.as_dict(),
            "blocks_auto_apply": report.blocks_auto_apply,
            **({"scale": scale} if scale else {}),
        }
    return filings
