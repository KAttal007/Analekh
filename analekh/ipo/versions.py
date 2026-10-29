"""Which offer document is current, and what changed between the RHP and the Prospectus.

Versions: RHP figures are version 1; Prospectus figures supersede them for display. Changed
numbers are listed as restatements. Quarterly XBRL after listing supersedes both (V10, not here).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from analekh.db.models import IpoDocument, IpoFinancial


@dataclass
class Restatement:
    basis: str
    period_end: date
    line: str
    old: Decimal
    new: Decimal


def current_document(session: Session, issue_id: int) -> IpoDocument | None:
    """The newest usable Prospectus; else the newest usable RHP. A failed document is skipped so
    it cannot hide a usable one."""
    docs = session.scalars(select(IpoDocument).where(IpoDocument.issue_id == issue_id, IpoDocument.status != "failed").order_by(IpoDocument.id.desc())).all()
    for stage in ("prospectus", "rhp"):
        for doc in docs:
            if doc.stage == stage:
                return doc
    return None


def _figures(session: Session, document_id: int) -> dict[tuple[str, date, str], Decimal]:
    rows = session.scalars(select(IpoFinancial).where(IpoFinancial.document_id == document_id)).all()
    return {(r.basis, r.period_end, r.line): r.amount for r in rows}


def restatements(session: Session, issue_id: int) -> list[Restatement]:
    """Figures in both the RHP and the Prospectus whose amounts differ, in period then line order.
    Empty unless the issue has both stages."""
    docs = session.scalars(select(IpoDocument).where(IpoDocument.issue_id == issue_id)).all()
    rhp = next((d for d in docs if d.stage == "rhp"), None)
    pro = next((d for d in docs if d.stage == "prospectus"), None)
    if rhp is None or pro is None:
        return []
    old, new = _figures(session, rhp.id), _figures(session, pro.id)
    changed = [Restatement(basis=b, period_end=p, line=line, old=old[(b, p, line)], new=amount) for (b, p, line), amount in new.items() if (b, p, line) in old and old[(b, p, line)] != amount]
    return sorted(changed, key=lambda r: (r.period_end, r.line))
