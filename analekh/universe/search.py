"""Company search with type-ahead (design doc F2, 20).

The list narrows with each keystroke. One character matches tickers or names that start with it
("T"); two or more match anywhere in the ticker or name ("TC", "TCS"). Every typed word starting
a word of the name also matches, in any order ("tata pass" finds Tata Motors Passenger
Vehicles). Results are ranked in tiers and paged with ``offset`` so the UI can load more as the
analyst scrolls. Trigram similarity (pg_trgm) is only a fallback for typos, used when nothing
else matches.
"""

import re
from dataclasses import dataclass

from sqlalchemy import ColumnElement, and_, case, func, or_, select
from sqlalchemy.orm import Session

from analekh.db.models import Company

DEFAULT_LIMIT = 15


@dataclass(frozen=True)
class SearchHit:
    id: int
    nse_symbol: str
    name: str
    isin: str | None
    sector: str | None
    is_active: bool
    score: float


def search(
    session: Session,
    q: str,
    limit: int = DEFAULT_LIMIT,
    include_inactive: bool = False,
    offset: int = 0,
) -> list[SearchHit]:
    q = " ".join(q.split())
    if not q:
        return []
    words = q.split(" ")
    sym = "".join(words).upper()  # "hdfc amc" -> HDFCAMC

    tiers: list[tuple[ColumnElement[bool], float]] = [
        (or_(Company.nse_symbol == sym, Company.isin == sym), 100.0),
        (Company.nse_symbol.startswith(sym, autoescape=True), 80.0),
        (Company.name.istartswith(q, autoescape=True), 60.0),
    ]
    if len(q) > 1:
        all_words = and_(*(Company.name.op("~*")(r"\m" + re.escape(w)) for w in words))
        tiers += [
            (all_words, 40.0),
            (Company.nse_symbol.contains(sym, autoescape=True), 30.0),
            (Company.name.icontains(q, autoescape=True), 20.0),
        ]
    rank = case(*tiers, else_=0.0)
    hits = _run(session, or_(*(cond for cond, _ in tiers)), rank, limit, offset, include_inactive)
    if not hits and offset == 0 and len(q) > 2:
        similarity = func.similarity(Company.name, q)
        hits = _run(session, Company.name.op("%")(q), similarity, limit, 0, include_inactive)
    return hits


def _run(
    session: Session,
    where: ColumnElement[bool],
    rank: ColumnElement[float],
    limit: int,
    offset: int,
    include_inactive: bool,
) -> list[SearchHit]:
    stmt = (
        select(Company, rank.label("rank"))
        .where(where if include_inactive else and_(where, Company.is_active))
        .order_by(rank.desc(), Company.nse_symbol)
        .limit(limit)
        .offset(offset)
    )
    return [
        SearchHit(c.id, c.nse_symbol, c.name, c.isin, c.sector, c.is_active, float(r))
        for c, r in session.execute(stmt).all()
    ]


def get(session: Session, symbol: str) -> Company | None:
    return session.scalar(select(Company).where(Company.nse_symbol == symbol.strip().upper()))
