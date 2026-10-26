"""Lenders' interest ratios: net interest margin, yield, cost of borrowing and spread, per quarter.

    NIM    = (interest income - interest expense) x 4 / average interest-earning assets
    Yield  = interest income x 4 / average interest-earning assets
    CoB    = interest expense x 4 / average interest-bearing funding
    Spread = Yield - CoB

Averages are of the quarter's opening and closing balances. Banks and NBFCs file the balance sheet
half-yearly (31 March, 30 September), so the other quarter ends (30 June, 31 December) are
interpolated between the two filed balance sheets around them. A June or December quarter can only
be worked out once the next half-year's balance sheet is filed: until then it is None (a dash),
never a figure on a stale balance sheet. Earning assets and funding are the sums of the lines in
``EARNING_ASSETS`` and ``FUNDING`` a filing tags (elements.py). All in Decimal.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from analekh.db.models import Company, Fact
from analekh.xbrl.elements import EARNING_ASSETS, FUNDING

HUNDRED = Decimal(100)
CENT = Decimal("0.01")  # ratios are shown to 0.01%
ANNUALISE = Decimal(4)  # quarters in a year
# Balance sheets further apart than a half-year (and a little) are not interpolated between.
MAX_GAP = timedelta(days=200)
# A ratio beyond this is a tagging or unit problem in the filing, not a margin: left out.
PLAUSIBLE = Decimal(100)
# A lender's NIM needs interest to be most of its income. Seen September 2026: banks and NBFCs
# 74-100% of revenue from operations, SBI Card 49% (card fees), IRFC (a lessor) 9%. Below the line
# a ratio is not worked out (a dash), never a negative margin from a company that does not earn
# interest.
MIN_INTEREST_SHARE = Decimal("0.4")
BANK_SECTORS = {"Banking Services"}  # banks and NBFCs (LSEG's group also holds NBFCs)
FINANCE_SECTORS = {"Investment Banking & Investment Services"}  # brokers, AMCs, holdings, more

# Which margin a company in the financial sectors shows (owner, 2026-10-26): every bank and NBFC
# its net interest margin ("nim"); every broker, wealth manager and asset manager the core
# pre-provision profit margin ("cpppm"). NSE's and LSEG's sector lists put those two groups
# together with investment holding companies and exchanges, and no field tells them apart, so the
# second group is named here. Companies in the finance sector but not named (holding companies,
# exchanges, shells) show neither: a dash.
FEE_FINANCE = frozenset(
    {
        # Asset managers and alternative-asset managers
        "NAM-INDIA", "ABSLAMC", "HDFCAMC", "ICICIAMC", "SBIFUNDS", "UTIAMC", "CRAMC", "GAJA", "IVC",
        # Wealth managers and distributors
        "360ONE", "ANANDRATHI", "NUVAMA", "WEALTH", "PRUDENT",
        # Brokers, investment and merchant banks
        "5PAISA", "ANGELONE", "ARIHANTCAP", "ARSSBL", "BIRLAMONEY", "DBSTOCKBRO", "GEOJITFSL",
        "IIFLCAPS", "KHANDSE", "LKPSEC", "MONARCH", "MOTILALOFS", "SHAREINDIA", "SMCGLOBAL",
        "ALMONDZ", "INDOTHAI", "INVENTURE", "EMKAY", "CHOICEIN", "DAMCAPITAL", "SYSTMTXC",
        "PRIMESECU", "ARYAMAN", "KEYFINSERV", "MASTERTR", "GCSL", "INDBANK", "AFSL", "DOLATALGO",
        "JMFINANCIL", "ONELIFECAP", "GANGESSECU", "SHARDUL", "PALASHSECU",
    }
)  # fmt: skip
# In the finance sector but lenders: a primary dealer's income is interest on government bonds.
LENDERS_IN_FINANCE = frozenset({"PNBGILTS", "EDELWEISS", "TFL", "LADDERUP", "APOORVA"})


# Exchanges sit in the finance sector but run an operating business: EBITDA margin like anyone's.
EXCHANGES = frozenset({"IEX", "MCX"})


def lender_kind(company: Company) -> Literal["nim", "cpppm", "ebitda", "holding"] | None:
    """What a financial company shows: "nim" (banks, NBFCs), "cpppm" (brokers, asset managers),
    "ebitda" (exchanges), "holding" (holding and investment companies: operating income), or None
    (insurers, and any company outside finance)."""
    if company.results_taxonomy in ("insurance", "life_insurance"):
        return None
    if company.nse_symbol in EXCHANGES:
        return "ebitda"
    if company.nse_symbol in FEE_FINANCE:
        return "cpppm"
    if company.nse_symbol in LENDERS_IN_FINANCE:
        return "nim"
    if company.results_taxonomy == "banking" or BANK_SECTORS & {
        company.sector,
        company.sector_lseg,
    }:
        return "nim"
    # What is left of the finance sectors: holding companies and investment shells.
    if {"Holding Companies"} & {company.sector, company.sector_lseg} or FINANCE_SECTORS & {
        company.sector,
        company.sector_lseg,
    }:
        return "holding"
    return None


KEYS = ("nim", "yield", "cob", "spread")
LABELS = {
    "nim": "Net interest margin",
    "yield": "Yield on earning assets",
    "cob": "Cost of borrowing",
    "spread": "Spread",
}
NOTES = {
    "nim": "(Interest earned - interest expense) x 4 / average interest-earning assets "
    "(advances or loans, investments, bank and call money balances). Computed, not the "
    "lender's reported NIM",
    "yield": "Interest earned x 4 / average interest-earning assets",
    "cob": "Interest expense x 4 / average deposits, borrowings, debt securities and "
    "subordinated liabilities",
    "spread": "Yield - cost of borrowing",
}
AVERAGE_NOTE = (
    "Averages of opening and closing balances; balance sheets are filed half-yearly, so June and "
    "December balances are interpolated, and those quarters show once the next half-year's "
    "balance sheet is filed"
)

Points = dict[date, Decimal]
Balances = dict[str, Points]  # element -> {balance-sheet date: value}


def is_lender(company: Company) -> bool:
    return lender_kind(company) == "nim"


@dataclass
class Ratios:
    nim: Decimal | None = None
    yield_: Decimal | None = None
    cob: Decimal | None = None
    spread: Decimal | None = None

    def get(self, key: str) -> Decimal | None:
        return getattr(self, "yield_" if key == "yield" else key)

    def rounded(self) -> "Ratios":
        """To 0.01%, with the spread worked out from the rounded yield and cost, so the figures
        shown add up (and the stacked chart's spread ends exactly at the yield)."""

        def r(v: Decimal | None) -> Decimal | None:
            return v.quantize(CENT) if v is not None else None

        out = Ratios(nim=r(self.nim), yield_=r(self.yield_), cob=r(self.cob))
        if out.yield_ is not None and out.cob is not None:
            out.spread = out.yield_ - out.cob
        return out


def balances(
    session: Session, company_ids: list[int], suspect: set[int]
) -> dict[tuple[int, bool], Balances]:
    """{(company id, consolidated): {element: {date: value}}} for the earning-asset and funding
    lines, leaving out filings V11 suspects of the wrong unit."""
    out: dict[tuple[int, bool], Balances] = {}
    if not company_ids:
        return out
    rows = session.execute(
        select(
            Fact.company_id,
            Fact.consolidated,
            Fact.element,
            Fact.period_end,
            Fact.value,
            Fact.filing_id,
        ).where(
            Fact.company_id.in_(company_ids),
            Fact.is_latest,
            Fact.is_instant.is_(True),
            Fact.dimensions == {},
            Fact.element.in_(EARNING_ASSETS + FUNDING),
        )
    )
    for r in rows:
        if r.value is None or r.filing_id in suspect:
            continue
        out.setdefault((r.company_id, bool(r.consolidated)), {}).setdefault(r.element, {})[
            r.period_end
        ] = r.value
    return out


def balance_at(points: Points, at: date) -> Decimal | None:
    """The filed balance on the day, or one interpolated between the filed balance sheets on
    either side (no more than a half-year apart); None when either side is not filed yet."""
    if at in points:
        return points[at]
    before = max((d for d in points if d < at), default=None)
    after = min((d for d in points if d > at), default=None)
    if before is None or after is None or after - before > MAX_GAP:
        return None
    share = Decimal((at - before).days) / Decimal((after - before).days)
    return points[before] + (points[after] - points[before]) * share


def average(
    parts: Balances, names: tuple[str, ...], opening: date, closing: date
) -> Decimal | None:
    """Sum over the lines of the average of opening and closing balances. A line known at one end
    and not the other leaves the whole average unknown, rather than understated."""
    total: Decimal | None = None
    for name in names:
        points = parts.get(name)
        if not points:
            continue
        o, c = balance_at(points, opening), balance_at(points, closing)
        if o is None and c is None:
            continue
        if o is None or c is None:
            return None
        total = (total or Decimal(0)) + (o + c) / 2
    return total if total is not None and total > 0 else None


def _plausible(v: Decimal | None) -> Decimal | None:
    return v if v is not None and abs(v) <= PLAUSIBLE else None


def lends(income: Decimal | None, revenue: Decimal | None) -> bool:
    """Interest is at least MIN_INTEREST_SHARE of revenue from operations (a bank's revenue is its
    interest earned, so a bank always qualifies). No revenue figure: judged on income alone."""
    if income is None or income <= 0:
        return False
    return revenue is None or revenue <= 0 or income >= revenue * MIN_INTEREST_SHARE


def ratios(
    income: Decimal | None,
    expense: Decimal | None,
    parts: Balances,
    start: date,
    end: date,
    revenue: Decimal | None = None,
) -> Ratios:
    """One quarter's ratios (``start``..``end``), in percent, unrounded; all None for a company
    whose income is mostly not interest (``lends``)."""
    if not lends(income, revenue):
        return Ratios()
    opening = start - timedelta(days=1)
    assets = average(parts, EARNING_ASSETS, opening, end)
    funding = average(parts, FUNDING, opening, end)
    out = Ratios()
    if assets is not None and income is not None:
        out.yield_ = _plausible(income * ANNUALISE / assets * HUNDRED)
        if expense is not None:
            out.nim = _plausible((income - expense) * ANNUALISE / assets * HUNDRED)
    if funding is not None and expense is not None:
        out.cob = _plausible(expense * ANNUALISE / funding * HUNDRED)
    if out.yield_ is not None and out.cob is not None:
        out.spread = out.yield_ - out.cob
    return out
