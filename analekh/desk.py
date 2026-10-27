"""Results desk (Home): who reported a quarter, revenue, profit and EBITDA margin vs same quarter a
year earlier, biggest movers, progress by sector.

One basis per company: consolidated if it filed consolidated for the quarter, else standalone
(rule used everywhere). "Revenue" = company's own top line (interest earned for banks, premium
earned for insurers). "Margin" = EBITDA margin for Ind-AS companies outside finance (derived as in
glance.py), net interest margin for lenders (interest.py), on consolidated figures when they allow
it, else standalone. Insurers: none.
"""

import statistics
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from analekh.db.models import Company, Fact, Filing, Watchlist
from analekh.glance import (
    change,
    derive,
    hidden_lines,
    missing_quarter_notes,
    quarter_label,
    raw_value,
    suspect_filings,
)
from analekh.interest import balances, is_lender, ratios
from analekh.prices import latest_prices
from analekh.xbrl.elements import candidates

# Movers leave out small companies and tiny profit bases, where growth rates are noise.
MIN_REVENUE = Decimal(500_000_000)  # Rs 50 crore of quarterly revenue
MIN_PROFIT_BASE = Decimal("0.02")  # year-ago profit at least 2% of year-ago revenue
MOVERS = 5
LOGICALS = (
    "revenue",
    "pat",
    "pat_continuing",
    "pbt",
    "exceptional_items",
    "finance_costs",
    "depreciation",
    "other_income",
    "interest_income",
    "interest_expense",
    "total_expenses",
    "impairment",
)
TAXONOMIES = ("indas", "banking", "insurance", "life_insurance")


@dataclass
class DeskRow:
    symbol: str
    name: str
    sector: str | None
    taxonomy: str
    consolidated: bool
    filed_at: datetime | None
    revenue: Decimal | None
    revenue_yoy: Decimal | None  # %
    pat: Decimal | None
    pat_yoy: Decimal | None  # %
    margin: Decimal | None  # %: EBITDA margin, NIM for lenders, core pre-provision for fee finance
    margin_kind: str | None  # "ebitda" | "nim"; None when the company has neither
    margin_yoy: Decimal | None  # basis points
    blocked: bool
    yoy_note: str | None = None  # why the YoY columns are blank, when the year-ago quarter is
    market_cap: Decimal | None = None  # at the latest stored close (bhavcopy)
    price_date: date | None = None  # that close's trading day
    margin_consolidated: bool | None = None  # the basis the margin is on (NIM may fall back)
    # Year-ago values, for the movers' base checks; not sent to the page.
    revenue_prev: Decimal | None = field(default=None, repr=False)
    pat_prev: Decimal | None = field(default=None, repr=False)


@dataclass
class SectorProgress:
    sector: str
    reported: int
    total: int
    median_revenue_yoy: Decimal | None
    median_pat_yoy: Decimal | None


@dataclass
class Desk:
    quarter_end: date | None
    quarter_label: str | None
    quarters: list[tuple[date, int]]  # recent quarter ends and how many companies reported
    companies_in_scope: int  # companies with a sector: the desk's universe
    reported: int  # of those, how many have results for this quarter (after filters)
    filings_total: int
    latest_filed_at: datetime | None
    rows: list[DeskRow]  # the requested page, newest filing first (or largest, by sort)
    rows_total: int
    revenue_top: list[DeskRow] = field(default_factory=list)
    revenue_bottom: list[DeskRow] = field(default_factory=list)
    profit_top: list[DeskRow] = field(default_factory=list)
    profit_bottom: list[DeskRow] = field(default_factory=list)
    turned_profitable: list[DeskRow] = field(default_factory=list)
    turned_loss: list[DeskRow] = field(default_factory=list)
    sectors: list[SectorProgress] = field(default_factory=list)
    # Sectors that reported the quarter, whatever the filter: the desk's sector dropdown.
    all_sectors: list[str] = field(default_factory=list)


def _quarter_start(end: date) -> date:
    month = end.month - 2
    return date(end.year if month > 0 else end.year - 1, month if month > 0 else month + 12, 1)


def recent_quarters(session: Session, limit: int = 6) -> list[tuple[date, int]]:
    rows = session.execute(
        select(Filing.period_end, func.count(func.distinct(Filing.company_id)))
        .where(Filing.kind == "results_xbrl", Filing.period_type == "Q")
        .group_by(Filing.period_end)
        .order_by(Filing.period_end.desc())
        .limit(limit)
    ).all()
    return [(end, n) for end, n in rows if end is not None]


def desk(
    session: Session,
    *,
    quarter_end: date | None = None,
    sector: str | None = None,
    watchlist_user: str | None = None,
    days: int | None = None,
    limit: int = 50,
    offset: int = 0,
    sort: str = "filed",
    now: datetime | None = None,
) -> Desk:
    # Each query is a round trip to the database: the counts share one, and the companies in
    # scope (active, with a sector) are the sum of the per-sector totals.
    quarters = recent_quarters(session)
    end = quarter_end or (quarters[0][0] if quarters else None)
    totals = sector_totals(session)
    filings_total, latest_filed_at = session.execute(
        select(func.count(), func.max(Filing.filed_at))
        .select_from(Filing)
        .where(Filing.kind == "results_xbrl")  # not transcripts, decks or other documents
    ).one()
    out = Desk(
        quarter_end=end,
        quarter_label=quarter_label(end) if end else None,
        quarters=quarters,
        companies_in_scope=sum(totals.values()),
        reported=0,
        filings_total=filings_total or 0,
        latest_filed_at=latest_filed_at,
        rows=[],
        rows_total=0,
    )
    if end is None:
        return out
    out.all_sectors = sorted(
        s
        for s in session.scalars(
            select(Company.sector)
            .distinct()
            .join(Filing, Filing.company_id == Company.id)
            .where(
                Filing.kind == "results_xbrl",
                Filing.period_type == "Q",
                Filing.period_end == end,
                Company.is_active,
                Company.sector.is_not(None),
            )
        )
        if s
    )

    company_q = select(Company).where(Company.is_active)
    if sector:
        company_q = company_q.where(Company.sector == sector)
    if watchlist_user:
        company_q = company_q.where(
            Company.id.in_(select(Watchlist.company_id).where(Watchlist.user_id == watchlist_user))
        )
    filings = session.execute(
        select(Filing.company_id, Filing.consolidated, Filing.filed_at, Filing.meta).where(
            Filing.kind == "results_xbrl",
            Filing.period_type == "Q",
            Filing.period_end == end,
            Filing.company_id.in_(company_q.with_only_columns(Company.id)),
        )
    ).all()
    by_company: dict[int, list] = {}
    for f in filings:
        by_company.setdefault(f.company_id, []).append(f)
    companies = {
        c.id: c for c in session.scalars(select(Company).where(Company.id.in_(by_company)))
    }

    year_ago = date(end.year - 1, end.month, end.day)
    periods = [(_quarter_start(end), end), (_quarter_start(year_ago), year_ago)]
    elements = sorted({e for t in TAXONOMIES for name in LOGICALS for e in candidates(name, t)})
    facts = session.execute(
        select(
            Fact.company_id,
            Fact.consolidated,
            Fact.element,
            Fact.period_start,
            Fact.period_end,
            Fact.value,
            Fact.filing_id,
        ).where(
            Fact.company_id.in_(by_company),
            Fact.is_latest,
            Fact.dimensions == {},
            Fact.is_instant.is_(False),
            Fact.element.in_(elements),
            tuple_(Fact.period_start, Fact.period_end).in_(periods),
        )
    ).all()
    values: dict[tuple[int, bool], dict[str, dict[date, Decimal]]] = {}
    # Figures from a filing V11 suspects of the wrong unit stay out of growth and Movers.
    suspect = suspect_filings(session, list(by_company))
    held_back: set[tuple[int, bool]] = set()
    for f in facts:
        if f.filing_id in suspect:
            held_back.add((f.company_id, bool(f.consolidated)))
            continue
        if f.value is not None:
            values.setdefault((f.company_id, bool(f.consolidated)), {}).setdefault(f.element, {})[
                f.period_end
            ] = f.value

    prices = latest_prices(session, list(by_company))
    lenders = [cid for cid, c in companies.items() if is_lender(c)]
    sheets = balances(session, lenders, suspect)  # balance sheets for the NIM, both bases
    rows: list[DeskRow] = []
    needs_note: dict[tuple[int, bool], DeskRow] = {}  # no year-ago figures: say why, below
    for company_id, company_filings in by_company.items():
        c = companies[company_id]
        basis = any(f.consolidated for f in company_filings)
        mine = [f for f in company_filings if bool(f.consolidated) == basis]
        taxonomy = c.results_taxonomy or "indas"

        def lines_for(consolidated: bool, cid: int = company_id, tax: str = taxonomy) -> dict:
            """glance.py's shape: {logical: {period_end: (period_start, value)}}."""
            by_element = values.get((cid, consolidated), {})
            return {
                name: {
                    at: (start, v)
                    for start, at in periods
                    if (
                        v := next(
                            (
                                by_element[e][at]
                                for e in candidates(name, tax)
                                if at in by_element.get(e, {})
                            ),
                            None,
                        )
                    )
                    is not None
                }
                for name in LOGICALS
            }

        q = lines_for(basis)
        rev, rev_prev = raw_value(q, "revenue", end), raw_value(q, "revenue", year_ago)
        pat, pat_prev = raw_value(q, "pat", end), raw_value(q, "pat", year_ago)
        margin = margin_prev = None
        margin_kind: str | None = None
        margin_basis: bool | None = basis
        # Banks and NBFCs: NIM, a dash where it can't be worked out (interest.py).
        if company_id in lenders:
            margin_kind = "nim"
            # Consolidated when it allows a NIM, else standalone (the lender's own book).
            for consolidated in (True, False) if basis else (False,):
                qb, parts = lines_for(consolidated), sheets.get((company_id, consolidated), {})

                def nim(at: date, qb: dict = qb, parts: dict = parts) -> Decimal | None:
                    return ratios(
                        raw_value(qb, "interest_income", at),
                        raw_value(qb, "interest_expense", at),
                        parts,
                        _quarter_start(at),
                        at,
                        raw_value(qb, "revenue", at),
                    ).nim

                if (margin := nim(end)) is not None:
                    margin_basis, margin_prev = consolidated, nim(year_ago)
                    break
        elif taxonomy == "indas":
            # Outside finance EBITDA margin; asset managers and brokers the core pre-provision
            # profit margin (glance.hidden_lines); other financials neither.
            shown = {"=ebitda_margin": "ebitda", "=cpppm": "cpppm"}
            hidden = hidden_lines(c)
            for line, kind in shown.items():
                if line not in hidden:
                    margin_kind = kind
                    margin, margin_prev = derive(q, end)[line], derive(q, year_ago)[line]
        filed = [f.filed_at for f in mine if f.filed_at]
        rows.append(
            DeskRow(
                symbol=c.nse_symbol,
                name=c.name,
                sector=c.sector,
                taxonomy=taxonomy,
                consolidated=basis,
                filed_at=min(filed) if filed else None,
                revenue=rev,
                revenue_yoy=change(rev, rev_prev, "inr"),
                pat=pat,
                pat_yoy=change(pat, pat_prev, "inr"),
                margin=margin.quantize(Decimal("0.01" if margin_kind == "nim" else "0.1"))
                if margin is not None
                else None,
                margin_kind=margin_kind,
                margin_yoy=change(margin, margin_prev, "pct"),
                margin_consolidated=margin_basis if margin is not None else None,
                blocked=any((f.meta or {}).get("blocks_auto_apply") for f in mine),
                revenue_prev=rev_prev,
                pat_prev=pat_prev,
            )
        )
        if price := prices.get(company_id):
            rows[-1].market_cap, rows[-1].price_date = price.market_cap, price.trade_date
        if (company_id, basis) in held_back and (rev_prev is None or rev is None):
            rows[-1].yoy_note = (
                "A filing for this comparison looks tagged in the wrong unit (check V11): "
                "left out until its PDF is checked"
            )
        elif rev_prev is None and pat_prev is None:
            needs_note[(company_id, basis)] = rows[-1]

    for key, note in missing_quarter_notes(session, list(needs_note), year_ago).items():
        needs_note[key].yoy_note = note

    _movers(out, rows)
    _sectors(out, rows, totals)
    out.reported = len(rows)

    if days:
        since = (now or datetime.now(UTC)) - timedelta(days=days)
        rows = [r for r in rows if r.filed_at and r.filed_at >= since]
    rows.sort(key=lambda r: r.filed_at or datetime.min.replace(tzinfo=UTC), reverse=True)
    if sort == "market_cap":  # stable: equal (or unknown) market caps keep the newest first
        rows.sort(key=lambda r: (r.market_cap is None, -(r.market_cap or 0)))
    out.rows_total = len(rows)
    out.rows = rows[offset : offset + limit]
    return out


def _solid_base(r: DeskRow) -> bool:
    """Profit growth means something: a year-ago profit, and not a tiny one next to revenue."""
    return (
        r.pat_prev is not None
        and r.revenue_prev is not None
        and r.pat_prev > 0
        and r.pat_prev >= r.revenue_prev * MIN_PROFIT_BASE
    )


def _split(ranked: list[DeskRow]) -> tuple[list[DeskRow], list[DeskRow]]:
    """Top and bottom movers from a list sorted by growth, ascending. Early in a season there are
    fewer than 2 x MOVERS companies: the bottom list then takes only those not already on top."""
    top = ranked[::-1][:MOVERS]
    rest = [r for r in ranked if r not in top]
    return top, rest[:MOVERS]


def _movers(out: Desk, rows: list[DeskRow]) -> None:
    big = [r for r in rows if r.revenue is not None and r.revenue >= MIN_REVENUE]

    by_revenue = sorted(
        ((r.revenue_yoy, r) for r in big if r.revenue_yoy is not None), key=lambda t: t[0]
    )
    out.revenue_top, out.revenue_bottom = _split([r for _, r in by_revenue])

    by_profit = []  # both quarters profitable, on a year-ago base that isn't tiny
    turned_profitable = []
    turned_loss = []
    for r in big:
        if r.pat is None or r.pat_prev is None:
            continue
        if r.pat_prev <= 0 < r.pat:
            turned_profitable.append((r.pat, r))
        elif r.pat <= 0 < r.pat_prev:
            turned_loss.append((r.pat, r))
        elif r.pat > 0 and r.pat_yoy is not None and _solid_base(r):
            by_profit.append((r.pat_yoy, r))
    by_profit.sort(key=lambda t: t[0])
    out.profit_top, out.profit_bottom = _split([r for _, r in by_profit])
    out.turned_profitable = [r for _, r in sorted(turned_profitable, key=lambda t: -t[0])][:MOVERS]
    out.turned_loss = [r for _, r in sorted(turned_loss, key=lambda t: t[0])][:MOVERS]


def sector_totals(session: Session) -> dict[str, int]:
    """Active companies per sector (companies without a sector are outside the desk)."""
    return {
        name: n
        for name, n in session.execute(
            select(Company.sector, func.count())
            .where(Company.is_active, Company.sector.is_not(None))
            .group_by(Company.sector)
        ).all()
        if name is not None  # the query excludes them; this tells the type checker
    }


def _sectors(out: Desk, rows: list[DeskRow], totals: dict[str, int]) -> None:
    grouped: dict[str, list[DeskRow]] = {}
    for r in rows:
        if r.sector:
            grouped.setdefault(r.sector, []).append(r)

    def sized(rs: list[DeskRow]) -> list[DeskRow]:
        # Medians use the movers' floor: a one-company sector of tiny filers would otherwise
        # show its outlier as the sector's "median".
        return [r for r in rs if r.revenue is not None and r.revenue >= MIN_REVENUE]

    def median(values: list[Decimal]) -> Decimal | None:
        return Decimal(statistics.median(values)).quantize(Decimal("0.1")) if values else None

    out.sectors = sorted(
        (
            SectorProgress(
                sector=name,
                reported=len(rs),
                total=totals.get(name, len(rs)),
                median_revenue_yoy=median(
                    [r.revenue_yoy for r in sized(rs) if r.revenue_yoy is not None]
                ),
                median_pat_yoy=median(
                    [r.pat_yoy for r in sized(rs) if r.pat_yoy is not None and _solid_base(r)]
                ),
            )
            for name, rs in grouped.items()
        ),
        key=lambda s: (-s.reported, s.sector),
    )
