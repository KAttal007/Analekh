from datetime import date
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from analekh import coverage
from analekh.db.models import Company
from analekh.ingest.http import PoliteClient
from analekh.universe import sectors
from analekh.universe.loader import parse_equity_list, upsert_universe
from analekh.universe.search import search
from analekh.universe.sectors import apply_sectors, parse_constituents, refresh_sectors

# Column layout of NSE's EQUITY_L.csv (design doc 3.1). Companies are SYNTHETIC.
EQUITY_L = (
    b"SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE, MARKET LOT, ISIN NUMBER,"
    b" FACE VALUE\n"
    b"""DEMOFIN,Demo Finance Limited,EQ,05-Jan-2012,10,1,INE000D01011,10
ACMEIND,Acme Industries Limited,EQ,17-Mar-2005,2,1,INE000A01022,2
OLDCO,Old Company Limited,BE,01-Jan-2000,10,1,INE000O01033,10
"""
)
# SME_EQUITY_L.csv as seen 2026-10-13: no MARKET_LOT, trailing comma, two-digit years.
SME_L = (
    b"SYMBOL,NAME_OF_COMPANY,SERIES,DATE_OF_LISTING,PAID_UP_VALUE,ISIN_NUMBER,FACE_VALUE,\n"
    b"""TINYSME,Tiny SME Limited,SM,12-Aug-24,10,INE000T01044,10,
"""
)


def test_parse_equity_list_handles_both_header_styles():
    rows = parse_equity_list(EQUITY_L) + parse_equity_list(SME_L, is_sme=True)
    demo = rows[0]
    assert demo.symbol == "DEMOFIN" and demo.series == "EQ" and demo.isin == "INE000D01011"
    assert demo.listing_date == date(2012, 1, 5) and demo.face_value == Decimal("10")
    sme = rows[-1]
    assert sme.symbol == "TINYSME" and sme.is_sme and sme.listing_date == date(2024, 8, 12)


def test_upsert_by_isin_renames_and_deactivates(db):
    first = upsert_universe(db, parse_equity_list(EQUITY_L))
    assert sorted(first.inserted) == ["ACMEIND", "DEMOFIN", "OLDCO"]

    # Next week: DEMOFIN renamed to DEMOFINANCE (same ISIN), OLDCO delisted.
    week2 = EQUITY_L.replace(b"DEMOFIN,", b"DEMOFINANCE,").replace(
        b"OLDCO,Old Company Limited,BE,01-Jan-2000,10,1,INE000O01033,10\n", b""
    )
    second = upsert_universe(db, parse_equity_list(week2))
    assert second.renamed == [("DEMOFIN", "DEMOFINANCE")]
    assert second.deactivated == ["OLDCO"]
    old = db.scalar(select(Company).where(Company.nse_symbol == "OLDCO"))
    assert old is not None and not old.is_active
    assert (
        db.scalar(select(Company).where(Company.isin == "INE000D01011")).nse_symbol == "DEMOFINANCE"
    )


def test_search_symbol_prefix_and_fuzzy_name(db):
    upsert_universe(db, parse_equity_list(EQUITY_L))
    assert search(db, "demofin")[0].nse_symbol == "DEMOFIN"
    assert search(db, "acme industr")[0].nse_symbol == "ACMEIND"
    assert search(db, "INE000A01022")[0].nse_symbol == "ACMEIND"
    assert search(db, "") == []


def test_search_matches_words_in_any_order(db):
    names = (
        EQUITY_L.split(b"\n", 2)[0]
        + b"""
ZEDMO,Zed Motors Limited,EQ,01-Jan-2020,2,1,INE000Z01011,2
ZEDPV,Zed Motors Passenger Vehicles Limited,EQ,01-Jan-2000,2,1,INE000Z01022,2
QUICKMOT,Quick Motors Ltd,EQ,01-Jan-2010,10,1,INE000Q01033,10
ZEDAMC,Zed Asset Management Company Limited,EQ,01-Jan-2015,5,1,INE000Z01044,5
ZEDSTEEL,Zed Steel Limited,EQ,01-Jan-2005,1,1,INE000Z01055,1
"""
    )
    upsert_universe(db, parse_equity_list(names))

    def symbols(q: str) -> list[str]:
        return [h.nse_symbol for h in search(db, q)]

    assert symbols("zed pass") == ["ZEDPV"]  # skipped word, partial last word
    assert symbols("passenger zed") == ["ZEDPV"]  # any order
    assert symbols("zed motors") == ["ZEDMO", "ZEDPV"]  # not Quick Motors
    assert symbols("zed amc")[0] == "ZEDAMC"  # words joined as a symbol prefix
    assert set(symbols("ZED")) == {"ZEDAMC", "ZEDMO", "ZEDPV", "ZEDSTEEL"}  # not Quick Motors
    assert symbols("zed stel")[0] == "ZEDSTEEL"  # typo falls back to trigram similarity
    assert symbols("  zed   pass ") == ["ZEDPV"]
    assert symbols("zed (pass") == []  # regex characters are escaped, not interpreted
    assert symbols("zed_") == [] and symbols("z%") == []  # LIKE wildcards too


def test_search_narrows_with_each_keystroke(db):
    names = (
        EQUITY_L.split(b"\n", 2)[0]
        + b"""
TCS,Tazza Consultancy Services Limited,EQ,01-Jan-2004,1,1,INE000T01011,1
TCIEXP,TCI Express Limited,EQ,01-Jan-2016,2,1,INE000T01022,2
TIGER,Tiger Foods Limited,EQ,01-Jan-2010,10,1,INE000T01033,10
MATCHBX,Matchbox Industries Limited,EQ,01-Jan-2012,10,1,INE000M01044,10
OTCX,Orion Trading Company Limited,EQ,01-Jan-2018,10,1,INE000O01055,10
ATLAS,Atlas Tyres Limited,EQ,01-Jan-2001,10,1,INE000A01066,10
"""
    )
    upsert_universe(db, parse_equity_list(names))

    def symbols(q: str, **kw: int) -> list[str]:
        return [h.nse_symbol for h in search(db, q, **kw)]

    # One character: ticker or name starts with it (not Atlas Tyres, whose second word does).
    assert symbols("T") == ["TCIEXP", "TCS", "TIGER"]
    # Two or more: anywhere in the ticker or name, closest matches first.
    assert symbols("TC") == ["TCIEXP", "TCS", "MATCHBX", "OTCX"]
    assert symbols("tcs") == ["TCS"]
    # Paging for long lists.
    assert symbols("T", limit=2) + symbols("T", limit=2, offset=2) == ["TCIEXP", "TCS", "TIGER"]
    assert symbols("T", limit=2, offset=3) == []


def test_sector_map_and_taxonomy(db):
    upsert_universe(db, parse_equity_list(EQUITY_L))
    apply_sectors(db, {"DEMOFIN": ("Financial Services", "NBFC")})
    demo = db.scalar(select(Company).where(Company.nse_symbol == "DEMOFIN"))
    assert demo.sector == "Financial Services" and demo.results_taxonomy == "nbfc"


def test_watchlist_controls_coverage_level(db):
    upsert_universe(db, parse_equity_list(EQUITY_L))
    demo = db.scalar(select(Company).where(Company.nse_symbol == "DEMOFIN"))
    assert coverage.level(db, demo) == "universe"
    coverage.add(db, demo, settings={"alerts": True})
    coverage.add(db, demo, settings={"alerts": False})  # idempotent upsert
    assert coverage.level(db, demo) == "deep"
    assert [w.settings for w in coverage.entries(db)] == [{"alerts": False}]
    coverage.remove(db, demo)
    assert not coverage.is_watched(db, demo.id)


# Layout of NSE Indices' constituent lists (verify against a real file). Companies are SYNTHETIC.
NIFTY_HEADER = b"Company Name,Industry,Symbol,Series,ISIN Code\n"


def test_parse_constituents_ignores_header_case_and_bom():
    data = (
        "﻿company name , INDUSTRY,symbol,Series,ISIN Code\nAcme Ltd,Capital Goods,acme,EQ,X\n"
    ).encode()
    assert parse_constituents(data) == {"ACME": ("Capital Goods", None)}


def test_refresh_sectors_from_index_lists(db, monkeypatch: pytest.MonkeyPatch):
    universe = (
        EQUITY_L
        + b"""ZEDBANK,Zed Bank Limited,EQ,01-Jan-2001,10,1,INE000Z01077,10
ZEDLIFE,Zed Life Insurance Limited,EQ,01-Jan-2017,10,1,INE000Z01088,10
"""
    )
    upsert_universe(db, parse_equity_list(universe))
    oldco = db.scalar(select(Company).where(Company.nse_symbol == "OLDCO"))
    oldco.sector = "Set by analyst"
    monkeypatch.setattr(sectors, "load_sector_map", lambda: {})

    lists = {
        "ind_nifty500list.csv": NIFTY_HEADER
        + b"""Demo Finance Limited,Financial Services,DEMOFIN,EQ,INE000D01011
Acme Industries Limited,Capital Goods,ACMEIND,EQ,INE000A01022
Old Company Limited,Capital Goods,OLDCO,EQ,INE000O01033
Zed Bank Limited,Financial Services,ZEDBANK,EQ,INE000Z01077
Zed Life Insurance Limited,Financial Services,ZEDLIFE,EQ,INE000Z01088
""",
        "ind_niftybanklist.csv": NIFTY_HEADER
        + b"Zed Bank Limited,Financial Services,ZEDBANK,EQ,INE000Z01077\n",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        name = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, content=lists[name]) if name in lists else httpx.Response(404)

    client = PoliteClient(transport=httpx.MockTransport(handler), backoff_base=0)
    result = refresh_sectors(db, client)

    assert result["lists_fetched"] == 2 and result["lists_total"] == 5  # missing lists skipped
    assert result["companies_listed"] == 5 and result["banks"] == 1
    by_symbol = {c.nse_symbol: c for c in db.scalars(select(Company))}
    assert by_symbol["ACMEIND"].sector == "Capital Goods"
    assert by_symbol["OLDCO"].sector == "Set by analyst"  # never overwritten
    assert by_symbol["ZEDBANK"].results_taxonomy == "banking"  # bank index membership
    # No strong signal: left for the first filing's schema reference to decide.
    assert by_symbol["ACMEIND"].results_taxonomy is None
    assert by_symbol["ZEDLIFE"].results_taxonomy is None


def test_stocks_workbook_import_and_source_precedence(db, tmp_path):
    from openpyxl import Workbook

    upsert_universe(db, parse_equity_list(EQUITY_L))
    by_symbol = {c.nse_symbol: c for c in db.scalars(select(Company))}
    by_symbol["OLDCO"].sector, by_symbol["OLDCO"].sector_source = "Analyst's call", "user"

    wb = Workbook()
    ws = wb.active
    ws.append(["Sector", "BSE Stock ID", "Security Code", "ISIN No"])
    ws.append(["Banking Services", "#VALUE!", "500001", "INE000D01011"])  # DEMOFIN
    ws.append(["Machinery, Equipment & Components", "#VALUE!", "500002", "INE000A01022"])  # ACME
    ws.append(["Chemicals", "#VALUE!", "500003", "INE000O01033"])  # OLDCO: user value wins
    ws.append(["#FIELD!", "#VALUE!", "500004", "INE999X01099"])  # error: skipped
    ws.append(["Food & Tobacco", "#VALUE!", "500005", "INE999Y01099"])  # not in the universe
    path = tmp_path / "stocks.xlsx"
    wb.save(path)

    result = sectors.import_stocks_workbook(db, path)
    assert result == {"rows": 5, "with_sector": 4, "matched": 3, "updated": 2}
    assert (by_symbol["DEMOFIN"].sector, by_symbol["DEMOFIN"].sector_source) == (
        "Banking Services",
        "excel_stocks",
    )
    assert by_symbol["DEMOFIN"].results_taxonomy is None  # LSEG "Banking Services" includes NBFCs
    assert by_symbol["OLDCO"].sector == "Analyst's call"

    # A lower source (NSE lists) never replaces Excel Stocks; the same source refreshes itself.
    assert apply_sectors(db, {"ACMEIND": ("Capital Goods", None)}, source="nse_indices") == 0
    assert by_symbol["ACMEIND"].sector == "Machinery, Equipment & Components"
    assert (
        apply_sectors(db, {"ACMEIND": ("Industrial Machinery", None)}, source="excel_stocks") == 1
    )
    assert by_symbol["ACMEIND"].sector == "Industrial Machinery"


def test_stocks_workbook_needs_sector_and_isin(db, tmp_path):
    from openpyxl import Workbook

    wb = Workbook()
    wb.active.append(["Name", "Ticker"])
    wb.save(tmp_path / "bad.xlsx")
    with pytest.raises(ValueError, match="needs Sector and ISIN No"):
        sectors.import_stocks_workbook(db, tmp_path / "bad.xlsx")
