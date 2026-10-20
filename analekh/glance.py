"""Latest quarter at a glance: the quarter's P&L lines with change on the previous quarter and on
the same quarter a year earlier, in the company's own results format (Ind-AS, bank, general or
life insurer).

Everything comes from stored XBRL facts on one basis; derived lines (EBITDA, net interest income,
margins) are computed here in Decimal and say how. Nothing is shown that the filing doesn't give.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from analekh.db.models import Company, Fact, Filing
from analekh.facts import files_consolidated
from analekh.xbrl.elements import candidates
from analekh.xbrl.parser import period_type

if TYPE_CHECKING:  # restatements imports this module
    from analekh.restatements import Revision

Kind = Literal["inr", "eps", "pct"]
HUNDRED = Decimal(100)

# (logical name, label, kind) in display order, per results format. Logical names starting with
# "=" are derived below; the rest come straight from the filing.
LINES: dict[str, list[tuple[str, str, Kind]]] = {
    "indas": [
        ("revenue", "Revenue", "inr"),  # from operations; other income is its own line
        ("=ebitda", "EBITDA", "inr"),
        ("=ebitda_margin", "EBITDA margin", "pct"),
        ("other_income", "Other income", "inr"),
        ("depreciation", "Depreciation", "inr"),
        ("finance_costs", "Finance costs", "inr"),
        ("exceptional_items", "Exceptional items", "inr"),
        ("pbt", "Profit before tax", "inr"),
        ("tax", "Tax", "inr"),
        ("pat", "Net profit", "inr"),
        ("=net_margin", "Net margin", "pct"),
        ("eps_basic", "EPS (basic)", "eps"),
    ],
    "banking": [
        ("revenue", "Interest earned", "inr"),
        ("interest_expended", "Interest expended", "inr"),
        ("=nii", "Net interest income", "inr"),
        ("other_income", "Other income", "inr"),
        ("operating_expenses", "Operating expenses", "inr"),
        ("operating_profit", "Operating profit (pre-provision)", "inr"),
        ("provisions", "Provisions", "inr"),
        ("pbt", "Profit before tax", "inr"),
        ("pat", "Net profit", "inr"),
        ("eps_basic", "EPS (basic)", "eps"),
    ],
    "insurance": [
        ("gross_premium", "Gross premium written", "inr"),
        ("net_premium", "Net premium written", "inr"),
        ("revenue", "Premium earned", "inr"),
        ("investment_income", "Investment income", "inr"),
        ("operating_profit", "Operating profit", "inr"),
        ("pbt", "Profit before tax", "inr"),
        ("pat", "Net profit", "inr"),
        ("eps_basic", "EPS (basic)", "eps"),
    ],
    "life_insurance": [
        ("gross_premium", "Gross premium income", "inr"),
        ("revenue", "Net premium income", "inr"),
        ("pbt", "Profit before tax", "inr"),
        ("pat", "Net profit", "inr"),
        ("eps_basic", "EPS (basic)", "eps"),
        ("solvency_ratio", "Solvency ratio", "pct"),
        ("persistency_13m", "13th-month persistency", "pct"),
        ("persistency_61m", "61st-month persistency", "pct"),
        ("expense_ratio", "Expenses of management", "pct"),
    ],
}
# Ratios the filing tags as fractions (life insurers: solvency 1.8041), shown as percentages.
AS_FRACTION = {"solvency_ratio", "persistency_13m", "persistency_61m", "expense_ratio"}
NOTES = {
    "=ebitda": "PBT + finance costs + D&A - other income, before exceptionals",
    "=nii": "Interest earned - interest expended",
    # The filing's own EPS: a bonus issue or split between the two quarters moves it (HDFC Bank's
    # 2025 1:1 bonus halved it) without any change in profit.
    "eps_basic": "As filed; not bonus- or split-adjusted",
    "solvency_ratio": "Available over required solvency margin; IRDAI's minimum is 150%",
    "persistency_13m": "Policies still paying premiums 13 months after issue",
    "persistency_61m": "Policies still paying premiums 61 months after issue",
    "expense_ratio": "Commission + operating expenses, as a share of gross premium",
}
# EBITDA adds back finance costs, which for a lender are the cost of doing business (an NBFC's
# "EBITDA margin" comes out near 90%), so it is left out for these sectors. LSEG's "Banking
# Services" also holds the NBFCs; fintech and exchanges keep EBITDA.
FINANCIAL_SECTORS = {
    "Banking Services",
    "Insurance",
    "Investment Banking & Investment Services",
    "Holding Companies",
}
NOT_FOR_FINANCIALS = {"=ebitda", "=ebitda_margin"}


def is_financial(company: Company) -> bool:
    """A lender, insurer or investment company, for which EBITDA means nothing. NSE's single
    "Financial Services" sector holds exchanges too, so LSEG's finer group decides where the
    company has one (Bajaj Finance: Banking Services); without it, EBITDA is kept."""
    return company.sector in FINANCIAL_SECTORS or company.sector_lseg in FINANCIAL_SECTORS


# Shown only when non-zero this quarter: a row of zeros is noise.
ONLY_WHEN_NONZERO = {"exceptional_items"}


@dataclass
class Line:
    key: str
    label: str
    kind: Kind
    value: Decimal | None
    qoq: Decimal | None  # % change; basis points for margins
    yoy: Decimal | None
    note: str | None = None


@dataclass
class Glance:
    consolidated: bool
    taxonomy: str
    period_start: date | None = None
    period_end: date | None = None
    quarter_label: str | None = None  # e.g. "Q1 FY27" (Indian financial year, April-March)
    previous_end: date | None = None
    year_ago_end: date | None = None
    # Why QoQ / YoY are blank throughout, when the comparison quarter has no figures at all.
    previous_note: str | None = None
    year_ago_note: str | None = None
    revision: "Revision | None" = None  # the quarter's figures come from a refiled filing
    lines: list[Line] = field(default_factory=list)


def quarter_label(end: date) -> str:
    fy = end.year + 1 if end.month >= 4 else end.year
    q = {6: 1, 9: 2, 12: 3, 3: 4}.get(end.month)
    return f"Q{q} FY{fy % 100:02d}" if q else f"Quarter ended {end:%d %b %Y}"


def _day(d: date) -> str:
    return f"{d.day} {d:%b %Y}"


def missing_quarter_note(session: Session, company_id: int, consolidated: bool, end: date) -> str:
    """Why a comparison quarter has no figures, for the tooltip on its dash. A company's first
    results after listing can cover a half-year only (Canara Robeco AMC, September 2025), and
    the quarter inside it is then never filed on its own."""
    label = quarter_label(end)
    basis = "consolidated" if consolidated else "standalone"
    covering = session.execute(
        select(Filing.period_start, Filing.period_type).where(
            Filing.company_id == company_id,
            Filing.kind == "results_xbrl",
            Filing.consolidated == consolidated,
            Filing.period_end == end,
        )
    ).first()
    if covering is not None and covering.period_type != "Q" and covering.period_start:
        return (
            f"{label} wasn't filed as a quarter: the {basis} results for {_day(end)} cover "
            f"{_day(covering.period_start)} to {_day(end)} only"
        )
    return f"No {basis} results for {label} on record"


def _latest_revision(
    session: Session, company: Company, consolidated: bool, end: date
) -> "Revision | None":
    """The revision status of the filing in use for the quarter, when it was filed more than
    once; None otherwise."""
    from analekh.restatements import revisions

    same = list(
        session.scalars(
            select(Filing).where(
                Filing.company_id == company.id,
                Filing.kind == "results_xbrl",
                Filing.consolidated == consolidated,
                Filing.period_end == end,
            )
        )
    )
    if len(same) < 2:
        return None
    revised = revisions(session, company, same)
    in_use = [r for r in revised.values() if r.superseded_by is None and r.status != "original"]
    return in_use[0] if in_use else None


def suspect_filings(session: Session, company_ids: list[int]) -> set[int]:
    """Filings whose amounts V11 suspects are in the wrong unit and could not correct: their
    figures stay off growth, margins and comps until someone checks the PDF."""
    if not company_ids:
        return set()
    return set(
        session.scalars(
            select(Filing.id).where(
                Filing.company_id.in_(company_ids),
                Filing.meta["scale"]["status"].astext == "suspect",
            )
        )
    )


def _quarters(session: Session, company_id: int, consolidated: bool, taxonomy: str) -> dict:
    """{logical: {period_end: (period_start, value)}} for quarter-length, undimensioned facts,
    leaving out filings V11 suspects of the wrong unit."""
    wanted = {name for lines in LINES.values() for name, _, _ in lines if not name.startswith("=")}
    wanted |= {"pat_continuing"}
    order = {logical: candidates(logical, taxonomy) for logical in wanted}
    elements = sorted({e for names in order.values() for e in names})
    facts = session.scalars(
        select(Fact).where(
            Fact.company_id == company_id,
            Fact.is_latest,
            Fact.consolidated == consolidated,
            Fact.dimensions == {},
            Fact.is_instant.is_(False),
            Fact.element.in_(elements),
        )
    )
    out: dict[str, dict[date, tuple[date, Decimal]]] = {}
    rank: dict[tuple[str, date], int] = {}
    suspect = suspect_filings(session, [company_id])
    for f in facts:
        if f.value is None or f.period_start is None or f.filing_id in suspect:
            continue
        if period_type(f.period_start, f.period_end) != "Q":
            continue
        for logical, names in order.items():
            if f.element not in names:
                continue
            r = names.index(f.element)  # first candidate wins when a filing tags several
            if rank.get((logical, f.period_end), 99) > r:
                rank[(logical, f.period_end)] = r
                out.setdefault(logical, {})[f.period_end] = (f.period_start, f.value)
    return out


def derive(q: dict, end: date) -> dict[str, Decimal | None]:
    def v(name: str) -> Decimal | None:
        hit = q.get(name, {}).get(end)
        return hit[1] if hit else None

    vals: dict[str, Decimal | None] = {}
    revenue, pbt, exc = v("revenue"), v("pbt"), v("exceptional_items")
    fin, dep, oth = v("finance_costs"), v("depreciation"), v("other_income")
    ebitda: Decimal | None = None
    if pbt is not None and fin is not None and dep is not None and oth is not None:
        ebitda = pbt - (exc if exc is not None else Decimal(0)) + fin + dep - oth
    vals["=ebitda"] = ebitda
    vals["=ebitda_margin"] = ebitda / revenue * HUNDRED if ebitda is not None and revenue else None
    pat = v("pat")
    vals["=net_margin"] = pat / revenue * HUNDRED if pat is not None and revenue else None
    ie = v("interest_expended")
    vals["=nii"] = revenue - ie if revenue is not None and ie is not None else None
    return vals


def change(cur: Decimal | None, prev: Decimal | None, kind: Kind) -> Decimal | None:
    if cur is None or prev is None:
        return None
    if kind == "pct":  # margins move in basis points (100 bps = 1 percentage point)
        return ((cur - prev) * HUNDRED).quantize(Decimal("1"))
    if prev == 0:
        return None
    return ((cur - prev) / abs(prev) * HUNDRED).quantize(Decimal("0.1"))


def glance(session: Session, company: Company, consolidated: bool | None = None) -> Glance:
    basis = files_consolidated(session, company.id) if consolidated is None else consolidated
    taxonomy = company.results_taxonomy or "indas"
    result = Glance(consolidated=basis, taxonomy=taxonomy)
    q = _quarters(session, company.id, basis, taxonomy)
    ends = q.get("revenue") or q.get("pat") or {}
    if not ends:
        return result
    end = max(ends)
    start = ends[end][0]
    prev_end = start - timedelta(days=1)
    year_ago = date(end.year - 1, end.month, end.day)
    result.period_start, result.period_end = start, end
    result.quarter_label = quarter_label(end)
    result.previous_end, result.year_ago_end = prev_end, year_ago
    result.revision = _latest_revision(session, company, basis, end)
    for at, attr in ((prev_end, "previous_note"), (year_ago, "year_ago_note")):
        if not any(at in q.get(name, {}) for name in ("revenue", "pat", "pat_continuing")):
            setattr(result, attr, missing_quarter_note(session, company.id, basis, at))

    def value(name: str, at: date) -> Decimal | None:
        if name.startswith("="):
            return derive(q, at).get(name)
        hit = q.get(name, {}).get(at)
        if hit is None and name == "pat":  # some filings tag only the continuing-operations line
            hit = q.get("pat_continuing", {}).get(at)
        if hit is None:
            return None
        return hit[1] * HUNDRED if name in AS_FRACTION else hit[1]

    for name, label, kind in LINES.get(taxonomy, LINES["indas"]):
        cur = value(name, end)
        if name in NOT_FOR_FINANCIALS and is_financial(company):
            continue
        if cur is None or (name in ONLY_WHEN_NONZERO and cur == 0):
            continue  # not in this filing: leave the line out rather than show a blank
        result.lines.append(
            Line(
                key=name.lstrip("="),
                label=label,
                kind=kind,
                # Margins are shown to 0.1%, but their change is worked out unrounded, so the
                # bps are exact rather than multiples of 10.
                value=cur.quantize(Decimal("0.1")) if kind == "pct" else cur,
                qoq=change(cur, value(name, prev_end), kind),
                yoy=change(cur, value(name, year_ago), kind),
                note=NOTES.get(name),
            )
        )
    return result
