"""V11: rupee amounts tagged in the wrong unit (validate/rules.py). Numbers are SYNTHETIC, shaped
like Metro Brands' consolidated September 2025 filing (every amount 100 times too small)."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from analekh.db.models import Company, Fact, Filing
from analekh.ingest.pipeline import ingest_results_xbrl, revalidate_company
from analekh.validate.rules import HistoryFact, ValidationContext, validate
from analekh.xbrl.parser import parse_instance
from tests.xbrl_factory import build_instance, pnl

CR = 10_000_000
Q2 = (date(2025, 7, 1), date(2025, 9, 30))
NEIGHBOURS = [  # (start, end, revenue in crore)
    (date(2025, 4, 1), date(2025, 6, 30), 628),
    (date(2025, 10, 1), date(2025, 12, 31), 700),
    (date(2026, 1, 1), date(2026, 3, 31), 690),
    (date(2026, 4, 1), date(2026, 6, 30), 720),
]


def quarter_file(revenue_cr: float, nature: str, start=Q2[0], end=Q2[1], divide: int = 1) -> bytes:
    rev = int(revenue_cr * CR)
    q = pnl(rev, rev // 25, rev * 85 // 100, rev // 40)
    q = {k: v // divide for k, v in q.items()}
    q["BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations"] = 249
    return build_instance(q_start=start, q_end=end, ytd_start=start, values_q=q, nature=nature)


def history(values: list[tuple[date, date, int]]) -> list[HistoryFact]:
    return [HistoryFact("RevenueFromOperations", s, e, Decimal(v * CR), 0) for s, e, v in values]


def standalone_q2() -> list[HistoryFact]:
    return history([(*Q2, 636)])


EPS = "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations"


def with_real_eps_unit(parsed):
    """The synthetic builder tags every value in INR; real filings tag EPS per share."""
    return replace(
        parsed,
        facts=[replace(f, unit="INR/shares") if f.element == EPS else f for f in parsed.facts],
    )


def test_amounts_100_times_too_small_are_corrected_when_both_signals_agree():
    parsed = with_real_eps_unit(parse_instance(quarter_file(651.14, "Consolidated", divide=100)))
    ctx = ValidationContext(parsed, history=history(NEIGHBOURS), other_basis=standalone_q2())
    report = validate(ctx)
    v11 = report.results[-1]
    assert (v11.rule, v11.status, v11.action) == ("V11", "fail", "flag")
    assert "100 times too small; corrected" in v11.message
    assert report.scale == Decimal(100) and not report.blocks_auto_apply
    corrected = {f.element: f.value for f in report.filing.facts if f.period_start == Q2[0]}
    assert corrected["RevenueFromOperations"] == Decimal(int(651.14 * CR) // 100 * 100)
    assert corrected[EPS] == 249
    # V1-V10 judged the corrected filing.
    assert next(r for r in report.results if r.rule == "V1").status == "pass"


def test_the_correct_filing_on_the_other_basis_is_left_alone():
    parsed = parse_instance(quarter_file(636, "Standalone"))
    bad_consolidated = history([(*Q2, 6)])
    report = validate(ValidationContext(parsed, history=history(NEIGHBOURS), other_basis=bad_consolidated))
    assert report.results[-1].status == "pass" and report.scale is None


def test_one_signal_alone_is_a_suspect_never_a_correction():
    parsed = parse_instance(quarter_file(651.14, "Consolidated", divide=100))
    report = validate(ValidationContext(parsed, history=history(NEIGHBOURS)))
    v11 = report.results[-1]
    assert (v11.status, v11.action, v11.details["status"]) == ("fail", "block", "suspect")
    assert report.scale is None and report.blocks_auto_apply


def test_real_jumps_and_holding_companies_pass():
    small = parse_instance(quarter_file(30, "Standalone"))
    report = validate(ValidationContext(small, history=history([(s, e, 10) for s, e, _ in NEIGHBOURS])))
    assert report.results[-1].status == "pass"
    holdco = parse_instance(quarter_file(651.14, "Consolidated"))
    report = validate(ValidationContext(holdco, history=history(NEIGHBOURS), other_basis=history([(*Q2, 6)])))
    assert report.results[-1].status == "pass" and report.scale is None


def test_both_bases_slipped_together_are_corrected():
    parsed = with_real_eps_unit(parse_instance(quarter_file(651.14, "Consolidated", divide=100)))
    standalone = history([(s, e, v - 10) for s, e, v in NEIGHBOURS] + [(*Q2, 6)])
    report = validate(ValidationContext(parsed, history=history(NEIGHBOURS), other_basis=standalone))
    assert report.results[-1].details["status"] == "corrected" and report.scale == Decimal(100)


def test_the_twin_of_a_corrected_filing_is_corrected_too():
    parsed = with_real_eps_unit(parse_instance(quarter_file(612, "Standalone", divide=100)))
    own = history([(s, e, v - 20) for s, e, v in NEIGHBOURS])
    consolidated = history(NEIGHBOURS + [(*Q2, 651)])
    report = validate(ValidationContext(parsed, history=own, other_basis=consolidated))
    assert report.results[-1].details["status"] == "corrected" and report.scale == Decimal(100)
    holdco = parse_instance(quarter_file(0.06, "Standalone"))
    report = validate(ValidationContext(holdco, history=history([(s, e, 6) for s, e, _ in NEIGHBOURS]), other_basis=consolidated))
    assert report.scale is None


def test_a_real_jump_reported_on_both_bases_passes():
    parsed = parse_instance(quarter_file(318, "Standalone"))
    own = history([(s, e, 3) for s, e, _ in NEIGHBOURS])
    consolidated = history([(s, e, 280) for s, e, _ in NEIGHBOURS] + [(*Q2, 270)])
    report = validate(ValidationContext(parsed, history=own, other_basis=consolidated))
    assert report.results[-1].status == "pass" and report.scale is None


def _company(db, symbol):
    c = Company(nse_symbol=symbol, name=f"{symbol.title()} Limited", isin=f"INE{symbol[:5]}0101")
    db.add(c)
    db.flush()
    return c


def test_ingest_stores_corrected_amounts_and_revalidating_never_doubles_them(db, store):
    co = _company(db, "METROX")
    for start, end, rev in NEIGHBOURS:
        ingest_results_xbrl(db, store, co, quarter_file(rev, "Consolidated", start, end))
    ingest_results_xbrl(db, store, co, quarter_file(636, "Standalone"))
    bad = ingest_results_xbrl(db, store, co, quarter_file(651.14, "Consolidated", divide=100))
    assert bad.filing.meta["scale"]["status"] == "corrected"
    assert bad.filing.meta["scale"]["factor"] == "100"

    def revenue() -> Decimal:
        return db.scalar(
            select(Fact.value).where(
                Fact.filing_id == bad.filing.id,
                Fact.element == "RevenueFromOperations",
                Fact.period_start == Q2[0],
            )
        )

    def precision() -> set[int | None]:
        return set(db.scalars(select(Fact.decimals).where(Fact.filing_id == bad.filing.id, Fact.unit == "INR")))

    assert revenue() > 600 * CR
    filed = {f.decimals for f in parse_instance(quarter_file(1, "Consolidated")).facts}
    for _ in range(2):  # twice: the factor is applied to the values as filed, never on top
        revalidate_company(db, store, co)
        db.refresh(bad.filing)
        assert revenue() > 600 * CR and revenue() < 700 * CR
        assert precision() == {d - 2 if d is not None else None for d in filed}
    standalone = db.scalar(select(Filing).where(Filing.company_id == co.id, Filing.consolidated.is_(False)))
    assert "scale" not in standalone.meta
