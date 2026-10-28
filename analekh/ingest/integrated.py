"""Integrated filing (financials) lookup: which results XBRL files a company has filed.

SEBI moved quarterly results into integrated filings; NSE's results RSS stopped carrying them
(frozen since 24 August 2026, seen 2026-10-14). List behind NSE's integrated-filing page gives
every filing per company with XBRL link on nsearchives. Rule 1 amended 2026-10-14 for this one
endpoint, queried per company; files still come from nsearchives. Endpoint answers without home
page cookies; requests stay honest Analekh ones.
"""

import csv
import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlencode

import httpx
from lxml import etree
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.orm import Session

from analekh.config import get_settings
from analekh.db.models import Company, Filing
from analekh.ingest.feeds import IST
from analekh.ingest.http import PoliteClient, refused
from analekh.ingest.pipeline import IncompleteXbrl, IngestResult, ingest_results_xbrl
from analekh.ingest.storage import ObjectStore

LOOKUP_URL = "https://www.nseindia.com/api/integrated-filing-results"
PAGE_URL = "https://www.nseindia.com/companies-listing/corporate-integrated-filing?integratedType=integratedfilingfinancials"
FINANCIALS = "Integrated Filing- Financials"
# (no paging), XBRL from 2018 (rule 1, owner-approved 2026-10-15). Ends where integrated filings
HISTORY_URL = "https://www.nseindia.com/api/corporates-financial-results"
HISTORY_PAGE_URL = "https://www.nseindia.com/companies-listing/corporate-filings-financial-results"
PAGE_SIZE = 50
MAX_PAGES = 10


@dataclass(frozen=True)
class IntegratedFiling:
    symbol: str
    period_end: date | None
    consolidated: bool | None
    xbrl_url: str | None
    broadcast_at: datetime | None  # UTC
    revision: str | None  # "Original" or "Revised"
    ixbrl_url: str | None = None  # the same filing as a readable web page
    pdf_url: str | None = None  # results PDF, when the company attached one

    @property
    def links(self) -> dict[str, str]:
        """Source links kept in Filing.meta["links"] for the web app."""
        urls = {"ixbrl": self.ixbrl_url, "pdf": self.pdf_url, "xbrl": self.xbrl_url}
        return {kind: url for kind, url in urls.items() if url}

    @classmethod
    def from_row(cls, row: dict) -> "IntegratedFiling":
        nature = (row.get("consolidated") or "").lower()
        return cls(
            symbol=(row.get("symbol") or "").strip().upper(),
            period_end=_date(row.get("qe_Date")),
            consolidated=True if "consolidated" in nature else False if nature else None,
            xbrl_url=_url(row.get("xbrl")),
            broadcast_at=_ist(row.get("broadcast_Date")) or _ist(row.get("creation_Date")),
            revision=row.get("type_Sub"),
            ixbrl_url=_url(row.get("ixbrl")),
            pdf_url=_url(row.get("pdf_attach")),
        )


def _url(raw: str | None) -> str | None:
    """A file link, or None. NSE fills a missing attachment with its base path plus "null"
    (".../corporate/null", on about 1 in 3 filings): that is no link."""
    url = (raw or "").strip()
    if not url.startswith("http"):  # the financial-results list writes "-" for no file
        return None
    if url.rstrip("/").rsplit("/", 1)[-1].lower() in ("null", "undefined", "none", "-"):
        return None
    return url


def _date(raw: str | None) -> date | None:
    try:
        return datetime.strptime((raw or "").strip().title(), "%d-%b-%Y").date()  # 30-SEP-2026
    except ValueError:
        return None


def _ist(raw: str | None) -> datetime | None:
    try:
        when = datetime.strptime((raw or "").strip(), "%d-%b-%Y %H:%M:%S")  # 13-Oct-2026 21:42:13
    except ValueError:
        return None
    return when.replace(tzinfo=IST).astimezone(UTC)


def lookup(client: PoliteClient, symbol: str, *, sme: bool = False) -> list[IntegratedFiling]:
    """Every integrated financials filing NSE lists for one company, newest first."""
    rows: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        query = urlencode(
            {
                "index": "sme" if sme else "equity",
                "symbol": symbol.upper(),
                "type": FINANCIALS,
                "page": page,
                "size": PAGE_SIZE,
            }
        )
        result = client.get(
            f"{LOOKUP_URL}?{query}",
            headers={"Accept": "application/json", "Referer": PAGE_URL},
        )
        body = json.loads(result.content)
        batch = body.get("data") or []
        rows.extend(batch)
        if not batch or len(rows) >= int(body.get("totalCount") or 0):
            break
    return [IntegratedFiling.from_row(r) for r in rows]


def _history_row(row: dict) -> IntegratedFiling:
    nature = (row.get("consolidated") or "").strip().lower()  # "Consolidated" / "Non-Consolidated"
    filed = (row.get("broadCastDate") or row.get("filingDate") or "").strip()
    url = _url(row.get("xbrl"))
    return IntegratedFiling(
        symbol=(row.get("symbol") or "").strip().upper(),
        period_end=_date(row.get("toDate")),
        consolidated=None if not nature else not nature.startswith("non"),
        xbrl_url=None if (url or "").endswith("_WEB.xml") else url,
        broadcast_at=_ist(filed) or _ist(f"{filed}:00"),  # filingDate has no seconds
        revision=None,  # the list carries no Original / Revision flag
    )


def lookup_history(client: PoliteClient, symbol: str, *, sme: bool = False) -> list[IntegratedFiling]:
    """Every quarterly results filing NSE's financial-results list holds for one company (back
    to 2005; XBRL from 2018), in one request."""
    query = urlencode(  # verify the SME index name against a live request
        {"index": "sme" if sme else "equities", "period": "Quarterly", "symbol": symbol.upper()}
    )
    result = client.get(
        f"{HISTORY_URL}?{query}",
        headers={"Accept": "application/json", "Referer": HISTORY_PAGE_URL},
    )
    body = json.loads(result.content)
    rows = (body.get("data") or []) if isinstance(body, dict) else (body or [])
    return [_history_row(r) for r in rows]


def select_filings(
    filings: list[IntegratedFiling],
    known: set[str],
    *,
    quarters: int | None = None,
    one_basis: bool = False,
) -> list[IntegratedFiling]:
    """Filings to download, oldest first so V5/V7/V9 have history; within a period the original
    before any revision. ``quarters`` keeps the newest N period ends; ``one_basis`` keeps
    consolidated when a period has it, else standalone (half the downloads for a bulk run)."""
    todo = [f for f in filings if f.xbrl_url and f.xbrl_url not in known]
    if quarters is not None:
        ends = sorted({f.period_end for f in filings if f.period_end}, reverse=True)[:quarters]
        todo = [f for f in todo if f.period_end in ends]
    if one_basis:
        consolidated = {f.period_end for f in filings if f.consolidated}
        todo = [f for f in todo if f.consolidated or f.period_end not in consolidated]
    return sorted(
        todo,
        key=lambda f: (
            f.period_end or date.min,
            f.revision != "Original",
            f.broadcast_at or datetime.min.replace(tzinfo=UTC),
        ),
    )


@dataclass
class FetchOutcome:
    listed: int  # integrated financials filings NSE lists for the company
    with_xbrl: int  # of those, how many link an XBRL file
    results: list[IngestResult]
    missing: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def new(self) -> int:
        return sum(not r.skipped for r in self.results)

    @property
    def gap(self) -> str | None:
        """Why the company has nothing to store, or None when it has filings."""
        if self.listed == 0:
            return "no integrated financials filings listed on NSE"
        if self.with_xbrl == 0:
            return f"{self.listed} filings listed, none with an XBRL file"
        if self.errors and not self.results:  # "error..." reasons are retried by bulk runs
            return f"error: {len(self.errors)} XBRL files failed ({self.errors[0]})"
        if self.missing and not self.results:
            return f"{len(self.missing)} XBRL files listed but missing or unreadable on NSE"
        return None


def fetch_results(
    session: Session,
    store: ObjectStore,
    client: PoliteClient,
    company: Company,
    *,
    quarters: int | None = None,
    one_basis: bool = False,
) -> FetchOutcome:
    """Download and ingest the company's integrated filings not yet stored."""
    listed = lookup(client, company.nse_symbol, sme=company.is_sme)
    return _fetch(session, store, client, company, listed, quarters, one_basis)


def fetch_history(
    session: Session,
    store: ObjectStore,
    client: PoliteClient,
    company: Company,
    *,
    one_basis: bool = False,
) -> FetchOutcome:
    """Download and ingest the company's results from before integrated filings (every quarter
    with XBRL, from 2018) not yet stored."""
    listed = lookup_history(client, company.nse_symbol, sme=company.is_sme)
    return _fetch(session, store, client, company, listed, None, one_basis)


def _fetch(
    session: Session,
    store: ObjectStore,
    client: PoliteClient,
    company: Company,
    listed: list[IntegratedFiling],
    quarters: int | None,
    one_basis: bool,
) -> FetchOutcome:
    known = unchanged_links(session, listed, company.id)
    out = FetchOutcome(len(listed), sum(1 for f in listed if f.xbrl_url), [])
    for f in select_filings(listed, known, quarters=quarters, one_basis=one_basis):
        try:
            result = _download_and_ingest(session, store, client, company, f)
        except Exception as exc:
            if refused(exc):  # bulk runs stop on this; the company is fetched again in full
                raise
            out.errors.append(_error(f, exc))
            continue
        if result is None:
            out.missing.append(f.xbrl_url or "")
        else:
            out.results.append(result)
    return out


def _error(f: IntegratedFiling, exc: BaseException) -> str:
    return f"{f.xbrl_url}: {type(exc).__name__}: {exc}"[:300]


def _listing(f: IntegratedFiling) -> dict[str, str]:
    """How NSE lists a link: its broadcast time and Original/Revision flag, when given."""
    out = {}
    if f.broadcast_at:
        out["broadcast_at"] = f.broadcast_at.isoformat()
    if f.revision:
        out["revision"] = f.revision
    return out


def unchanged_links(session: Session, listed: list[IntegratedFiling], company_id: int | None = None) -> set[str]:
    """Listed XBRL links already stored and listed as before: nothing to download.

    A link NSE lists with new broadcast time or Original/Revision flag is fetched once more (a
    corrected file may sit behind it). A filing remembers each listing it was fetched for (meta
    "listed", by link): identical file, or one stored under another link, not fetched again every
    run. A listing with no time or flag matches any.
    """
    urls = sorted({f.xbrl_url for f in listed if f.xbrl_url})
    if not urls:
        return set()
    q = select(Filing.source_url, Filing.filed_at, Filing.meta).where(or_(Filing.source_url.in_(urls), Filing.meta["listed"].has_any(array(urls))))
    if company_id is not None:
        q = q.where(Filing.company_id == company_id)
    seen: dict[str, list[tuple[datetime | None, str | None]]] = {}
    for source_url, filed_at, meta in session.execute(q):
        meta = meta or {}
        if source_url:  # as filed: the filing's own time and flag
            seen.setdefault(source_url, []).append((filed_at, meta.get("revision")))
        for url, again in (meta.get("listed") or {}).items():
            when = again.get("broadcast_at")
            seen.setdefault(url, []).append((datetime.fromisoformat(when) if when else None, again.get("revision")))
    return {
        f.xbrl_url
        for f in listed
        if f.xbrl_url and any((f.broadcast_at is None or f.broadcast_at == when) and (f.revision is None or f.revision == revision) for when, revision in seen.get(f.xbrl_url, ()))
    }


def _download_and_ingest(
    session: Session,
    store: ObjectStore,
    client: PoliteClient,
    company: Company,
    f: IntegratedFiling,
) -> IngestResult | None:
    """One listed filing into store; None when NSE lists a file it no longer serves (Adani
    Enterprises) or serves broken (XML cut off, Laurus Labs), so company's other filings are kept,
    not all lost. Broken file fetched once more in case download was cut short.
    """
    if f.xbrl_url is None:
        raise ValueError("listed filing has no XBRL link")
    attempts = get_settings().integrated_file_attempts
    for attempt in range(1, attempts + 1):
        try:
            data = client.get(f.xbrl_url).content
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (404, 410):
                return None
            raise
        try:
            with session.begin_nested():
                result = ingest_results_xbrl(
                    session,
                    store,
                    company,
                    data,
                    source_url=f.xbrl_url,
                    filed_at=f.broadcast_at,
                    revision=f.revision,
                )
                if not result.skipped:
                    result.filing.meta = {**result.filing.meta, "links": f.links}
                else:  # already stored: remember this listing so it isn't fetched again
                    meta = result.filing.meta or {}
                    listed = {**(meta.get("listed") or {}), f.xbrl_url: _listing(f)}
                    result.filing.meta = {**meta, "listed": listed}
            return result
        except IncompleteXbrl:
            return None  # the same file every time: no point fetching it again
        except etree.XMLSyntaxError:
            if attempt == attempts:
                return None
    return None


# Results watcher reads NSE's latest-results list in ONE request per run (rule 1). Truncated page


def next_page_size(last_summary: dict | None) -> int:
    """Page size for the next watcher run, from the last run's job-status summary."""
    last = (last_summary or {}).get("page_size")
    s = get_settings()
    size = last if isinstance(last, int) and not isinstance(last, bool) and last > 0 else None
    if not (last_summary or {}).get("truncated"):
        return s.latest_page_size
    return min((size or s.latest_page_size) * 2, s.latest_max_page_size)


@dataclass
class LatestOutcome:
    listed: int  # rows on the page
    new: int  # filings downloaded and stored
    unknown_symbols: list[str] = field(default_factory=list)  # not in our universe
    missing: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)  # "url: error"; tried again next run
    stopped: str | None = None  # NSE refused or stalled: the rest waits for the next run
    page_size: int = 0  # what we asked for (set from config.py by fetch_latest)
    total: int | None = None  # NSE's totalCount, when it gives one
    truncated: bool = False  # the page holds fewer rows than NSE has
    capped: bool = False  # truncated even at latest_max_page_size: only a bulk run can catch up

    @property
    def warning(self) -> str | None:
        if not self.capped:
            return None
        return f"NSE lists {self.total or 'more than'} rows but a page of {self.page_size} holds {self.listed}: run a bulk fetch (analekh results-backfill) to catch up"


def is_truncated(returned: int, requested: int, total: int | None) -> bool:
    """With NSE's totalCount: fewer rows than it has. Without: a page as big as we asked for."""
    return returned < total if total is not None else returned >= requested


def fetch_latest(session: Session, store: ObjectStore, client: PoliteClient, size: int | None = None) -> LatestOutcome:
    """New results filings across all companies from ONE request to NSE's latest-results list
    (the integrated-filing lookup without a ticker), then the XBRL for each filing we lack."""
    s = get_settings()
    size = size or s.latest_page_size
    query = urlencode({"index": "equity", "type": FINANCIALS, "page": 1, "size": size})
    result = client.get(f"{LOOKUP_URL}?{query}", headers={"Accept": "application/json", "Referer": PAGE_URL})
    body = json.loads(result.content)
    listed = [IntegratedFiling.from_row(r) for r in body.get("data") or []]
    raw_total = body.get("totalCount")
    total = int(raw_total) if str(raw_total or "").isdigit() else None
    known = unchanged_links(session, listed)
    companies = {c.nse_symbol: c for c in session.scalars(select(Company).where(Company.nse_symbol.in_({f.symbol for f in listed})))}
    out = LatestOutcome(listed=len(listed), new=0, page_size=size, total=total)
    out.truncated = is_truncated(len(listed), size, total)
    out.capped = out.truncated and size >= s.latest_max_page_size
    todo = [f for f in listed if f.xbrl_url and f.xbrl_url not in known]
    for f in select_filings(todo, set()):
        company = companies.get(f.symbol)
        if company is None:
            out.unknown_symbols.append(f.symbol)
            continue
        try:
            ingested = _download_and_ingest(session, store, client, company, f)
        except Exception as exc:
            if refused(exc):  # stop knocking; what is stored so far is kept
                out.stopped = _error(f, exc)
                break
            out.errors.append(_error(f, exc))
            continue
        if ingested is None:
            out.missing.append(f.xbrl_url or "")
        elif not ingested.skipped:
            out.new += 1
    return out


GAP_FIELDS = [
    "symbol",
    "name",
    "series",
    "isin",
    "sector",
    "listed",
    "with_xbrl",
    "reason",
    "checked_at",
]


def record_gap(path: Path, company: Company, reason: str | None, outcome: FetchOutcome | None) -> None:
    """Keep ``path`` (CSV, one row per company) listing companies with no results to store and
    why. A company that later has filings is removed. Rewritten whole: it stays small."""
    rows: dict[str, dict[str, str]] = {}
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            rows = {r["symbol"]: r for r in csv.DictReader(fh)}
    if reason is None:
        if rows.pop(company.nse_symbol, None) is None:
            return
    else:
        rows[company.nse_symbol] = {
            "symbol": company.nse_symbol,
            "name": company.name,
            "series": company.series or "",
            "isin": company.isin or "",
            "sector": company.sector or "",
            "listed": "" if outcome is None else str(outcome.listed),
            "with_xbrl": "" if outcome is None else str(outcome.with_xbrl),
            "reason": reason,
            "checked_at": datetime.now(UTC).astimezone(IST).strftime("%Y-%m-%d %H:%M"),
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=GAP_FIELDS)
        writer.writeheader()
        writer.writerows(sorted(rows.values(), key=lambda r: r["symbol"]))


class NseRefusedError(RuntimeError):
    pass
