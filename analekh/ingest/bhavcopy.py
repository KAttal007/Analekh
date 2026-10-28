"""Daily closing prices from NSE's bhavcopy (design doc 3.3: one static reference price at a time).

NSE publishes one file per trading day after close, on nsearchives (rule 1, owner-approved
2026-10-17): zip of one CSV, every traded security with ISIN, open, high, low, close, previous
close, volume. One request a day. Only latest day kept: each file replaces previous day's prices
(owner's rule, 2026-10-18); day's change from the file's previous close. Rows matched to companies
by ISIN; market cap = close x shares outstanding: paid-up equity capital from latest results
filing / face value in NSE's equity list. Results watcher recomputes when new filings arrive.
"""

import csv
import io
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, cast

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from analekh.db.models import Company, Fact, Price
from analekh.ingest.http import PoliteClient

BHAVCOPY_URL = "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{day:%Y%m%d}_F_0000.csv.zip"
EQUITY_SERIES = frozenset({"EQ", "BE", "BZ", "SM", "ST", "SZ"})
SERIES_RANK = {"EQ": 0, "SM": 1, "BE": 2, "ST": 3, "BZ": 4, "SZ": 5}  # one row per ISIN


@dataclass(frozen=True)
class BhavRow:
    isin: str
    symbol: str
    series: str
    trade_date: date
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    prev_close: Decimal | None
    volume: int | None


def _dec(raw: str | None) -> Decimal | None:
    try:
        return Decimal((raw or "").strip()) if (raw or "").strip() else None
    except InvalidOperation:
        return None


def parse(data: bytes) -> list[BhavRow]:
    """Equity rows of one bhavcopy zip, one per ISIN (the main series when a stock has two)."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        text = z.read(z.namelist()[0]).decode("utf-8-sig", errors="replace")
    best: dict[str, BhavRow] = {}
    for r in csv.DictReader(io.StringIO(text)):
        series = (r.get("SctySrs") or "").strip()
        isin = (r.get("ISIN") or "").strip()
        if series not in EQUITY_SERIES or not isin.startswith("IN"):
            continue
        volume = (r.get("TtlTradgVol") or "").strip()
        row = BhavRow(
            isin=isin,
            symbol=(r.get("TckrSymb") or "").strip(),
            series=series,
            trade_date=date.fromisoformat((r.get("TradDt") or "").strip()),
            open=_dec(r.get("OpnPric")),
            high=_dec(r.get("HghPric")),
            low=_dec(r.get("LwPric")),
            close=_dec(r.get("ClsPric")),
            prev_close=_dec(r.get("PrvsClsgPric")),
            volume=int(Decimal(volume)) if volume else None,
        )
        have = best.get(isin)
        if have is None or SERIES_RANK[series] < SERIES_RANK[have.series]:
            best[isin] = row
    return list(best.values())


def fetch(client: PoliteClient, day: date) -> list[BhavRow] | None:
    """The day's equity rows, or None when NSE has no file for it (a holiday, or not published
    yet: it answers 404)."""
    try:
        data = client.get(BHAVCOPY_URL.format(day=day)).content
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (404, 410):
            return None
        raise
    return parse(data)


PAID_UP = ("PaidUpValueOfEquityShareCapital", "PaidUpEquityCapital", "PaidUpEquityShareCapital")
FACE_VALUE = "FaceValueOfEquityShareCapital"
ASSETS = "Assets"  # total assets for Ind-AS filers and banks; not in the insurers' formats
INSURERS = ("insurance", "life_insurance")
MAX_MARKET_CAP = Decimal("30e12")  # ₹30 lakh crore
ASSETS_MULTIPLE = 100  # paid-up capital above this many times total assets is a tagging error
JUMP = 50  # bonus and rights issues never move paid-up capital this far in a quarter


def paid_up_capital(history: list[tuple[date, Decimal]], assets: Decimal | None) -> Decimal | None:
    """Paid-up capital to use from a company's filed values (period end, value).

    Filers sometimes tag it 1,000 to 1,00,000 times too large: in latest quarter (Steelcast, CMR
    Green, Orient Bell, June 2026) or earlier ones (Taurian, Lloyds). Errors only go up, so when
    latest quarter and the one before differ by more than JUMP times, use the smaller. Company with
    every value wrong (Vishwas: Rs 10 lakh crore) caught by total assets: heavy loss-makers carry
    capital above assets, but not ASSETS_MULTIPLE times (GTL Infra, TTML: 20x at most). Quarter
    filed twice (standalone, consolidated) with different values: use larger.
    """
    by_period: dict[date, Decimal] = {}
    for end, value in history:
        if assets is not None and value > assets * ASSETS_MULTIPLE:
            continue
        by_period[end] = max(value, by_period.get(end, value))
    ordered = [by_period[end] for end in sorted(by_period, reverse=True)]
    if not ordered:
        return None
    latest = ordered[0]
    if len(ordered) > 1 and not ordered[1] / JUMP <= latest <= ordered[1] * JUMP:
        return min(latest, ordered[1])
    return latest


def shares_outstanding(session: Session, company_ids: list[int]) -> dict[int, Decimal]:
    """Shares in issue: paid-up equity capital from results filings / face value in NSE's equity
    list. Filed face value is fallback only: filers tag 0 (Honasa), their capital (Bharti Airtel:
    19,13,672) or pre-split value, while the list is current, as price is. (Insurers' NumberOfShares
    no better: New India, 2,400.)
    """
    face: dict[int, Decimal] = {}
    insurers: set[int] = set()
    for cid, value, taxonomy in session.execute(select(Company.id, Company.face_value, Company.results_taxonomy).where(Company.id.in_(company_ids))):
        if value:
            face[cid] = value
        if taxonomy in INSURERS:
            insurers.add(cid)
    paid_up: dict[int, list[tuple[date, Decimal]]] = defaultdict(list)
    filed_face: dict[int, tuple[date, Decimal]] = {}
    rows = session.execute(
        select(Fact.company_id, Fact.element, Fact.period_end, Fact.value).where(
            Fact.company_id.in_(company_ids),
            Fact.is_latest,
            Fact.dimensions == {},
            Fact.element.in_((*PAID_UP, FACE_VALUE, ASSETS)),
        )
    )
    assets: dict[int, tuple[date, Decimal]] = {}
    for cid, element, end, value in rows:
        if not value or value < 0:
            continue
        if element == ASSETS:
            if cid not in insurers and (cid not in assets or end > assets[cid][0]):
                assets[cid] = (end, value)
        elif element != FACE_VALUE:
            paid_up[cid].append((end, value))
        elif cid not in filed_face or end > filed_face[cid][0]:
            filed_face[cid] = (end, value)
    out: dict[int, Decimal] = {}
    for cid, history in paid_up.items():
        capital = paid_up_capital(history, assets.get(cid, (None, None))[1])
        per_share = face.get(cid) or filed_face.get(cid, (None, None))[1]
        if capital and per_share:
            out[cid] = capital / per_share
    return out


def market_cap(close: Decimal | None, shares: Decimal | None) -> Decimal | None:
    if close is None or shares is None:
        return None
    cap = (close * shares).quantize(Decimal("0.01"))
    return cap if cap <= MAX_MARKET_CAP else None


def recompute_market_caps(session: Session) -> dict[str, int]:
    """Market caps of the stored prices from the current share counts, without downloading: after
    new results filings, or a change to how shares are counted."""
    prices = session.scalars(select(Price)).all()
    shares = shares_outstanding(session, [p.company_id for p in prices])
    changed = 0
    for p in prices:
        cap = market_cap(p.close, shares.get(p.company_id))
        if cap != p.market_cap:
            p.market_cap = cap
            changed += 1
    return {
        "prices": len(prices),
        "with_market_cap": sum(p.market_cap is not None for p in prices),
        "changed": changed,
    }


def store(session: Session, rows: list[BhavRow]) -> dict[str, int]:
    """Upsert the day's prices for the companies we know, matched by ISIN."""
    if not rows:
        return {"rows": 0, "matched": 0, "with_market_cap": 0}
    by_isin = {r.isin: r for r in rows}
    companies = session.execute(select(Company.id, Company.isin).where(Company.isin.in_(by_isin))).all()
    shares = shares_outstanding(session, [cid for cid, _ in companies])
    values = []
    for cid, isin in companies:
        if isin is None:
            continue
        r = by_isin[isin]
        values.append(
            {
                "company_id": cid,
                "trade_date": r.trade_date,
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "prev_close": r.prev_close,
                "volume": r.volume,
                "market_cap": market_cap(r.close, shares.get(cid)),
            }
        )
    if values:
        stmt = insert(Price).values(values)
        session.execute(
            stmt.on_conflict_do_update(
                index_elements=[Price.company_id, Price.trade_date],
                set_={c: stmt.excluded[c] for c in ("open", "high", "low", "close", "prev_close", "volume", "market_cap")},
            )
        )
    return {
        "rows": len(rows),
        "matched": len(values),
        "with_market_cap": sum(1 for v in values if v["market_cap"] is not None),
    }


def stored_for(session: Session, day: date) -> int:
    return int(session.scalar(select(func.count()).select_from(Price).where(Price.trade_date == day)) or 0)


def latest_stored(session: Session) -> date | None:
    return session.scalar(select(func.max(Price.trade_date)))


def load_day(session: Session, client: PoliteClient, day: date) -> dict[str, object]:
    """Fetch one trading day's prices and make them the only ones stored: the previous day's
    are replaced. Skipped when that day, or a later one, is already stored."""
    if stored_for(session, day):
        return {"day": day.isoformat(), "skipped": "already stored"}
    newest = latest_stored(session)
    if newest and newest > day:
        return {"day": day.isoformat(), "skipped": f"a later close ({newest}) is stored"}
    rows = fetch(client, day)
    if rows is None:
        return {"day": day.isoformat(), "skipped": "no file (holiday, or not published yet)"}
    counts = store(session, rows)
    gone = cast("CursorResult[Any]", session.execute(delete(Price).where(Price.trade_date < day)))
    replaced = gone.rowcount
    return {"day": day.isoformat(), **counts, "replaced": replaced}
