"""Idempotent background jobs (design doc 2.2, 4, 9). Re-running any task never duplicates rows.

Coverage levels decide the work: results XBRL is fetched and parsed for every filer; announcement
PDFs are stored for everyone but the document pipeline runs only for watchlist companies or a
company someone asked to analyse.
"""

from datetime import date, datetime
from pathlib import Path

from sqlalchemy import exists, select

from analekh.config import get_settings
from analekh.db.models import FeedItem, Filing, Watchlist
from analekh.db.session import session_scope
from analekh.ingest.backfill import run_backfill
from analekh.ingest.feeds import FeedWatcher
from analekh.ingest.http import PoliteClient
from analekh.ingest.integrated import fetch_results
from analekh.ingest.pipeline import process_feed_item
from analekh.ingest.storage import default_store
from analekh.jobs.app import app
from analekh.universe.search import get as get_company

_watcher: FeedWatcher | None = None
NIFTY500 = Path(__file__).resolve().parent.parent / "universe" / "data" / "nifty500.csv"


def watcher() -> FeedWatcher:
    global _watcher
    if _watcher is None:
        _watcher = FeedWatcher()
    return _watcher


@app.task(bind=True, max_retries=5, retry_backoff=True)
def poll_feed(self, feed: str) -> int:
    try:
        with session_scope() as s:
            return watcher().poll(s, feed)
    except Exception as exc:
        raise self.retry(exc=exc) from exc


@app.task
def process_pending(limit: int = 100) -> int:
    """Fetch the files new feed items link to, for every linked company (cheap, no AI)."""
    store, client, done = default_store(), PoliteClient(), 0
    with session_scope() as s:
        items = s.scalars(
            select(FeedItem)
            .where(FeedItem.processed_at.is_(None), FeedItem.company_id.is_not(None))
            .order_by(FeedItem.pub_date)
            .limit(limit)
        ).all()
        for item in items:
            with s.begin_nested():
                process_feed_item(s, store, client, item)
                done += 1
    return done


@app.task
def process_documents(limit: int = 10, company_id: int | None = None) -> int:
    """Document pipeline (AI) for watchlist companies, or one company on demand."""
    from analekh.docs.pipeline import process_document
    from analekh.genai.client import Claude

    store, done = default_store(), 0
    with session_scope() as s:
        claude = Claude(s) if get_settings().anthropic_api_key else None
        q = select(Filing).where(Filing.status == "fetched", Filing.kind != "results_xbrl")
        if company_id is not None:
            q = q.where(Filing.company_id == company_id)
        else:
            q = q.where(exists().where(Watchlist.company_id == Filing.company_id))
        for filing in s.scalars(q.limit(limit)).all():
            with s.begin_nested():
                process_document(s, store, filing, claude, embedder=None)
                done += 1
    return done


@app.task
def refresh_company(symbol: str) -> dict:
    """Newest results filing for a ticker (workflow 6.1 steps 2-4): pending feed items, then
    NSE's integrated-filing list for anything the feed missed."""
    with session_scope() as s:
        company = get_company(s, symbol)
        if company is None:
            return {"error": f"unknown symbol {symbol}"}
        pending = s.scalars(
            select(FeedItem).where(
                FeedItem.company_id == company.id,
                FeedItem.feed == "financial_results",
                FeedItem.processed_at.is_(None),
            )
        ).all()
        store, client = default_store(), PoliteClient()
        for item in pending:
            process_feed_item(s, store, client, item)
        integrated = fetch_results(s, store, client, company)
        latest = s.scalar(
            select(Filing)
            .where(Filing.company_id == company.id, Filing.kind == "results_xbrl")
            .order_by(Filing.period_end.desc().nulls_last())
        )
        return {
            "filing_id": latest.id if latest else None,
            "period_end": str(latest.period_end) if latest else None,
            "fetched": len(pending),
            "integrated_new": integrated.new,
        }


@app.task
def analyse_company(symbol: str) -> dict:
    """On-demand deep coverage (section 4.1): backfill history, then run the document pipeline."""
    result = backfill(symbol)
    with session_scope() as s:
        company = get_company(s, symbol)
        company_id = company.id if company else None
    docs = process_documents(limit=50, company_id=company_id) if company_id else 0
    return {"backfill": result, "documents_processed": docs}


@app.task
def backfill(symbol: str | None = None) -> dict:
    with session_scope() as s:
        summary = run_backfill(s, default_store(), Path(get_settings().import_dir), symbol)
        return summary.__dict__


@app.task
def background_backfill(batch: int = 5) -> dict:
    """Nightly, lowest priority: backfill Nifty 500 constituents that have no history yet.
    PHASE 1: fill universe/data/nifty500.csv (symbol column) from the index constituent file."""
    import csv

    if not NIFTY500.exists():
        return {"skipped": "universe/data/nifty500.csv not present"}
    with NIFTY500.open(newline="") as fh:
        symbols = [r["symbol"].strip().upper() for r in csv.DictReader(fh) if r.get("symbol")]
    done = []
    with session_scope() as s:
        for sym in symbols:
            c = get_company(s, sym)
            if c is None or s.scalar(select(exists().where(Filing.company_id == c.id))):
                continue
            done.append(sym)
            if len(done) >= batch:
                break
    return {"queued": [backfill.delay(sym).id for sym in done], "symbols": done}


@app.task
def refresh_universe() -> dict:
    """Weekly (UNIVERSE_REFRESH_CRON): new listings, symbol changes and delistings."""
    from analekh.universe.loader import refresh_from_nse

    with session_scope() as s:
        summary = refresh_from_nse(s)
        return {k: len(v) for k, v in summary.__dict__.items()}


@app.task
def sync_model(model_id: int, filing_id: int) -> dict:
    """Build a change set for a linked model from new results (section 16)."""
    from analekh.db.models import Model, ModelVersion
    from analekh.facts import DbValueSource
    from analekh.modelsync.changeset import build_change_set, save_proposal
    from analekh.workbook.mapping import Mapping
    from analekh.workbook.reader import load

    store = default_store()
    with session_scope() as s:
        model = s.get(Model, model_id)
        filing = s.get(Filing, filing_id)
        if model is None or filing is None or filing.period_end is None:
            return {"error": "model or filing not found"}
        if model.mapping is None:
            return {"error": "model mapping not confirmed"}
        version = s.scalar(
            select(ModelVersion)
            .where(ModelVersion.model_id == model_id)
            .order_by(ModelVersion.version.desc())
        )
        if version is None:
            return {"error": "model has no saved version"}
        proposal = build_change_set(
            load(store.get(version.storage_key)),
            Mapping.model_validate(model.mapping),
            filing.period_end,
            DbValueSource(s, filing.company_id),
            last_fingerprint=model.fingerprint,
        )
        if filing.meta.get("blocks_auto_apply"):
            proposal.warnings.insert(0, "Validation failures on this filing: review before apply")
        cs = save_proposal(s, model_id, version.version, filing_id, proposal)
        return {"change_set_id": cs.id, **proposal.summary}


@app.task
def bulk_fetch_results(
    symbols: list[str] | None = None,
    *,
    limit: int | None = None,
    quarters: int | None = 8,
    one_basis: bool = False,  # both standalone and consolidated
    skip_done: bool = True,
    log_dir: str = "out/bulk",
    interval_seconds: float | None = None,
    start_at: str | None = None,
    skip_no_filings: bool = True,
    history: bool = False,
    sectors: list[str] | None = None,
) -> dict:
    """Integrated-filing results for many companies (default: every company with a sector).

    One company per transaction, so a stopped run keeps what it stored; ``skip_done`` skips
    companies that already have a results filing, so rerunning resumes. Stops at the first sign
    that NSE is refusing or throttling us (403/429, timeouts) instead of retrying into a block.
    Progress goes to one JSON line per company under ``log_dir``.

    ``start_at`` resumes at that ticker (inclusive, in ticker order): the company NSE stalled on
    stored nothing (its transaction rolled back), so it is fetched again in full.
    ``skip_no_filings`` leaves out companies already listed in no-filings.csv as having nothing
    on NSE, so a restart doesn't spend requests re-checking them (errors there are retried).
    ``history`` fetches results from before integrated filings instead (NSE's financial-results
    list, XBRL from 2018): every company in scope, whether or not it has filings already, and
    the no-filings list is left alone. ``sectors`` limits the run to those sectors (exact names,
    as on the company page), so a long run can go sector by sector.
    """
    import json
    import time
    from datetime import datetime

    from analekh.db.models import Company
    from analekh.ingest.integrated import fetch_history, record_gap, refused

    with session_scope() as s:
        q = select(Company.nse_symbol).where(Company.is_active).order_by(Company.nse_symbol)
        if symbols:
            q = q.where(Company.nse_symbol.in_([x.upper() for x in symbols]))
        else:
            q = q.where(Company.sector.is_not(None))
        if sectors:
            q = q.where(Company.sector.in_(sectors))
        if skip_done and not history:
            q = q.where(
                ~exists().where(Filing.company_id == Company.id, Filing.kind == "results_xbrl")
            )
        if start_at:
            q = q.where(Company.nse_symbol >= start_at.upper())
        todo = list(s.scalars(q))

    prefix = "history-" if history else ""
    log = Path(log_dir) / f"{prefix}{datetime.now():%Y%m%d-%H%M%S}.jsonl"
    gaps = Path(log_dir) / "no-filings.csv"  # running list across runs: companies with nothing
    if skip_no_filings and not symbols and not history and gaps.exists():
        import csv

        with gaps.open(newline="", encoding="utf-8") as fh:
            nothing = {
                r["symbol"] for r in csv.DictReader(fh) if not r["reason"].startswith("error")
            }
        todo = [x for x in todo if x not in nothing]
    todo = todo[:limit]
    log.parent.mkdir(parents=True, exist_ok=True)
    rate = 1 / interval_seconds if interval_seconds else None  # e.g. 5 s: one request per 5 s
    store, client = default_store(), PoliteClient(max_attempts=2, rate_per_second=rate)
    summary: dict = {"companies": len(todo), "done": 0, "filings": 0, "errors": 0, "log": str(log)}
    summary["interval_seconds"] = interval_seconds
    started = time.monotonic()
    with log.open("a", encoding="utf-8") as out:
        for symbol in todo:
            t0 = time.monotonic()
            entry: dict[str, object] = {"symbol": symbol}
            try:
                with session_scope() as s:
                    company = get_company(s, symbol)
                    assert company is not None
                    if history:
                        outcome = fetch_history(s, store, client, company, one_basis=one_basis)
                    else:
                        outcome = fetch_results(
                            s, store, client, company, quarters=quarters, one_basis=one_basis
                        )
                    entry.update(listed=outcome.listed, new=outcome.new)
                    if outcome.missing:
                        entry["missing"] = len(outcome.missing)
                    entry["blocked"] = sum(
                        bool(r.report and r.report.blocks_auto_apply) for r in outcome.results
                    )
                    if outcome.gap:
                        entry["gap"] = outcome.gap
                    if not history:  # the no-filings list is about integrated filings
                        record_gap(gaps, company, outcome.gap, outcome)
                summary["done"] += 1
                summary["filings"] += outcome.new
            except Exception as exc:  # noqa: BLE001 - one bad company must not stop the run
                entry["error"] = f"{type(exc).__name__}: {exc}"[:300]
                summary["errors"] += 1
                if not refused(exc) and not history:  # a refusal says nothing about the company
                    with session_scope() as s:
                        company = get_company(s, symbol)
                        if company is not None:
                            record_gap(gaps, company, f"error: {entry['error']}", None)
                if refused(exc):
                    summary["stopped"] = f"NSE refused or stalled at {symbol}: {entry['error']}"
                    out.write(json.dumps(entry) + "\n")
                    break
            entry["seconds"] = round(time.monotonic() - t0, 1)
            out.write(json.dumps(entry) + "\n")
            out.flush()
    summary["seconds"] = round(time.monotonic() - started)
    return summary


def last_close_day(now: datetime | None = None) -> date:
    """The latest trading day whose bhavcopy should exist: today after 18:00 IST, else the day
    before; weekends roll back to Friday (holidays simply have no file)."""
    from datetime import UTC, timedelta

    from analekh.ingest.feeds import IST

    local = (now or datetime.now(UTC)).astimezone(IST)
    day = local.date() if local.hour >= 18 else local.date() - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


@app.task
def fetch_prices(day: str | None = None) -> dict:
    """NSE's bhavcopy for one trading day (default: the latest close): ONE request, then closing
    prices and market caps for every company it lists (rule 1, owner-approved 2026-10-17)."""
    from analekh.ingest.bhavcopy import load_day

    target = date.fromisoformat(day) if day else last_close_day()
    with session_scope() as s:
        return load_day(s, PoliteClient(), target)


@app.task
def watch_results(force: bool = False) -> dict:
    """New results filings for every company, from one request to NSE's latest list. Runs only
    when the season schedule says so (analekh.seasons): every 2 hours from 09:00 to 23:00 IST in
    a results season, at 21:00 otherwise. `force` asks NSE regardless."""
    from analekh.ingest.integrated import fetch_latest
    from analekh.seasons import watch_due

    due, reason = watch_due()
    if not (due or force):
        return {"skipped": reason}
    with session_scope() as s:
        out = fetch_latest(s, default_store(), PoliteClient(max_attempts=2))
    return {
        "why": reason if due else "forced",
        "listed": out.listed,
        "new": out.new,
        "missing": len(out.missing),
        "unknown_symbols": sorted(set(out.unknown_symbols)),
        "warning": (
            "every filing on the page was new: there may be more than one page of results today"
            if out.page_full
            else None
        ),
    }
