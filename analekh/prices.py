"""Latest closing price and market cap per company, as loaded from NSE's bhavcopy
(ingest/bhavcopy.py). End of day only: one row per company per trading day, no live prices."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from analekh.db.models import Price


@dataclass
class LastClose:
    trade_date: date
    close: Decimal | None
    prev_close: Decimal | None
    change_pct: Decimal | None  # % on the previous close
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    volume: int | None
    market_cap: Decimal | None  # rupees; None when no results filing gives the share count


def _change(close: Decimal | None, prev: Decimal | None) -> Decimal | None:
    if close is None or not prev:
        return None
    return ((close / prev - 1) * 100).quantize(Decimal("0.01"))


def latest_prices(session: Session, company_ids: list[int]) -> dict[int, LastClose]:
    """Each company's most recent stored trading day."""
    if not company_ids:
        return {}
    newest = (
        select(Price.company_id, func.max(Price.trade_date).label("day"))
        .where(Price.company_id.in_(company_ids))
        .group_by(Price.company_id)
        .subquery()
    )
    rows = session.scalars(
        select(Price).join(
            newest,
            (Price.company_id == newest.c.company_id) & (Price.trade_date == newest.c.day),
        )
    )
    return {
        p.company_id: LastClose(
            trade_date=p.trade_date,
            close=p.close,
            prev_close=p.prev_close,
            change_pct=_change(p.close, p.prev_close),
            open=p.open,
            high=p.high,
            low=p.low,
            volume=p.volume,
            market_cap=p.market_cap,
        )
        for p in rows
    }


def latest_price(session: Session, company_id: int) -> LastClose | None:
    return latest_prices(session, [company_id]).get(company_id)
