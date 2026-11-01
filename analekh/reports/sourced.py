"""Which numbers in a draft are sourced?

A number is sourced if it matches a tool result fetched during the thread, or a latest filed fact or
KPI of the company for the report's periods (a database read, no model call). So a correct filing
figure the AI never fetched is not flagged when the analyst types it. Numbers that match nothing are
flagged "not sourced", never blocked: the analyst is the author (design: the draft).
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from analekh.config import get_settings
from analekh.db.models import Fact, Kpi, ReportThread
from analekh.genai.grounding import check


def _window(thread: ReportThread) -> tuple[date | None, date | None]:
    """Report quarter back `sourced_lookback_days`; no quarter set means no limit on either side."""
    if thread.quarter_end is None:
        return None, None
    return thread.quarter_end - timedelta(days=get_settings().sourced_lookback_days), thread.quarter_end


def company_values(db: Session, thread: ReportThread) -> list[Decimal]:
    lo, hi = _window(thread)
    facts = select(Fact.value).where(Fact.company_id == thread.company_id, Fact.is_latest.is_(True), Fact.value.is_not(None))
    kpis = select(Kpi.value).where(Kpi.company_id == thread.company_id, Kpi.value.is_not(None))
    if lo and hi:
        facts = facts.where(Fact.period_end.between(lo, hi))
        kpis = kpis.where(or_(Kpi.period_end.is_(None), Kpi.period_end.between(lo, hi)))
    return [v for v in [*db.scalars(facts), *db.scalars(kpis)] if v is not None]


def unsourced_numbers(db: Session, thread: ReportThread, text: str, results: list[Any]) -> list[str]:
    """Numbers in `text` that match no thread tool result and no company data for the report's periods."""
    pool: list[Any] = [*results, company_values(db, thread)]
    return check(text, pool).unmatched
