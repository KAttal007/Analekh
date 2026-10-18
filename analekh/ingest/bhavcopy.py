"""Daily closing prices from NSE's bhavcopy (design doc 3.3: one static reference price at a time).

NSE publishes one file per trading day after the close, on nsearchives (rule 1, owner-approved
2026-10-17): a zip of one CSV with every traded security, its ISIN, open, high, low, close,
previous close and volume. One request a day. Only the latest day is kept: each new file
replaces the previous day's prices (owner's rule, 2026-10-18), and the day's change comes from the
previous close the file carries. Rows are matched to companies by ISIN; market cap is the close
times the shares outstanding from the latest results filing (paid-up equity capital / face value).
"""

import csv
import io
import zipfile
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

BHAVCOPY_URL = (
    "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{day:%Y%m%d}_F_0000.csv.zip"
)
# Equity series: main board (EQ, BE trade-for-trade, BZ non-compliant) and SME (SM, ST, SZ).
# Bonds, government securities and the rest of the file are left out.
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


def shares_outstanding(session: Session, company_ids: list[int]) -> dict[int, Decimal]:
    """Shares in issue from each company's latest results filing: paid-up equity capital divided
    by face value (both filed in rupees)."""
    out: dict[int, Decimal] = {}
    latest: dict[tuple[int, str], tuple[date, Decimal]] = {}
    rows = session.execute(
        select(Fact.company_id, Fact.element, Fact.period_end, Fact.value).where(
            Fact.company_id.in_(company_ids),
            Fact.is_latest,
            Fact.dimensions == {},
            Fact.element.in_(("PaidUpValueOfEquityShareCapital", "FaceValueOfEquityShareCapital")),
        )
    )
    for cid, element, end, value in rows:
        if value is None:
            continue
        have = latest.get((cid, element))
        if have is None or end > have[0]:
            latest[(cid, element)] = (end, value)
    for (cid, element), (_, paid_up) in latest.items():
        if element != "PaidUpValueOfEquityShareCapital":
            continue
        face = latest.get((cid, "FaceValueOfEquityShareCapital"))
        if face and face[1] > 0:
            out[cid] = paid_up / face[1]
    return out


def store(session: Session, rows: list[BhavRow]) -> dict[str, int]:
    """Upsert the day's prices for the companies we know, matched by ISIN."""
    if not rows:
        return {"rows": 0, "matched": 0, "with_market_cap": 0}
    by_isin = {r.isin: r for r in rows}
    companies = session.execute(
        select(Company.id, Company.isin).where(Company.isin.in_(by_isin))
    ).all()
    shares = shares_outstanding(session, [cid for cid, _ in companies])
    values = []
    for cid, isin in companies:
        if isin is None:
            continue
        r = by_isin[isin]
        cap = r.close * shares[cid] if r.close is not None and cid in shares else None
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
                "market_cap": cap.quantize(Decimal("0.01")) if cap is not None else None,
            }
        )
    if values:
        stmt = insert(Price).values(values)
        session.execute(
            stmt.on_conflict_do_update(
                index_elements=[Price.company_id, Price.trade_date],
                set_={
                    c: stmt.excluded[c]
                    for c in ("open", "high", "low", "close", "prev_close", "volume", "market_cap")
                },
            )
        )
    return {
        "rows": len(rows),
        "matched": len(values),
        "with_market_cap": sum(1 for v in values if v["market_cap"] is not None),
    }


def stored_for(session: Session, day: date) -> int:
    return int(
        session.scalar(select(func.count()).select_from(Price).where(Price.trade_date == day)) or 0
    )


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
    # Only the latest close is kept, so a company missing from today's file (suspended, not
    # traded) has no price rather than a stale one.
    gone = cast("CursorResult[Any]", session.execute(delete(Price).where(Price.trade_date < day)))
    replaced = gone.rowcount
    return {"day": day.isoformat(), **counts, "replaced": replaced}
