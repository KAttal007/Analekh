"""Results desk: change on the previous quarter (QoQ) beside the year-on-year change. SYNTHETIC data."""

from datetime import date
from decimal import Decimal

from analekh.db.models import Company
from analekh.desk import _previous_quarter_end, desk
from analekh.ingest.pipeline import ingest_results_xbrl
from tests.xbrl_factory import build_instance, pnl

CRORE = 10_000_000
JUN, SEP, DEC, MAR = date(2026, 6, 30), date(2026, 9, 30), date(2026, 12, 31), date(2027, 3, 31)


def _company(db, symbol: str, sector: str) -> Company:
    c = Company(nse_symbol=symbol, name=f"{symbol.title()} Limited", isin=f"INE{symbol[:6].ljust(6, '0')}01")
    c.sector = sector
    db.add(c)
    db.flush()
    return c


def _file(db, store, company, start, end, revenue, expenses, extra=None):
    q = pnl(revenue * CRORE, 0, expenses * CRORE, 0) | {k: v * CRORE for k, v in (extra or {}).items()}
    ingest_results_xbrl(db, store, company, build_instance(q_start=start, q_end=end, ytd_start=start, values_q=q))


def test_previous_quarter_end_steps_back_one_quarter_across_a_year_boundary():
    assert _previous_quarter_end(SEP) == JUN
    assert _previous_quarter_end(date(2026, 3, 31)) == date(2025, 12, 31)
    assert _previous_quarter_end(date(2026, 6, 30)) == date(2026, 3, 31)


def test_revenue_and_profit_change_on_the_previous_quarter(db, store):
    sector = "Qoq Test Sector"
    co = _company(db, "QOQMAKER", sector)
    _file(db, store, co, date(2026, 4, 1), JUN, 100, 80)  # revenue 100, profit 20
    _file(db, store, co, date(2026, 7, 1), SEP, 110, 85)  # revenue 110, profit 25
    row = next(r for r in desk(db, quarter_end=SEP, sector=sector).rows if r.symbol == "QOQMAKER")
    assert row.revenue_qoq == Decimal("10.0")
    assert row.pat_qoq == Decimal("25.0")
    assert row.revenue_yoy is None  # no year-ago quarter: the two changes are independent


def test_no_previous_quarter_leaves_qoq_blank_not_zero(db, store):
    sector = "Qoq First Sector"
    co = _company(db, "QOQFIRST", sector)
    _file(db, store, co, date(2026, 7, 1), SEP, 110, 85)
    row = next(r for r in desk(db, quarter_end=SEP, sector=sector).rows if r.symbol == "QOQFIRST")
    assert row.revenue_qoq is None and row.pat_qoq is None and row.margin_qoq is None


def test_margin_change_is_in_basis_points_on_the_previous_quarter(db, store):
    sector = "Qoq Margin Sector"
    co = _company(db, "QOQMARGIN", sector)
    extra = {"FinanceCosts": 2, "DepreciationDepletionAndAmortisationExpense": 3}
    _file(db, store, co, date(2026, 4, 1), JUN, 100, 80, extra)  # EBITDA margin 25.0%
    _file(db, store, co, date(2026, 7, 1), SEP, 100, 78, extra)  # EBITDA margin 27.0%
    row = next(r for r in desk(db, quarter_end=SEP, sector=sector).rows if r.symbol == "QOQMARGIN")
    assert row.margin_kind == "ebitda" and row.margin == Decimal("27.0")
    assert row.margin_qoq == Decimal("200")  # 2.0 points = 200 bps


def test_a_loss_making_previous_quarter_gives_no_percentage(db, store):
    sector = "Qoq Loss Sector"
    co = _company(db, "QOQLOSS", sector)
    _file(db, store, co, date(2026, 4, 1), JUN, 100, 100)  # profit 0: no base for a percentage
    _file(db, store, co, date(2026, 7, 1), SEP, 100, 90)
    row = next(r for r in desk(db, quarter_end=SEP, sector=sector).rows if r.symbol == "QOQLOSS")
    assert row.pat_qoq is None and row.revenue_qoq == Decimal("0.0")
