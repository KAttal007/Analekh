"""Numbers the analyst types are checked against the company's data, not only what the AI fetched."""

from datetime import date
from decimal import Decimal

import pytest

from analekh.db.models import Company, Fact, Filing, Kpi
from analekh.reports.sourced import unsourced_numbers
from analekh.reports.threads import create_thread


@pytest.fixture
def thread(db, analyst):
    co = Company(nse_symbol="SRCCO", name="Sourced Co Limited", isin="INE000S01011")
    db.add(co)
    db.flush()
    filing = Filing(company_id=co.id, kind="results_xbrl", period_end=date(2026, 9, 30), file_sha256="s" * 64, storage_key="x")
    db.add(filing)
    db.flush()
    db.add(Fact(filing_id=filing.id, company_id=co.id, element="ProfitLoss", period_end=date(2026, 9, 30), is_instant=False, consolidated=True, value=Decimal("2100000000"), dims_hash="d"))
    db.add(Fact(filing_id=filing.id, company_id=co.id, element="ProfitLoss", period_end=date(2020, 9, 30), is_instant=False, consolidated=True, value=Decimal("7770000000"), dims_hash="d2"))
    db.add(Kpi(filing_id=filing.id, company_id=co.id, name="nim", value=Decimal("3.42"), period_end=date(2026, 9, 30)))
    db.flush()
    return create_thread(db, analyst.id, co.id, "quarterly", "word", "both", quarter_end=date(2026, 9, 30))


def test_a_filed_figure_the_ai_never_fetched_is_sourced(db, thread):
    assert unsourced_numbers(db, thread, "Net profit was INR 210 crore and NIM 3.4%.", []) == []


def test_a_number_matching_nothing_is_reported(db, thread):
    assert unsourced_numbers(db, thread, "Net profit was INR 210 crore and margin 18.2%.", []) == ["18.2%"]


def test_thread_tool_results_count_as_sources(db, thread):
    assert unsourced_numbers(db, thread, "Growth was 41.5%.", [{"result": "41.5"}]) == []


def test_facts_far_outside_the_reports_periods_do_not_count(db, thread):
    assert unsourced_numbers(db, thread, "Net profit was INR 777 crore.", []) == ["777"]
