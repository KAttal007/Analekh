"""Deck reader: quarter labels in every notation, metric labels, and the three fixes of 2026-10-31."""

from datetime import date

import pymupdf
import pytest

from analekh.decks import entities, reader

SEP26 = date(2026, 9, 30)


@pytest.mark.parametrize(
    "label",
    [
        "Q2FY27", "Q2 FY27", "Q2 FY2027", "Q2-2027", "Q2- 2027", "Q2 2026-27", "Q2FY2026-27", "2QFY27", "2Q27",
        "Sep'26", "Sep-26", "Sep 26", "Sep 2026", "September 2026", "Sept'26", "Sep’26", "Jul-Sep'26", "Jul-Sep 2026",
        "30-Sep-26", "30 Sep 2026", "30.09.2026", "30/09/2026", "Quarter ended 30-Sep-2026", "Sep'26 Quarterly", "q2fy27",
    ],
)  # fmt: skip
def test_every_notation_of_the_quarter_gives_one_date(label):
    assert reader.parse_period(label) == ("Q", SEP26)


@pytest.mark.parametrize(
    ("label", "want"),
    [("Q1FY27", date(2026, 6, 30)), ("Q3FY26", date(2025, 12, 31)), ("Q4FY26", date(2026, 3, 31)), ("Mar'26", date(2026, 3, 31)), ("Dec 2025", date(2025, 12, 31)), ("31.03.2026", date(2026, 3, 31))],
)
def test_other_quarters(label, want):
    assert reader.parse_period(label) == ("Q", want)


@pytest.mark.parametrize(
    "label",
    [
        "H1FY27", "H1 FY27", "H1-2027", "1HFY27", "9MFY27", "9M FY27", "FY2026", "FY27", "Sep'26 Cumulative", "YTD Sep'26",
        "Half Year ended Sep'26", "Six months ended 30-Sep-26", "Year ended 31-Mar-26", "Mar 31", "Oct'26", "Q5FY27", "Q2",
    ],
)  # fmt: skip
def test_half_years_cumulative_and_full_years_are_never_a_quarter(label):
    assert reader.parse_period(label)[0] != "Q"


def test_a_bare_quarter_takes_the_year_the_deck_states():
    assert reader.parse_period("Q1", fy_hint=2027) == ("Q", date(2026, 6, 30))


@pytest.mark.parametrize("label", ["Net Interest Margin", "Net interest margin1,2", "NIM", "NIM (%)", "NIM (Whole Bank)", "NIM - Domestic"])
def test_metric_labels_accepted(label):
    reader.use_metric("nim")
    assert reader.accept_metric(label)


@pytest.mark.parametrize("label", ["Risk Adjusted NIM (%)", "Core NIM", "Net interest margin excl. one-off", "NIM impact", "Net interest income"])
def test_metric_labels_rejected(label):
    reader.use_metric("nim")
    assert not reader.accept_metric(label)


def test_cost_of_funds_label_and_its_exclusions():
    reader.use_metric("cof")
    assert reader.accept_metric("Cost of Funds (%)") and reader.accept_metric("COST OF FUNDS(%)")
    assert not reader.accept_metric("Incremental cost of funds")


def test_a_shared_title_ending_in_and_is_still_a_title():
    """ESAF: 'Cost of Funds and Cost of Deposits (%)' is one title over one chart (the text left of the second term ends in 'and')."""
    doc = pymupdf.open()
    page = doc.new_page(width=960, height=540)
    page.insert_text((40, 60), "Cost of Funds and Cost of Deposits (%)", fontsize=12)
    reader.use_metric("cod")
    # no axis on this page, so nothing is read; the title must not raise and must not be mistaken for a legend entry
    assert reader.chart_layer(page, 1) == []


def test_titles_of_a_business_statement_are_a_segment_not_the_company():
    entities.set_names({"CHOLAFIN": "Cholamandalam Investment and Finance Company Limited", "SHANKARA": "Shankara Building Products Limited"})
    assert entities.parse_title("Profit and Loss Statement – Vehicle Finance (Managed)", "CHOLAFIN")[0] == "other:Vehicle Finance (Managed)"
    assert entities.parse_title("Profit and Loss Statement – CSEL", "CHOLAFIN")[0] == "other:CSEL"
    assert entities.parse_title("Profit and Loss Statement (As per IND AS)", "CHOLAFIN") == (None, None)


def test_an_acronym_names_a_company_only_inside_its_own_group():
    entities.set_names({"BAJFINANCE": "Bajaj Finance Limited", "BAJAJHFL": "Bajaj Housing Finance Limited", "SHANKARA": "Shankara Building Products Limited"})
    assert entities.parse_title("Executive summary - BHFL", "BAJFINANCE")[0] == "BAJAJHFL"
    assert entities.parse_title("Executive summary - Bajaj Finance", "BAJFINANCE")[0] == "self"
    assert entities.parse_title("Executive summary - SBPL", "BAJFINANCE")[0] != "SHANKARA"
