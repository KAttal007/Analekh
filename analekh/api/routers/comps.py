"""Comps: saved peer lists, peer suggestions and the comparable-companies table (design doc 18)."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from analekh.api import schemas
from analekh.api.deps import DB, company_or_404
from analekh.db.models import PeerList, Price
from analekh.glance import quarter_label
from analekh.ib.comps import (
    MAX_COMPANIES,
    CompRow,
    build_table,
    clean_symbols,
    suggest_peers,
    summary_stats,
    to_xlsx,
)
from analekh.universe.search import get as get_company

router = APIRouter(tags=["comps"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _symbols(db: DB, raw: list[str]) -> list[str]:
    """The NSE symbols to save in a list: each once, all known to the universe."""
    symbols = clean_symbols(raw)
    if len(symbols) > MAX_COMPANIES:
        raise HTTPException(422, f"a peer list holds at most {MAX_COMPANIES} companies")
    found: list[str] = []
    unknown: list[str] = []
    for s in symbols:
        company = get_company(db, s)
        if company is None:
            unknown.append(s)
        else:
            found.append(company.nse_symbol)
    if unknown:
        raise HTTPException(422, f"not in the NSE universe: {', '.join(unknown)}")
    return found


def _name(db: DB, raw: str, exclude: int | None = None) -> str:
    name = " ".join(raw.split())
    if not name:
        raise HTTPException(422, "give the list a name")
    clash = select(PeerList.id).where(func.lower(PeerList.name) == name.lower())
    if exclude is not None:
        clash = clash.where(PeerList.id != exclude)
    if db.scalar(clash) is not None:
        raise HTTPException(409, f"a peer list called {name!r} already exists")
    return name


def _commit(db: DB, name: str) -> None:
    """Commit, turning the unique-name constraint into the same 409 as the check above: two
    saves with one name at the same moment both pass the check, and only one can win."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, f"a peer list called {name!r} already exists") from exc


def _list_or_404(db: DB, list_id: int) -> PeerList:
    peer_list = db.get(PeerList, list_id)
    if peer_list is None:
        raise HTTPException(404, "peer list not found")
    return peer_list


@router.get("/peer-lists")
def peer_lists(db: DB) -> list[schemas.PeerListOut]:
    rows = db.scalars(select(PeerList).order_by(func.lower(PeerList.name)))
    return [schemas.PeerListOut.model_validate(r) for r in rows]


@router.post("/peer-lists", status_code=201)
def create_peer_list(body: schemas.PeerListIn, db: DB) -> schemas.PeerListOut:
    peer_list = PeerList(name=_name(db, body.name), symbols=_symbols(db, body.symbols))
    db.add(peer_list)
    _commit(db, peer_list.name)  # visible to the next request before this one returns
    return schemas.PeerListOut.model_validate(peer_list)


@router.put("/peer-lists/{list_id}")
def update_peer_list(list_id: int, body: schemas.PeerListUpdate, db: DB) -> schemas.PeerListOut:
    peer_list = _list_or_404(db, list_id)
    if body.name is not None:
        peer_list.name = _name(db, body.name, exclude=list_id)
    if body.symbols is not None:
        peer_list.symbols = _symbols(db, body.symbols)
    _commit(db, peer_list.name)
    return schemas.PeerListOut.model_validate(peer_list)


@router.delete("/peer-lists/{list_id}", status_code=204)
def delete_peer_list(list_id: int, db: DB) -> None:
    db.delete(_list_or_404(db, list_id))
    db.commit()


@router.get("/companies/{symbol}/peers")
def peers(symbol: str, db: DB, limit: int = 8) -> list[schemas.PeerOut]:
    """Same sector and results format, closest in market cap first; empty without a sector."""
    company = company_or_404(db, symbol)
    found = suggest_peers(db, company, max(1, min(limit, MAX_COMPANIES)))
    latest = select(func.max(Price.trade_date)).scalar_subquery()
    caps = dict(
        db.execute(
            select(Price.company_id, Price.market_cap).where(
                Price.trade_date == latest, Price.company_id.in_([p.id for p in found])
            )
        ).all()
    )
    return [
        schemas.PeerOut(
            symbol=p.nse_symbol, name=p.name, sector=p.sector, market_cap=caps.get(p.id)
        )
        for p in found
    ]


def _requested(body: schemas.CompsRequest, db: DB) -> list[str]:
    symbols = body.symbols
    if body.peer_list:
        pl = db.scalar(select(PeerList).where(PeerList.name == body.peer_list))
        if pl is None:
            raise HTTPException(404, "peer list not found")
        symbols = pl.symbols
    wanted = clean_symbols(symbols)
    if not wanted:
        raise HTTPException(422, "add at least one company")
    if len(wanted) > MAX_COMPANIES:
        raise HTTPException(422, f"a comparison holds at most {MAX_COMPANIES} companies")
    return wanted


def _row_out(row: CompRow) -> schemas.CompRowOut:
    i = row.inputs
    return schemas.CompRowOut(
        symbol=i.symbol,
        name=i.name,
        sector=i.sector,
        taxonomy=i.taxonomy,
        consolidated=i.consolidated,
        price=i.price,
        price_date=i.as_of,
        market_cap=i.market_cap,
        ttm_revenue=i.ttm_revenue,
        ttm_ebitda=i.ttm_ebitda,
        ttm_pat=i.ttm_pat,
        revenue_yoy=i.revenue_yoy,
        ebitda_margin=i.ebitda_margin,
        pat_margin=i.pat_margin,
        pe=row.pe,
        pb=row.pb,
        book_value=i.book_value,
        book_value_at=i.book_value_at,
        ev=row.ev,
        ev_ebitda=row.ev_ebitda,
        quarter_end=i.quarter_end,
        quarter_label=quarter_label(i.quarter_end) if i.quarter_end else None,
        notes=i.notes,
    )


@router.post("/comps/table")
def comps_table(body: schemas.CompsRequest, db: DB) -> schemas.CompsTableOut:
    rows, missing = build_table(db, _requested(body, db), body.consolidated)
    stats = {k: schemas.CompStatOut(**v) for k, v in summary_stats(rows).items()}
    dates = [r.inputs.as_of for r in rows if r.inputs.as_of]
    return schemas.CompsTableOut(
        rows=[_row_out(r) for r in rows],
        stats=stats,
        missing=missing,
        as_of=max(dates) if dates else None,
    )


@router.post("/comps")
def comps(body: schemas.CompsRequest, db: DB) -> Response:
    """The same table as an Excel workbook."""
    rows, _ = build_table(db, _requested(body, db), body.consolidated)
    return Response(
        to_xlsx(rows),
        media_type=XLSX,
        headers={"Content-Disposition": 'attachment; filename="comps.xlsx"'},
    )
