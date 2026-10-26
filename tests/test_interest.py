"""Lenders' interest ratios (analekh/interest.py): NIM, yield, cost of borrowing, spread, on the
results desk and the company history. SYNTHETIC data."""

from datetime import date
from decimal import Decimal

from analekh.db.models import Company
from analekh.desk import desk
from analekh.history import history
from analekh.ingest.pipeline import ingest_results_xbrl
from analekh.interest import average, balance_at, ratios
from tests.xbrl_factory import build_instance, pnl

CRORE = 10_000_000
MAR, JUN, SEP = date(2026, 3, 31), date(2026, 6, 30), date(2026, 9, 30)


def test_filed_balances_are_used_and_june_is_interpolated_between_march_and_september():
    points = {MAR: Decimal(1000), SEP: Decimal(1200)}
    assert balance_at(points, MAR) == 1000 and balance_at(points, SEP) == 1200
    # 91 of the 183 days from March to September: just under the midpoint.
    assert balance_at(points, JUN) == Decimal(1000) + Decimal(200) * 91 / 183


def test_a_june_quarter_is_a_dash_until_septembers_balance_sheet_is_filed():
    only_march = {"Loans": {MAR: Decimal(1000)}}
    assert balance_at(only_march["Loans"], JUN) is None
    r = ratios(Decimal(40), Decimal(20), only_march, date(2026, 4, 1), JUN)
    assert r.nim is None and r.yield_ is None and r.spread is None


def test_balance_sheets_more_than_a_half_year_apart_are_not_interpolated():
    points = {date(2025, 3, 31): Decimal(800), SEP: Decimal(1200)}
    assert balance_at(points, JUN) is None


def test_a_line_known_at_one_end_only_leaves_the_average_unknown_not_understated():
    parts = {"Loans": {MAR: Decimal(900), SEP: Decimal(1100)}, "Investments": {SEP: Decimal(100)}}
    assert average(parts, ("Loans", "Investments"), JUN, SEP) is None


def test_ratios_never_come_out_as_huge_percentages_from_a_tiny_or_missing_base():
    tiny = {"Loans": {MAR: Decimal(1), SEP: Decimal(1)}}  # a tagging slip: crore read as rupees
    r = ratios(Decimal(40), Decimal(20), tiny, date(2026, 7, 1), SEP)
    assert r.nim is None and r.yield_ is None
    assert ratios(Decimal(40), Decimal(20), {}, date(2026, 7, 1), SEP).nim is None


def test_bank_ratios_tie_out():
    # Shaped like a large bank's September 2026 quarter, in crore.
    parts = {
        "Advances": {MAR: Decimal(2937166), SEP: Decimal(3195566)},
        "Investments": {MAR: Decimal(884201), SEP: Decimal(923997)},
        "BalancesWithBanksAndMoneyAtCallAndShortNotice": {MAR: Decimal(97787), SEP: Decimal(75235)},
        "Deposits": {MAR: Decimal(3105250), SEP: Decimal(3327449)},
        "Borrowings": {MAR: Decimal(489395), SEP: Decimal(489018)},
    }
    r = ratios(Decimal(83427), Decimal(48807), parts, date(2026, 7, 1), SEP)
    assert round(r.yield_, 1) == Decimal("8.1") and round(r.cob, 1) == Decimal("5.2")
    assert round(r.nim, 1) == Decimal("3.4")
    assert r.spread == r.yield_ - r.cob


def _file(db, store, company, start, end, interest, finance, instant=None):
    q = pnl(interest * CRORE, 0, (interest - 10) * CRORE, 0)
    q |= {"InterestEarned": interest * CRORE, "FinanceCosts": finance * CRORE}
    values_instant = {k: v * CRORE for k, v in (instant or {}).items()}
    data = build_instance(
        q_start=start, q_end=end, ytd_start=start, values_q=q, values_instant=values_instant
    )
    ingest_results_xbrl(db, store, company, data)


def test_nbfc_nim_on_the_desk_and_ratios_in_the_history(db, store):
    sector = "Banking Services"
    nbfc = Company(nse_symbol="LENDX", name="Lendx Finance Limited", isin="INE000X01019")
    nbfc.sector = sector
    db.add(nbfc)
    db.flush()
    _file(
        db,
        store,
        nbfc,
        date(2026, 1, 1),
        MAR,
        36,
        18,
        {"Loans": 900, "Investments": 100, "Borrowings": 700, "DebtSecurities": 100},
    )
    _file(db, store, nbfc, date(2026, 4, 1), JUN, 38, 19)  # June: no balance sheet
    _file(
        db,
        store,
        nbfc,
        date(2026, 7, 1),
        SEP,
        40,
        20,
        {"Loans": 1100, "Investments": 100, "Borrowings": 900, "DebtSecurities": 100},
    )

    d = desk(db, quarter_end=SEP, sector=sector, limit=500)
    row = next(r for r in d.rows if r.symbol == "LENDX")
    assert row.margin_kind == "nim" and row.margin_consolidated is True
    # Earning assets: March 1000, June interpolated ~1099.5, September 1200: average ~1149.7.
    # NIM = (40 - 20) x 4 / 1149.7 = 6.96%.
    assert row.margin == Decimal("6.96")
    assert row.margin_yoy is None  # no year-ago balance sheets

    h = history(db, nbfc, consolidated=True)
    lines = {line.key: line for line in h.lines}
    assert set(lines) >= {"nim", "yield", "cob", "spread"}
    by_end = dict(zip(h.quarter_ends, lines["nim"].values, strict=True))
    assert by_end[MAR] is None  # no December balance sheet to average with
    assert by_end[JUN] is not None  # September is filed now, so June is interpolated
    assert by_end[SEP] == Decimal("6.96")
    sep = h.quarter_ends.index(SEP)
    assert lines["spread"].values[sep] == lines["yield"].values[sep] - lines["cob"].values[sep]


def test_ebitda_margin_stays_for_companies_outside_finance(db, store):
    sector = "Margin Test Sector"
    maker = Company(nse_symbol="MAKERX", name="Makerx Limited", isin="INE000Y01017")
    maker.sector = sector
    db.add(maker)
    db.flush()
    q = pnl(100 * CRORE, 0, 80 * CRORE, 5 * CRORE)
    q |= {"FinanceCosts": 2 * CRORE, "DepreciationDepletionAndAmortisationExpense": 3 * CRORE}
    ingest_results_xbrl(
        db,
        store,
        maker,
        build_instance(q_start=date(2026, 7, 1), q_end=SEP, ytd_start=date(2026, 7, 1), values_q=q),
    )
    row = next(r for r in desk(db, quarter_end=SEP, sector=sector).rows if r.symbol == "MAKERX")
    assert row.margin_kind == "ebitda" and row.margin == Decimal("25.0")  # 20 + 2 + 3 on 100


def test_no_nim_for_asset_managers_and_lessors_whose_income_is_mostly_not_interest():
    parts = {"Loans": {MAR: Decimal(1000), SEP: Decimal(1200)}}
    # Interest 3 on revenue 100 (an asset manager): no ratios, not a negative NIM.
    assert ratios(Decimal(3), Decimal(5), parts, date(2026, 7, 1), SEP, Decimal(100)).nim is None
    # Interest 49 of revenue 100 (a card lender with large fee income): still a lender.
    assert ratios(Decimal(49), Decimal(20), parts, date(2026, 7, 1), SEP, Decimal(100)).nim


def _amc(db, store, symbol="ABSLAMC"):
    """An asset manager (named in interest.FEE_FINANCE) with a September 2026 quarter and the
    same quarter a year earlier."""
    sector = "Investment Banking & Investment Services"
    amc = Company(nse_symbol=symbol, name="Test Asset Management Limited", isin="INE000Z01015")
    amc.sector = amc.sector_lseg = sector
    db.add(amc)
    db.flush()
    for start, end, revenue, expenses in (
        (date(2025, 7, 1), date(2025, 9, 30), 160, 100),
        (date(2026, 7, 1), date(2026, 9, 30), 200, 120),
    ):
        q = pnl(revenue * CRORE, 10 * CRORE, expenses * CRORE, 20 * CRORE)
        q |= {"FinanceCosts": 5 * CRORE, "ImpairmentOnFinancialInstruments": 3 * CRORE}
        q |= {"InterestEarned": 4 * CRORE}  # 2% of revenue
        ingest_results_xbrl(
            db, store, amc, build_instance(q_start=start, q_end=end, ytd_start=start, values_q=q)
        )
    return amc, sector


def test_asset_manager_shows_core_pre_provision_margin_not_ebitda_or_nim(db, store):
    amc, sector = _amc(db, store)
    row = next(r for r in desk(db, quarter_end=SEP, sector=sector).rows if r.symbol == "ABSLAMC")
    # Operating expenses = 120 - 5 finance costs - 3 impairment = 112; (200 - 112) / 200 = 44%.
    assert row.margin_kind == "cpppm" and row.margin == Decimal("44.0")
    keys = {line.key for line in history(db, amc, consolidated=True).lines}
    assert "cpppm" in keys and "ebitda_margin" not in keys and "nim" not in keys


def test_operating_leverage_is_revenue_growth_less_expense_growth(db, store):
    amc, _ = _amc(db, store)
    h = history(db, amc, consolidated=True)
    line = next(line for line in h.lines if line.key == "oplev")
    # Revenue 160 -> 200 (+25%); operating expenses 100 - 5 - 3 = 92 -> 112 (+21.74%): +3.26 points.
    assert line.values[h.quarter_ends.index(SEP)] == Decimal("3.3")
    assert line.values[0] is None  # no year-ago quarter for the first one


def test_every_bank_and_nbfc_has_a_nim_kind_even_where_it_cannot_be_worked_out(db, store):
    lessor = Company(nse_symbol="LESSORX", name="Lessorx Finance Limited", isin="INE000V01011")
    lessor.sector = "Banking Services"
    db.add(lessor)
    db.flush()
    q = pnl(100 * CRORE, 0, 60 * CRORE, 10 * CRORE) | {"InterestEarned": 9 * CRORE}  # 9% interest
    ingest_results_xbrl(
        db,
        store,
        lessor,
        build_instance(
            q_start=date(2026, 7, 1),
            q_end=SEP,
            ytd_start=date(2026, 7, 1),
            values_q=q,
            values_instant={"Loans": 500 * CRORE},
        ),
    )
    row = next(
        r
        for r in desk(db, quarter_end=SEP, sector="Banking Services").rows
        if r.symbol == "LESSORX"
    )
    assert row.margin_kind == "nim" and row.margin is None


def test_no_core_pre_provision_margin_outside_fee_finance(db, store):
    maker = Company(nse_symbol="PLAINX", name="Plainx Limited", isin="INE000W01013")
    maker.sector = "Margin Test Sector"
    db.add(maker)
    db.flush()
    q = pnl(100 * CRORE, 0, 80 * CRORE, 5 * CRORE) | {"FinanceCosts": 2 * CRORE}
    ingest_results_xbrl(
        db,
        store,
        maker,
        build_instance(q_start=date(2026, 7, 1), q_end=SEP, ytd_start=date(2026, 7, 1), values_q=q),
    )
    keys = {line.key for line in history(db, maker, consolidated=True).lines}
    assert "cpppm" not in keys


def test_exchanges_keep_ebitda_and_holding_companies_show_operating_income(db, store):
    sector = "Investment Banking & Investment Services"
    q = pnl(100 * CRORE, 0, 80 * CRORE, 5 * CRORE) | {
        "FinanceCosts": 2 * CRORE,
        "DepreciationDepletionAndAmortisationExpense": 3 * CRORE,
    }
    keys = {}
    for n, (symbol, isin) in enumerate((("IEX", "INE000A01011"), ("TATAINVEST", "INE000A01029"))):
        c = Company(nse_symbol=symbol, name=f"{symbol} Limited", isin=isin)
        c.sector = c.sector_lseg = sector
        db.add(c)
        db.flush()
        mine = q | {"FinanceCosts": (2 + n) * CRORE}  # files with the same bytes are stored once
        data = build_instance(
            q_start=date(2026, 7, 1), q_end=SEP, ytd_start=date(2026, 7, 1), values_q=mine
        )
        ingest_results_xbrl(db, store, c, data)
        keys[symbol] = {line.key for line in history(db, c, consolidated=True).lines}
    assert "ebitda_margin" in keys["IEX"] and "opinc" not in keys["IEX"]
    assert "opinc" in keys["TATAINVEST"] and "ebitda_margin" not in keys["TATAINVEST"]
    assert "cpppm" not in keys["IEX"] | keys["TATAINVEST"]
