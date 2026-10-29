"""NSE symbol for an IPO issue. Two ways, both without guessing:

- The analyst enters it once NSE assigns it (bids open), through the API.
- After listing, `link_listed` matches the issue's name stem against listed companies' names and
  links only when exactly one company matches.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from analekh.db.models import Company, IpoIssue
from analekh.ipo.listing import issue_stem

_SYMBOL = re.compile(r"[A-Z0-9&-]{1,20}")


def valid_symbol(symbol: str | None) -> bool:
    return bool(symbol) and _SYMBOL.fullmatch(symbol or "") is not None


def link_listed(session: Session) -> int:
    """Link every unlinked issue whose name stem matches exactly one listed company. Returns the
    number linked. Called after the daily bhavcopy is loaded."""
    by_stem: dict[str, list[Company]] = {}
    for company in session.scalars(select(Company)).all():
        by_stem.setdefault(issue_stem(company.name or ""), []).append(company)
    linked = 0
    for issue in session.scalars(select(IpoIssue).where(IpoIssue.symbol.is_(None))).all():
        candidates = by_stem.get(issue.stem, [])
        if len(candidates) == 1:
            issue.symbol = candidates[0].nse_symbol
            issue.company_id = candidates[0].id
            linked += 1
    session.flush()
    return linked
