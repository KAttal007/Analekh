"""Integrated filing (financials) lookup: which results XBRL files a company has filed.

SEBI moved quarterly results into integrated filings, and NSE's results RSS feed stopped carrying
them (frozen since 24 August 2026, seen 2026-10-14). The list behind NSE's integrated-filing page
gives every filing per company with its XBRL link on nsearchives. Rule 1 was amended on 2026-10-14
to allow this one endpoint, queried per company; the files themselves come from nsearchives as
before. The endpoint answers without the home page's cookies; requests stay honest Analekh ones.
"""

import csv
import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from analekh.db.models import Company, Filing
from analekh.ingest.feeds import IST
from analekh.ingest.http import PoliteClient
from analekh.ingest.pipeline import IngestResult, ingest_results_xbrl
from analekh.ingest.storage import ObjectStore

LOOKUP_URL = "https://www.nseindia.com/api/integrated-filing-results"
PAGE_URL = (
    "https://www.nseindia.com/companies-listing/corporate-integrated-filing"
    "?integratedType=integratedfilingfinancials"
)
FINANCIALS = "Integrated Filing- Financials"
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
            # Revisions can come without a broadcast date (seen on Tata Elxsi, March 2026).
            broadcast_at=_ist(row.get("broadcast_Date")) or _ist(row.get("creation_Date")),
            revision=row.get("type_Sub"),
            ixbrl_url=_url(row.get("ixbrl")),
            pdf_url=_url(row.get("pdf_attach")),
        )


def _url(raw: str | None) -> str | None:
    """A file link, or None. NSE fills a missing attachment with its base path plus "null"
    (".../corporate/null", on about 1 in 3 filings): that is no link."""
    url = (raw or "").strip()
    if not url or url.rstrip("/").rsplit("/", 1)[-1].lower() in ("null", "undefined", "none"):
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
    missing: list[str] = field(default_factory=list)  # XBRL links NSE lists but answers 404 for

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
        if self.missing and not self.results:
            return f"{len(self.missing)} XBRL files listed but missing on NSE (404)"
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
    """Download and ingest the company's filings not yet stored."""
    urls = session.scalars(select(Filing.source_url).where(Filing.company_id == company.id))
    known = {u for u in urls if u}
    listed = lookup(client, company.nse_symbol, sme=company.is_sme)
    results: list[IngestResult] = []
    missing: list[str] = []
    for f in select_filings(listed, known, quarters=quarters, one_basis=one_basis):
        result = _download_and_ingest(session, store, client, company, f)
        if result is None:
            missing.append(f.xbrl_url or "")
        else:
            results.append(result)
    return FetchOutcome(len(listed), sum(1 for f in listed if f.xbrl_url), results, missing)


def _download_and_ingest(
    session: Session,
    store: ObjectStore,
    client: PoliteClient,
    company: Company,
    f: IntegratedFiling,
) -> IngestResult | None:
    """One listed filing into the store; None when NSE lists a file it no longer serves (seen on
    Adani Enterprises), so the company's other filings are kept rather than all lost."""
    assert f.xbrl_url is not None
    try:
        data = client.get(f.xbrl_url).content
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (404, 410):
            return None
        raise
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
    return result


# The daily results watcher reads NSE's latest-results list once (the owner's choice: one request
# a day), so it asks for a page big enough for a busy results day.
LATEST_PAGE_SIZE = 500


@dataclass
class LatestOutcome:
    listed: int  # rows on the page
    new: int  # filings downloaded and stored
    unknown_symbols: list[str] = field(default_factory=list)  # not in our universe
    missing: list[str] = field(default_factory=list)
    page_full: bool = False  # every row was new: there may be more than one page of news


def fetch_latest(
    session: Session, store: ObjectStore, client: PoliteClient, size: int = LATEST_PAGE_SIZE
) -> LatestOutcome:
    """New results filings across all companies from ONE request to NSE's latest-results list
    (the integrated-filing lookup without a ticker), then the XBRL for each filing we lack."""
    query = urlencode({"index": "equity", "type": FINANCIALS, "page": 1, "size": size})
    result = client.get(
        f"{LOOKUP_URL}?{query}", headers={"Accept": "application/json", "Referer": PAGE_URL}
    )
    listed = [IntegratedFiling.from_row(r) for r in json.loads(result.content).get("data") or []]
    urls = {f.xbrl_url for f in listed if f.xbrl_url}
    known = set(session.scalars(select(Filing.source_url).where(Filing.source_url.in_(urls))))
    companies = {
        c.nse_symbol: c
        for c in session.scalars(
            select(Company).where(Company.nse_symbol.in_({f.symbol for f in listed}))
        )
    }
    out = LatestOutcome(listed=len(listed), new=0)
    todo = [f for f in listed if f.xbrl_url and f.xbrl_url not in known]
    out.page_full = bool(listed) and len(todo) == len(listed)
    for f in select_filings(todo, set()):
        company = companies.get(f.symbol)
        if company is None:
            out.unknown_symbols.append(f.symbol)
            continue
        ingested = _download_and_ingest(session, store, client, company, f)
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


def record_gap(
    path: Path, company: Company, reason: str | None, outcome: FetchOutcome | None
) -> None:
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


# Statuses that mean NSE is refusing us: stop the whole run rather than keep knocking.
BLOCKED_STATUSES = {401, 403, 429}


class NseRefusedError(RuntimeError):
    pass


def refused(exc: BaseException) -> bool:
    """A sign that NSE is blocking or throttling us, as opposed to one bad file."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in BLOCKED_STATUSES
    return isinstance(exc, httpx.TransportError)  # timeouts and stalls included
