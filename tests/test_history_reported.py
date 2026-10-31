"""The results history shows a lender's own reported NIM and cost of funds beside, and tagged apart
from, the figures Analekh calculates."""

from decimal import Decimal

from analekh.db.models import InvestorDeck, ReportedRatio
from analekh.history import history, to_xlsx
from analekh.interest import BANK_SECTORS
from tests import test_builder
from tests.test_builder import QUARTERS

company = test_builder.company  # the lender fixture, reused


def _lender(company):
    company.sector = sorted(BANK_SECTORS)[0]  # a lender, so the interest ratios are shown


def _deck(db, company):
    deck = InvestorDeck(company_id=company.id, url="https://nsearchives.nseindia.com/corporate/x.pdf", status="read", ratios=3)
    db.add(deck)
    db.flush()
    return deck


def test_reported_lines_are_separate_and_tagged(db, company):
    _lender(company)
    deck = _deck(db, company)
    last = QUARTERS[-1]
    db.add_all(
        [
            ReportedRatio(company_id=company.id, period_end=last, metric="nim", basis="all", value=Decimal("6.10"), deck_id=deck.id, page=1, layer="sentence"),
            ReportedRatio(company_id=company.id, period_end=last, metric="cof", basis="all", value=Decimal("8.40"), deck_id=deck.id, page=1, layer="sentence"),
        ]
    )
    db.flush()
    h = history(db, company, quarters=len(QUARTERS))
    by_key = {line.key: line for line in h.lines}
    assert by_key["nim_reported"].source == "reported" and by_key["nim_reported"].values[-1] == Decimal("6.10")
    assert by_key["cof_reported"].values[-1] == Decimal("8.40") and by_key["cof_reported"].values[0] is None
    # calculated rows (none here: the synthetic filings carry no interest lines) are never replaced by the reported ones
    calculated = [k for k, line in by_key.items() if line.source == "calculated"]
    assert set(calculated) <= {"nim", "yield", "cob", "spread"}
    # lines that are plain filed figures carry no tag
    assert by_key["revenue"].source is None
    assert b"Net interest margin (reported)" in _cells(to_xlsx(h, company))


def test_no_reported_rows_without_a_deck(db, company):
    _lender(company)
    h = history(db, company, quarters=len(QUARTERS))
    assert not [line for line in h.lines if line.source == "reported"]


def _cells(xlsx: bytes) -> bytes:
    import io
    import zipfile

    with zipfile.ZipFile(io.BytesIO(xlsx)) as z:
        return z.read("xl/sharedStrings.xml")
