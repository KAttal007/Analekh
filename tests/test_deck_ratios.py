"""Reported ratios from investor decks: what is stored, what the desk shows. SYNTHETIC data."""

import json
from datetime import UTC, date, datetime
from decimal import Decimal

import pymupdf

from analekh.db.models import Company, InvestorDeck, ReportedRatio
from analekh.decks.ratios import _resolve
from analekh.desk import _pick_reported, desk
from analekh.ingest.decks import Announcement, fetch_new_decks
from analekh.ingest.http import path_allowed
from analekh.ingest.pipeline import ingest_results_xbrl
from tests.xbrl_factory import build_instance, pnl

JUN, SEP, SEP25 = date(2026, 6, 30), date(2026, 9, 30), date(2025, 9, 30)
CRORE = 10_000_000


def reading(value, basis="unspecified", page=5, quarter=SEP, flags=None, entity="self", layer="chart"):
    return {"quarter": quarter, "value": value, "basis": basis, "page": page, "flags": flags or [], "entity": entity, "layer": layer}


def test_agreeing_readings_are_stored_once():
    kept, _ = _resolve([reading(3.5, page=5), reading(3.5, page=9, layer="table")], set())
    assert kept == [("self", SEP, "all", 3.5, 5, "chart")]


def test_a_disagreement_stores_nothing():
    kept, _ = _resolve([reading(3.5), reading(3.6, page=9)], set())
    assert kept == []


def test_an_explicit_quarterly_column_wins_and_marks_the_other_page():
    kept, overruled = _resolve([reading(3.5, flags=["explicit-quarterly"]), reading(1.7, page=9)], set())
    assert [k[3] for k in kept] == [3.5] and overruled == {9}


def test_consolidated_and_standalone_are_kept_apart():
    kept, _ = _resolve([reading(7.31, "consolidated"), reading(7.40, "standalone", page=31)], set())
    assert {(k[2], k[3]) for k in kept} == {("consolidated", 7.31), ("standalone", 7.40)}


def test_segments_domestic_and_forecasts_are_not_stored():
    kept, _ = _resolve(
        [reading(9.0, entity="other:Vehicle Finance"), reading(3.9, "domestic", page=7), reading(3.8, flags=["forecast-word"], page=8), reading(3.1, page=6)],
        set(),
    )
    assert [k[3] for k in kept] == [3.1]


def test_a_subsidiary_section_is_kept_under_its_own_symbol():
    kept, _ = _resolve([reading(7.04, entity="BAJAJHFL", page=16)], set())
    assert kept[0][0] == "BAJAJHFL"


def test_pages_overruled_for_nim_are_dropped_for_other_metrics():
    kept, _ = _resolve([reading(7.3, page=9)], {9})
    assert kept == []


def test_pick_prefers_the_basis_asked_for_then_the_single_figure():
    rep = {(1, "nim", SEP): {"consolidated": Decimal("7.31"), "standalone": Decimal("7.40")}}
    dates = (SEP, SEP25, JUN)
    assert _pick_reported(rep, 1, "nim", True, dates) == (Decimal("7.31"), None, None, True)
    assert _pick_reported(rep, 1, "nim", False, dates) == (Decimal("7.40"), None, None, False)
    single = _pick_reported({(1, "nim", SEP): {"all": Decimal("3.5")}}, 1, "nim", True, dates)
    assert single is not None and single[3] is True
    assert _pick_reported({}, 1, "nim", True, dates) is None


def test_a_change_needs_the_earlier_quarter_on_the_same_basis():
    rep = {(1, "nim", SEP): {"all": Decimal("3.5")}, (1, "nim", SEP25): {"standalone": Decimal("3.4")}}
    assert _pick_reported(rep, 1, "nim", True, (SEP, SEP25, JUN)) == (Decimal("3.5"), None, None, True)


def test_announcements_accept_only_https_pdfs_on_the_archive_host():
    good = {"symbol": "ABC", "attchmntFile": "https://nsearchives.nseindia.com/corporate/ABC_1.pdf", "an_dt": "31-Oct-2026 16:04:04"}
    parsed = Announcement.from_row(good)
    assert parsed is not None and parsed.symbol == "ABC"
    assert parsed.broadcast_at == datetime(2026, 10, 31, 10, 34, 4, tzinfo=UTC)
    for bad in (
        {**good, "attchmntFile": "http://nsearchives.nseindia.com/corporate/ABC_1.pdf"},
        {**good, "attchmntFile": "https://example.com/corporate/ABC_1.pdf"},
        {**good, "attchmntFile": "https://nsearchives.nseindia.com/other/ABC_1.pdf"},
        {**good, "attchmntFile": "https://nsearchives.nseindia.com/corporate/ABC_1.zip"},
        {**good, "symbol": ""},
    ):
        assert Announcement.from_row(bad) is None


def test_the_announcements_path_is_on_the_allow_list_and_nothing_wider():
    assert path_allowed("www.nseindia.com", "/api/corporate-announcements")
    assert not path_allowed("www.nseindia.com", "/api/quote-equity")


def _lender(db, symbol: str) -> Company:
    c = Company(nse_symbol=symbol, name=f"{symbol.title()} Bank Limited", isin=f"INE{symbol[:6].ljust(6, '0')}01")
    c.sector, c.results_taxonomy = "Deck Test Banks", "banking"
    db.add(c)
    db.flush()
    return c


def _deck(db, company) -> InvestorDeck:
    d = InvestorDeck(company_id=company.id, url=f"https://nsearchives.nseindia.com/corporate/{company.nse_symbol}.pdf", status="read")
    db.add(d)
    db.flush()
    return d


def _filed(db, store, company):
    q = pnl(100 * CRORE, 0, 80 * CRORE, 0)
    ingest_results_xbrl(db, store, company, build_instance(q_start=date(2026, 7, 1), q_end=SEP, ytd_start=date(2026, 4, 1), values_q=q))


def test_the_desk_shows_the_reported_figures_with_changes_on_reported_only(db, store):
    co = _lender(db, "DECKBANK")
    _filed(db, store, co)
    deck = _deck(db, co)
    for metric, at, value in (("nim", SEP, "3.50"), ("nim", SEP25, "3.40"), ("nim", JUN, "3.45"), ("cof", SEP, "5.10"), ("cof", JUN, "5.20")):
        db.add(ReportedRatio(company_id=co.id, period_end=at, metric=metric, basis="all", value=Decimal(value), deck_id=deck.id, page=5, layer="chart"))
    db.flush()
    row = next(r for r in desk(db, quarter_end=SEP, sector="Deck Test Banks").rows if r.symbol == "DECKBANK")
    assert (row.margin, row.margin_source, row.margin_yoy, row.margin_qoq) == (Decimal("3.50"), "reported", Decimal("10.00"), Decimal("5.00"))
    assert (row.cof, row.cof_source, row.cof_yoy, row.cof_qoq) == (Decimal("5.10"), "reported", None, Decimal("-10.00"))


def test_without_a_reported_figure_the_desk_has_no_reported_source(db, store):
    co = _lender(db, "NODECK")
    _filed(db, store, co)
    row = next(r for r in desk(db, quarter_end=SEP, sector="Deck Test Banks").rows if r.symbol == "NODECK")
    assert row.margin_source != "reported" and row.cof_source != "reported"


class FakeClient:
    """Stands in for PoliteClient: a list of announcements and one PDF."""

    def __init__(self, rows, pdf: bytes):
        self.rows, self.pdf, self.asked = rows, pdf, []

    def get(self, url, **kw):
        self.asked.append(url)
        body = json.dumps(self.rows).encode() if "corporate-announcements" in url else self.pdf
        return type("R", (), {"content": body, "status": 200})()


def _pdf(text: str) -> bytes:
    doc = pymupdf.open()
    doc.new_page(width=960, height=540).insert_text((60, 100), text, fontsize=14)
    return doc.tobytes()


def test_a_new_deck_is_read_once_and_its_ratios_stored(db, store):
    co = _lender(db, "READBANK")
    url = "https://nsearchives.nseindia.com/corporate/READBANK_1.pdf"
    other = url.replace("READ", "OTHE")
    rows = [
        {"symbol": "READBANK", "attchmntFile": url, "an_dt": "31-Oct-2026 16:04:04"},
        {"symbol": "OTHERCO", "attchmntFile": other, "an_dt": "31-Oct-2026 16:04:04"},
    ]
    client = FakeClient(rows, _pdf("Net Interest Margin for Q2 FY27 was 3.52%"))
    run = fetch_new_decks(db, store, client)
    assert (run.new, run.read, run.ratios) == (1, 1, 1)  # OTHERCO is not a lender we cover
    stored = db.query(ReportedRatio).filter_by(company_id=co.id).one()
    assert (stored.metric, stored.period_end, stored.value) == ("nim", SEP, Decimal("3.52"))
    again = fetch_new_decks(db, store, client)
    assert again.new == 0  # the ledger remembers the URL
    assert client.asked.count(url) == 1


def test_a_deck_that_is_not_a_pdf_is_skipped_not_read(db, store):
    _lender(db, "FAKEBANK")
    url = "https://nsearchives.nseindia.com/corporate/FAKEBANK_1.pdf"
    client = FakeClient([{"symbol": "FAKEBANK", "attchmntFile": url, "an_dt": "31-Oct-2026 16:04:04"}], b"<html>not a pdf</html>")
    run = fetch_new_decks(db, store, client)
    assert (run.skipped, run.read) == (1, 0)
