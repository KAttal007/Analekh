"""Comparable companies table (design doc 18).

TTM figures are the sum of the last four reported quarters, which must run back to back (a gap
would sum four quarters spread over more than a year), all on one basis: consolidated when the
company has four consolidated quarters, else standalone (many companies file standalone only),
unless the caller fixes the basis. Each row records its basis so a mixed table is visible. EBITDA
is derived as on the company page (glance.py) and left out for lenders and insurers. Book value is
the latest balance sheet's equity (attributable to owners when consolidated; capital plus
reserves for banks). EV = market cap + debt - cash, shown only once both debt and cash are
sourced; until then EV multiples are blank rather than market cap passed off as EV. Multiples
that would divide by zero or a negative denominator are left blank (shown as "n.m."), never
forced.
"""

import io
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

import xlsxwriter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from analekh.db.models import Company, Fact, Price
from analekh.facts import files_consolidated
from analekh.glance import HUNDRED, _quarters, change, derive, is_financial

CRORE = Decimal(10_000_000)
BASIS_LABEL = {True: "Consolidated", False: "Standalone", None: "n.a."}
MAX_COMPANIES = 30  # per table: enough for any peer set, small enough to answer at once

# Balance-sheet equity for the book value, first found wins (instant facts, no dimensions).
BOOK_VALUE = {
    "indas": ("EquityAttributableToOwnersOfParent", "Equity"),
    "banking": (),  # capital + reserves, below
    "insurance": (),
    "life_insurance": (),
}


@dataclass
class CompInputs:
    symbol: str
    name: str
    market_cap: Decimal | None
    debt: Decimal | None
    cash: Decimal | None
    ttm_revenue: Decimal | None
    ttm_ebitda: Decimal | None
    ttm_pat: Decimal | None
    book_value: Decimal | None
    as_of: date | None = None  # the close the market cap is at
    notes: list[str] = field(default_factory=list)
    consolidated: bool | None = None  # basis of the figures; None when nothing was found
    sector: str | None = None
    taxonomy: str = "indas"
    price: Decimal | None = None
    quarter_end: date | None = None  # latest quarter in the TTM
    revenue_yoy: Decimal | None = None  # latest quarter on the same quarter a year earlier, %
    book_value_at: date | None = None

    @property
    def ebitda_margin(self) -> Decimal | None:
        return _pct(self.ttm_ebitda, self.ttm_revenue)

    @property
    def pat_margin(self) -> Decimal | None:
        return _pct(self.ttm_pat, self.ttm_revenue)


@dataclass
class CompRow:
    inputs: CompInputs
    ev: Decimal | None
    ev_sales: Decimal | None
    ev_ebitda: Decimal | None
    pe: Decimal | None
    pb: Decimal | None


def _pct(num: Decimal | None, den: Decimal | None) -> Decimal | None:
    if num is None or den is None or den <= 0:
        return None
    return (num / den * HUNDRED).quantize(Decimal("0.1"))


def _ratio(num: Decimal | None, den: Decimal | None) -> Decimal | None:
    if num is None or den is None or den <= 0:
        return None
    return (num / den).quantize(Decimal("0.1"))


def compute(inputs: CompInputs) -> CompRow:
    ev = None
    if inputs.market_cap is not None and inputs.debt is not None and inputs.cash is not None:
        ev = inputs.market_cap + inputs.debt - inputs.cash
    return CompRow(
        inputs,
        ev,
        _ratio(ev, inputs.ttm_revenue),
        _ratio(ev, inputs.ttm_ebitda),
        _ratio(inputs.market_cap, inputs.ttm_pat),
        _ratio(inputs.market_cap, inputs.book_value),
    )


STAT_METRICS = ("ev_sales", "ev_ebitda", "pe", "pb", "ebitda_margin", "pat_margin", "revenue_yoy")


def _metric(row: CompRow, metric: str) -> Decimal | None:
    value: Decimal | None = getattr(row, metric, None)
    if value is None and not hasattr(row, metric):
        value = getattr(row.inputs, metric)
    return value


def summary_stats(rows: list[CompRow]) -> dict[str, dict[str, Decimal | None]]:
    out: dict[str, dict[str, Decimal | None]] = {}
    for metric in STAT_METRICS:
        vals: list[Decimal] = sorted(v for r in rows if (v := _metric(r, metric)) is not None)
        if not vals:
            out[metric] = {"median": None, "mean": None}
            continue
        mid = len(vals) // 2
        median = vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2
        out[metric] = {
            "median": median.quantize(Decimal("0.1")),
            "mean": (sum(vals, Decimal(0)) / len(vals)).quantize(Decimal("0.1")),
        }
    return out


def four_quarters(q: dict) -> list[date] | None:
    """Ends of the latest four back-to-back quarters with revenue, newest first; None if the
    record has a gap or fewer than four."""
    revenue: dict[date, tuple[date, Decimal]] = q.get("revenue", {})
    if not revenue:
        return None
    ends = [max(revenue)]
    while len(ends) < 4:
        previous = revenue[ends[-1]][0] - timedelta(days=1)
        if previous not in revenue:
            return None
        ends.append(previous)
    return ends


def _value(q: dict, logical: str, end: date) -> Decimal | None:
    hit = q.get(logical, {}).get(end)
    if hit is None and logical == "pat":  # some filings tag only the continuing-operations line
        hit = q.get("pat_continuing", {}).get(end)
    return hit[1] if hit else None


def _sum(values: list[Decimal | None]) -> Decimal | None:
    if any(v is None for v in values):
        return None
    return sum((v for v in values if v is not None), Decimal(0))


def book_value(
    session: Session, company: Company, consolidated: bool
) -> tuple[Decimal | None, date | None]:
    """Equity from the latest balance sheet filed on this basis."""
    taxonomy = company.results_taxonomy or "indas"
    names = BOOK_VALUE.get(taxonomy, BOOK_VALUE["indas"])
    if taxonomy == "banking":
        names = ("Capital", "ReservesAndSurplus")
    if not names:
        return None, None
    facts = session.execute(
        select(Fact.element, Fact.period_end, Fact.value)
        .where(
            Fact.company_id == company.id,
            Fact.element.in_(names),
            Fact.is_latest,
            Fact.is_instant,
            Fact.consolidated == consolidated,
            Fact.dimensions == {},
        )
        .order_by(Fact.period_end.desc())
    ).all()
    by_end: dict[date, dict[str, Decimal]] = {}
    for element, end, value in facts:
        if value is not None:
            by_end.setdefault(end, {}).setdefault(element, value)
    for end in sorted(by_end, reverse=True):
        found = by_end[end]
        if taxonomy == "banking":
            if all(n in found for n in names):
                return found["Capital"] + found["ReservesAndSurplus"], end
            continue
        for name in names:
            if name in found:
                return found[name], end
    return None, None


def gather(session: Session, symbol: str, consolidated: bool | None = None) -> CompInputs:
    """Inputs for one company. ``consolidated`` sets the basis to try first; None tries
    consolidated when the company files it. The other basis is used, with a note, when the first
    has fewer than four back-to-back quarters."""
    company = session.scalar(select(Company).where(Company.nse_symbol == symbol))
    if company is None:
        raise LookupError(symbol)
    tax = company.results_taxonomy or "indas"
    notes: list[str] = []
    first = files_consolidated(session, company.id) if consolidated is None else consolidated
    basis, q = first, _quarters(session, company.id, first, tax)
    ends = four_quarters(q)
    if ends is None:
        other = _quarters(session, company.id, not first, tax)
        other_ends = four_quarters(other)
        if other_ends is not None:
            basis, q, ends = not first, other, other_ends
            mine, theirs = (
                ("standalone", "consolidated") if first else ("consolidated", "standalone")
            )
            notes.append(f"{mine}: fewer than four {theirs} quarters")
    revenue = pat = ebitda = yoy = None
    if ends is None:
        notes.append(
            "SME companies file half-yearly results; TTM needs four quarters"
            if company.is_sme
            else "fewer than four back-to-back quarters of results on record"
        )
    else:
        revenue = _sum([_value(q, "revenue", e) for e in ends])
        pat = _sum([_value(q, "pat", e) for e in ends])
        if pat is None:
            notes.append("net profit missing for a quarter in the last four")
        if tax == "indas" and not is_financial(company):
            ebitda = _sum([derive(q, e)["=ebitda"] for e in ends])
        latest = ends[0]
        year_ago = date(latest.year - 1, latest.month, latest.day)
        yoy = change(_value(q, "revenue", latest), _value(q, "revenue", year_ago), "inr")
    book, book_at = book_value(session, company, basis)
    price = session.scalar(
        select(Price).where(Price.company_id == company.id).order_by(Price.trade_date.desc())
    )
    if price is None:
        notes.append("no closing price loaded")
    elif price.market_cap is None:
        notes.append("no market cap: no share count in its results filings")
    return CompInputs(
        symbol,
        company.name,
        price.market_cap if price else None,
        debt=None,
        cash=None,
        ttm_revenue=revenue,
        ttm_ebitda=ebitda,
        ttm_pat=pat,
        book_value=book,
        as_of=price.trade_date if price else None,
        notes=notes,
        consolidated=basis,  # the basis looked up, TTM or not (the book value uses it too)
        sector=company.sector,
        taxonomy=tax,
        price=price.close if price else None,
        quarter_end=ends[0] if ends else None,
        revenue_yoy=yoy,
        book_value_at=book_at,
    )


def clean_symbols(symbols: list[str]) -> list[str]:
    """Upper case, trimmed, each once, in the order given."""
    out: list[str] = []
    for raw in symbols:
        s = raw.strip().upper()
        if s and s not in out:
            out.append(s)
    return out


def build_table(
    session: Session, symbols: list[str], consolidated: bool | None = None
) -> tuple[list[CompRow], list[str]]:
    """Rows for the symbols Analekh knows, and the ones it doesn't (a saved list can outlive a
    delisting or a symbol change), so one stale symbol never breaks the table."""
    from analekh.universe.search import get as get_company

    rows: list[CompRow] = []
    missing: list[str] = []
    for symbol in clean_symbols(symbols)[:MAX_COMPANIES]:
        company = get_company(session, symbol)
        if company is None:
            missing.append(symbol)
            continue
        rows.append(compute(gather(session, company.nse_symbol, consolidated)))
    return rows, missing


def suggest_peers(session: Session, company: Company, limit: int = 8) -> list[Company]:
    """Companies in the same sector and results format with a market cap, closest in size first;
    within NSE's broad sectors, those in the same LSEG group come first."""
    if not company.sector:
        return []
    latest = select(func.max(Price.trade_date)).scalar_subquery()
    rows = session.execute(
        select(Company, Price.market_cap)
        .join(Price, Price.company_id == Company.id)
        .where(
            Price.trade_date == latest,
            Price.market_cap.is_not(None),
            Price.market_cap > 0,
            Company.is_active,
            Company.sector == company.sector,
            Company.id != company.id,
            func.coalesce(Company.results_taxonomy, "indas")
            == (company.results_taxonomy or "indas"),
        )
    ).all()
    own = session.scalar(
        select(Price.market_cap).where(Price.company_id == company.id, Price.trade_date == latest)
    )

    pairs = [(peer, cap) for peer, cap in rows if cap is not None]

    def rank(row: tuple[Company, Decimal]) -> tuple[int, float]:
        peer, cap = row
        other_group = int(bool(company.sector_lseg) and peer.sector_lseg != company.sector_lseg)
        distance = abs(math.log(float(cap) / float(own))) if own and own > 0 else -float(cap)
        return other_group, distance

    return [peer for peer, _ in sorted(pairs, key=rank)[:limit]]


def to_xlsx(rows: list[CompRow], title: str = "Comparable companies") -> bytes:
    out = io.BytesIO()
    wb = xlsxwriter.Workbook(out, {"in_memory": True})
    ws = wb.add_worksheet("Comps")
    bold = wb.add_format({"bold": True, "bottom": 1})
    num = wb.add_format({"num_format": "#,##0"})
    money = wb.add_format({"num_format": "#,##0.00"})
    mult = wb.add_format({"num_format": '0.0"x"'})
    pct = wb.add_format({"num_format": '0.0"%"'})
    ws.write(0, 0, title, wb.add_format({"bold": True, "font_size": 14}))
    ws.write(
        1,
        0,
        "INR crore; TTM = last four reported quarters; YoY = latest quarter on a year earlier; "
        "n.m. = not meaningful; n.a. = not available; check Basis before comparing",
    )
    headers = [
        "Company",
        "Basis",
        "Price",
        "Mkt cap",
        "TTM revenue",
        "TTM EBITDA",
        "TTM PAT",
        "Revenue YoY",
        "EBITDA margin",
        "Net margin",
        "P/E",
        "P/B",
        "EV/EBITDA",
        "Notes",
    ]
    for c, h in enumerate(headers):
        ws.write(3, c, h, bold)
    for r, row in enumerate(rows, start=4):
        i = row.inputs
        ws.write(r, 0, i.name)
        ws.write(r, 1, BASIS_LABEL[i.consolidated])
        ws.write(r, 2, float(i.price), money) if i.price is not None else ws.write(r, 2, "n.a.")
        amounts = [i.market_cap, i.ttm_revenue, i.ttm_ebitda, i.ttm_pat]
        for c, v in enumerate(amounts, start=3):
            ws.write(r, c, float(v / CRORE), num) if v is not None else ws.write(r, c, "n.a.")
        for c, v in enumerate([i.revenue_yoy, i.ebitda_margin, i.pat_margin], start=7):
            ws.write(r, c, float(v), pct) if v is not None else ws.write(r, c, "n.a.")
        for c, v in enumerate([row.pe, row.pb, row.ev_ebitda], start=10):
            ws.write(r, c, float(v), mult) if v is not None else ws.write(r, c, "n.m.")
        ws.write(r, 13, "; ".join(i.notes))
    stats = summary_stats(rows)
    base = 4 + len(rows) + 1
    columns = {7: "revenue_yoy", 8: "ebitda_margin", 9: "pat_margin", 10: "pe", 11: "pb"}
    columns[12] = "ev_ebitda"
    for k, label in enumerate(("median", "mean")):
        ws.write(base + k, 0, label.capitalize(), bold)
        for c, metric in columns.items():
            v = stats[metric][label]
            fmt = pct if c < 10 else mult
            ws.write(base + k, c, float(v), fmt) if v is not None else ws.write(base + k, c, "n.m.")
    ws.write(base + 3, 0, "EV/EBITDA needs balance-sheet debt and cash, not sourced yet.")
    ws.set_column(0, 0, 32)
    ws.set_column(1, 12, 12)
    ws.set_column(13, 13, 48)
    wb.close()
    return out.getvalue()
