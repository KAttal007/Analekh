"""Universe, company pages, watchlist and on-demand coverage (design doc 4, 19.1, 20)."""

import hashlib
import json
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on

from analekh import coverage
from analekh.api import schemas
from analekh.api.deps import DB, User, company_or_404, job
from analekh.db.models import ChangeSet, Company, Fact, Filing, Kpi, Model
from analekh.facts import files_consolidated
from analekh.universe.search import DEFAULT_LIMIT, search
from analekh.xbrl.elements import candidates

router = APIRouter(tags=["companies"])
SLIM_META = {"links", "blocks_auto_apply", "scale"}  # company page + V11 audit trail


@router.get("/companies/index", response_model=list[schemas.CompanyIndexEntry])
def company_index(db: DB, request: Request, response: Response) -> object:
    """Every active company, for the web app's in-browser type-ahead.

    About 3,200 short rows, so the browser loads it once and searches locally on each keystroke;
    /companies/search stays the source of truth (and the typo fallback). The ETag lets the
    browser revalidate with a 304 instead of downloading the list again."""
    rows = db.execute(select(Company.id, Company.nse_symbol, Company.name, Company.isin, Company.sector).where(Company.is_active).order_by(Company.nse_symbol)).all()
    digest = hashlib.sha256(json.dumps([tuple(r) for r in rows]).encode()).hexdigest()
    etag = f'"{digest[:40]}"'
    headers = {"ETag": etag, "Cache-Control": "private, max-age=300"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    response.headers.update(headers)
    return [schemas.CompanyIndexEntry(**r._mapping) for r in rows]


@router.get("/companies/search", response_model=list[schemas.SearchHitOut])
def search_companies(db: DB, q: str, limit: int = DEFAULT_LIMIT, offset: int = 0) -> list[schemas.SearchHitOut]:
    """Type-ahead search; page through long lists with ``offset``."""
    hits = search(db, q, min(max(limit, 1), 50), offset=max(offset, 0))
    return [schemas.SearchHitOut(**h.__dict__) for h in hits]


@router.get("/companies/{symbol}", response_model=schemas.CompanyDetail)
def get_company(symbol: str, db: DB) -> schemas.CompanyDetail:
    c = company_or_404(db, symbol)
    return schemas.CompanyDetail.model_validate(
        {
            **schemas.CompanyOut.model_validate(c).model_dump(),
            "coverage_level": coverage.level(db, c),
            "watched": coverage.is_watched(db, c.id),
        }
    )


@router.post("/watchlist", response_model=schemas.CompanyDetail)
def watch(body: schemas.WatchRequest, db: DB, user: User) -> schemas.CompanyDetail:
    c = company_or_404(db, body.symbol)
    coverage.add(db, c, user, body.settings)
    db.commit()
    return get_company(c.nse_symbol, db)


@router.delete("/watchlist/{symbol}", status_code=204)
def unwatch(symbol: str, db: DB, user: User) -> None:
    coverage.remove(db, company_or_404(db, symbol), user)
    db.commit()  # before the reply, as in watch()


@router.get("/watchlist", response_model=list[schemas.WatchlistEntryOut])
def watchlist(db: DB, user: User) -> list[schemas.WatchlistEntryOut]:
    from analekh.glance import glance, suspect_filings
    from analekh.prices import latest_prices

    entries = list(coverage.entries(db, user))
    ids = [w.company_id for w in entries]
    prices = latest_prices(db, ids)
    suspect = suspect_filings(db, ids)
    newest = (
        select(Filing.company_id, Filing.period_end, Filing.meta)
        .ext(distinct_on(Filing.company_id))
        .where(Filing.company_id.in_(ids), Filing.kind == "results_xbrl")
        .order_by(Filing.company_id, Filing.period_end.desc().nulls_last())
    )
    last_by_company = {r.company_id: r for r in db.execute(newest)}
    pending_by_company = dict(
        db.execute(
            select(Model.company_id, func.count(ChangeSet.id))
            .join(ChangeSet, ChangeSet.model_id == Model.id)
            .where(Model.company_id.in_(ids), ChangeSet.status == "proposed")
            .group_by(Model.company_id)
        ).all()
    )
    out = []
    for w in entries:
        last = last_by_company.get(w.company_id)
        pending = pending_by_company.get(w.company_id, 0)
        g = glance(db, w.company, suspect=suspect)
        lines = {line.key: line for line in g.lines}
        price = prices.get(w.company_id)
        out.append(
            schemas.WatchlistEntryOut(
                symbol=w.company.nse_symbol,
                name=w.company.name,
                added_at=w.added_at,
                settings=w.settings,
                last_filing=last.period_end if last else None,
                validation_blocked=bool(last and last.meta.get("blocks_auto_apply")),
                pending_change_sets=pending,
                sector=w.company.sector,
                taxonomy=g.taxonomy,
                consolidated=g.consolidated if g.lines else None,
                price=price.close if price else None,
                change_pct=price.change_pct if price else None,
                price_date=price.trade_date if price else None,
                market_cap=price.market_cap if price else None,
                quarter_label=g.quarter_label,
                revenue=lines["revenue"].value if "revenue" in lines else None,
                revenue_yoy=lines["revenue"].yoy if "revenue" in lines else None,
                pat=lines["pat"].value if "pat" in lines else None,
                pat_yoy=lines["pat"].yoy if "pat" in lines else None,
            )
        )
    return out


@router.post("/companies/{symbol}/refresh", response_model=schemas.JobOut)
def refresh(symbol: str, db: DB) -> schemas.JobOut:
    from analekh.jobs.tasks import refresh_company

    return job(refresh_company, company_or_404(db, symbol).nse_symbol)


@router.post("/companies/{symbol}/analyse", response_model=schemas.JobOut)
def analyse(symbol: str, db: DB) -> schemas.JobOut:
    """On-demand deep coverage for any company: backfill history and run the document pipeline."""
    from analekh.jobs.tasks import analyse_company

    return job(analyse_company, company_or_404(db, symbol).nse_symbol)


@router.get("/companies/{symbol}/filings", response_model=list[schemas.FilingOut])
def filings(
    symbol: str,
    db: DB,
    kind: str | None = None,
    start: date | None = None,
    end: date | None = None,
    full: bool = False,
) -> list[schemas.FilingOut]:
    """Filings, newest period first; a quarter filed more than once says which filing is in
    use, what it replaced and which headline numbers changed. ``meta`` holds only what the
    company page shows (file links, whether validation blocks it) unless ``full`` is set: the
    whole validation report is about 2 KB a filing."""
    from dataclasses import asdict

    from analekh.restatements import revisions

    company = company_or_404(db, symbol)
    q = select(Filing).where(Filing.company_id == company.id)
    if kind:
        q = q.where(Filing.kind == kind)
    if start:
        q = q.where(Filing.period_end >= start)
    if end:
        q = q.where(Filing.period_end <= end)
    rows = list(db.scalars(q.order_by(Filing.period_end.desc().nulls_last(), Filing.id.desc())))
    revised = revisions(db, company, rows)
    out = []
    for f in rows:
        item = schemas.FilingOut.model_validate(f)
        if not full:
            item.meta = {k: v for k, v in item.meta.items() if k in SLIM_META}
        if f.id in revised:
            item.revision = schemas.RevisionOut.model_validate(asdict(revised[f.id]))
        out.append(item)
    return out


@router.get("/companies/{symbol}/facts", response_model=list[schemas.FactOut])
def facts(
    symbol: str,
    db: DB,
    elements: str | None = None,
    start: date | None = None,
    end: date | None = None,
    consolidated: bool | None = None,
    logical: str | None = None,
) -> list[Fact]:
    """Facts by element name, or by ``logical`` name (e.g. revenue), resolved for the company's
    results format: a bank's revenue is interest earned, an insurer's premium earned."""
    company = company_or_404(db, symbol)
    company_id = company.id
    if logical:
        names = [e for x in logical.split(",") for e in candidates(x, company.results_taxonomy or "indas")]
        elements = ",".join(names) or "-"  # nothing in this format: no facts
    if consolidated is None:
        consolidated = files_consolidated(db, company_id)
    q = select(Fact).where(
        Fact.company_id == company_id,
        Fact.is_latest,
        Fact.consolidated == consolidated,
    )
    if elements:
        q = q.where(Fact.element.in_(elements.split(",")))
    if start:
        q = q.where(Fact.period_end >= start)
    if end:
        q = q.where(Fact.period_end <= end)
    return list(db.scalars(q.order_by(Fact.period_end.desc(), Fact.element)))


@router.get("/desk", response_model=schemas.DeskOut)
def results_desk(
    db: DB,
    user: User,
    quarter_end: date | None = None,
    sector: str | None = None,
    watchlist: bool = False,
    days: int | None = None,
    limit: int = 50,
    offset: int = 0,
    sort: Literal["filed", "market_cap"] = "filed",
) -> schemas.DeskOut:
    """Results desk (Home): who reported the quarter (newest first, latest quarter by default),
    year-on-year movers and progress by sector."""
    from dataclasses import asdict

    from analekh.desk import desk
    from analekh.glance import quarter_label

    d = desk(
        db,
        quarter_end=quarter_end,
        sector=sector,
        watchlist_user=user if watchlist else None,
        days=days,
        limit=min(max(limit, 1), 200),
        offset=max(offset, 0),
        sort=sort,
    )
    data = asdict(d)
    data["quarters"] = [{"quarter_end": end, "quarter_label": quarter_label(end), "reported": n} for end, n in d.quarters]
    return schemas.DeskOut.model_validate(data)


@router.get("/calendar", response_model=schemas.CalendarOut)
def results_calendar(
    db: DB,
    user: User,
    start: date | None = None,
    end: date | None = None,
    watchlist: bool = False,
) -> schemas.CalendarOut:
    """Who reports results or meets, by day (from the Board Meetings feed). ``watchlist`` keeps
    only watchlist companies; either way each event says whether its company is watched."""
    from dataclasses import asdict

    from analekh import schedule

    today = date.today()
    start = start or today - timedelta(days=2)
    end = end or start + timedelta(days=45)
    if end < start or (end - start).days > 400:
        raise HTTPException(422, "end must be after start, within 400 days")
    found = schedule.events(db, start, end, watchlist_user=user, only_watched=watchlist)
    unscheduled: list[schemas.UnscheduledOut] = []
    if watchlist:
        dated = {e.symbol for e in found if e.kind == "results"}
        unscheduled = [schemas.UnscheduledOut(symbol=c.nse_symbol, name=c.name, sector=c.sector) for c in (w.company for w in coverage.entries(db, user)) if c.nse_symbol not in dated]
    return schemas.CalendarOut(
        start=start,
        end=end,
        events=[schemas.CalendarEventOut(**asdict(e)) for e in found],
        unscheduled=unscheduled,
    )


@router.get("/companies/{symbol}/glance", response_model=schemas.GlanceOut)
def company_glance(symbol: str, db: DB, consolidated: bool | None = None) -> schemas.GlanceOut:
    """Latest quarter at a glance: P&L lines in the company's format, with QoQ and YoY change."""
    from dataclasses import asdict

    from analekh.glance import glance

    return schemas.GlanceOut.model_validate(asdict(glance(db, company_or_404(db, symbol), consolidated)))


@router.get("/companies/{symbol}/history", response_model=schemas.HistoryOut)
def company_history(symbol: str, db: DB, consolidated: bool | None = None, quarters: int = 8) -> schemas.HistoryOut:
    """Every stored quarter's P&L lines, oldest first (up to 28), on one basis."""
    from dataclasses import asdict

    from analekh.history import history

    return schemas.HistoryOut.model_validate(asdict(history(db, company_or_404(db, symbol), consolidated, quarters)))


@router.get("/companies/{symbol}/history.xlsx")
def company_history_xlsx(symbol: str, db: DB, consolidated: bool | None = None, quarters: int = 12) -> Response:
    """The results history as an Excel workbook, amounts in crore."""
    from analekh.history import history, to_xlsx

    c = company_or_404(db, symbol)
    h = history(db, c, consolidated, quarters)
    basis = "consolidated" if h.consolidated else "standalone"
    return Response(
        to_xlsx(h, c),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{c.nse_symbol}-results-{basis}.xlsx"'},
    )


@router.get("/companies/{symbol}/price", response_model=schemas.PriceOut | None)
def company_price(symbol: str, db: DB) -> schemas.PriceOut | None:
    """Latest close and market cap from NSE's bhavcopy (end of day); null before the first load."""
    from dataclasses import asdict

    from analekh.prices import latest_price

    price = latest_price(db, company_or_404(db, symbol).id)
    return schemas.PriceOut.model_validate(asdict(price)) if price else None


@router.get("/companies/{symbol}/kpis", response_model=list[schemas.KpiOut])
def kpis(symbol: str, db: DB, names: str | None = None) -> list[Kpi]:
    q = select(Kpi).where(Kpi.company_id == company_or_404(db, symbol).id)
    if names:
        q = q.where(Kpi.name.in_(names.split(",")))
    return list(db.scalars(q.order_by(Kpi.period_end.desc())))


@router.get("/jobs/{job_id}", response_model=schemas.JobOut)
def job_status(job_id: str) -> schemas.JobOut:
    from analekh.jobs.app import app as celery

    res = celery.AsyncResult(job_id)
    if res is None:
        raise HTTPException(404)
    return schemas.JobOut(job_id=job_id, status=res.status, result=res.result if res.ready() else None)
