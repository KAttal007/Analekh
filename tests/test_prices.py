"""Daily prices from NSE's bhavcopy (ingest/bhavcopy.py). Files are SYNTHETIC, in NSE's layout."""

import io
import zipfile
from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
from sqlalchemy import select

from analekh.db.models import Company, Price
from analekh.ingest.bhavcopy import fetch, load_day, parse
from analekh.ingest.http import PoliteClient
from analekh.ingest.pipeline import ingest_results_xbrl
from analekh.jobs.tasks import last_close_day
from tests.xbrl_factory import build_instance, pnl

HEADER = (
    "TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,XpryDt,"
    "FininstrmActlXpryDt,StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,LwPric,ClsPric,LastPric,"
    "PrvsClsgPric,UndrlygPric,SttlmPric,OpnIntrst,ChngInOpnIntrst,TtlTradgVol,TtlTrfVal,"
    "TtlNbOfTxsExctd,SsnId,NewBrdLotQty,Rmks,Rsvd1,Rsvd2,Rsvd3,Rsvd4\n"
)


def _row(isin: str, symbol: str, series: str, close: str, volume: str = "1000") -> str:
    return (
        f"2020-01-03,2020-01-03,CM,NSE,STK,1,{isin},{symbol},{series},,,,,{symbol} LTD,"
        f"100.00,110.00,95.00,{close},{close},99.00,,{close},,,{volume},100000,10,F1,1,,,,,\n"
    )


def _zip(rows: list[str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("BhavCopy_NSE_CM_0_0_0_20200103_F_0000.csv", HEADER + "".join(rows))
    return buf.getvalue()


FILE = _zip(
    [
        _row("INE000P01011", "PRICEY", "EQ", "2465.00", "12166634"),
        _row("INE000P01011", "PRICEY", "BE", "2400.00"),  # same ISIN, second series: EQ wins
        _row("INE000S01022", "SMECO", "SM", "48.50"),
        _row("IN0020230011", "GS2030", "GS", "101.20"),  # government security: left out
    ]
)


def test_parse_keeps_equity_one_row_per_isin():
    rows = {r.isin: r for r in parse(FILE)}
    assert set(rows) == {"INE000P01011", "INE000S01022"}
    tcs = rows["INE000P01011"]
    assert (tcs.series, tcs.close, tcs.volume) == ("EQ", Decimal("2465.00"), 12166634)
    assert tcs.prev_close == Decimal("99.00")  # the day's change needs no stored history
    assert tcs.trade_date == date(2020, 1, 3)


def test_store_matches_by_isin_and_works_out_market_cap(db, store):
    pricey = Company(nse_symbol="PRICEY", name="Pricey Ltd", isin="INE000P01011")
    db.add(pricey)
    db.flush()
    # Paid-up equity capital Rs 362 crore at face value Rs 1: 3.62 billion shares (as TCS files).
    q = pnl(1_000_000_000, 0, 800_000_000, 50_000_000)
    q |= {"PaidUpValueOfEquityShareCapital": 3_620_000_000, "FaceValueOfEquityShareCapital": 1}
    data = build_instance(
        q_start=date(2026, 7, 1), q_end=date(2026, 9, 30), ytd_start=date(2026, 4, 1), values_q=q
    )
    ingest_results_xbrl(db, store, pricey, data)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("20200103_F_0000.csv.zip"):
            return httpx.Response(200, content=FILE)
        return httpx.Response(404)  # holiday, or not published yet

    client = PoliteClient(transport=httpx.MockTransport(handler), backoff_base=0)
    # A date no real bhavcopy is loaded for (tests share the local database).
    result = load_day(db, client, date(2020, 1, 3))
    assert result["matched"] == 1 and result["with_market_cap"] == 1  # SMECO is not ours
    price = db.scalar(select(Price).where(Price.company_id == pricey.id))
    assert price.close == Decimal("2465.0000") and price.prev_close == Decimal("99.0000")
    assert price.market_cap == Decimal("8923300000000.00")  # 2,465 x 3.62 bn
    # A stored day is never fetched again; a day with no file says so.
    assert load_day(db, client, date(2020, 1, 3))["skipped"] == "already stored"
    assert fetch(client, date(2020, 1, 6)) is None


def test_latest_close_day_waits_for_the_evening_and_skips_weekends():
    ist_7pm_fri = datetime(2026, 10, 16, 13, 30, tzinfo=UTC)  # 19:00 IST
    ist_10am_fri = datetime(2026, 10, 16, 4, 30, tzinfo=UTC)
    ist_sat = datetime(2026, 10, 17, 9, 0, tzinfo=UTC)
    ist_mon_morning = datetime(2026, 10, 19, 3, 0, tzinfo=UTC)
    assert last_close_day(ist_7pm_fri) == date(2026, 10, 16)
    assert last_close_day(ist_10am_fri) == date(2026, 10, 15)
    assert last_close_day(ist_sat) == date(2026, 10, 16)
    assert last_close_day(ist_mon_morning) == date(2026, 10, 16)
