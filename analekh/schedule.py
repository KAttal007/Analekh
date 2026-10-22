"""Results and meeting calendar, read from the Board Meetings feed (design doc 6.9).

NSE's Board_Meetings.xml writes each intimation as a company name for the title and
"<purpose> |Meeting Date: 27-Oct-2026" for the description (seen in real items, 2026-10-21).
Nothing is stored beyond the feed items already kept: the calendar is a read over them.

An event has a ``kind``: ``results`` (purpose names financial results), ``meeting`` (any other
board meeting) or ``concall`` (reserved: an earnings-call source needs the owner's approval under
rule 1, so no code produces it yet; the API and the web app already carry the kind).
"""

import re
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from analekh.db.models import Company, FeedItem, Filing, Watchlist
from analekh.ingest.feeds import IST

MEETING_DATE = re.compile(r"Meeting Date:\s*(\d{1,2}-[A-Za-z]{3}-\d{4})")
LOOKBACK_DAYS = 120  # intimations come at least two working days ahead; older ones are history


@dataclass(frozen=True)
class CalendarEvent:
    date: date
    kind: str  # results | meeting | concall
    symbol: str
    name: str
    sector: str | None
    purpose: str | None
    watched: bool
    source_url: str | None
    status: str = "scheduled"  # scheduled (announced) | filed (the results are in)
    revised: bool = False  # filed as a revision of an earlier quarter's numbers


def parse_description(description: str | None) -> tuple[str | None, date | None]:
    """(purpose, meeting date) from a feed description; (None, None) when it has no date."""
    if not description:
        return None, None
    m = MEETING_DATE.search(description)
    if not m:
        return None, None
    try:
        when = datetime.strptime(m.group(1), "%d-%b-%Y").date()
    except ValueError:
        return None, None
    purpose = description[: m.start()].strip(" |").strip() or None
    return purpose, when


def kind_of(purpose: str | None) -> str:
    return "results" if purpose and "result" in purpose.lower() else "meeting"


def events(
    session: Session,
    start: date,
    end: date,
    *,
    watchlist_user: str | None = None,
    only_watched: bool = False,
    now: datetime | None = None,
) -> list[CalendarEvent]:
    """Calendar events dated start..end, oldest first.

    A company's results date can move: the newest intimation of its results meeting wins, so a
    rescheduled board meeting shows once, on its new date. Other meetings are kept per date."""
    since = (now or datetime.now(UTC)) - timedelta(days=LOOKBACK_DAYS)
    watched: set[int] = set()
    if watchlist_user:
        watched = set(
            session.scalars(select(Watchlist.company_id).where(Watchlist.user_id == watchlist_user))
        )
    rows = session.execute(
        select(FeedItem.description, FeedItem.link, FeedItem.pub_date, Company)
        .join(Company, Company.id == FeedItem.company_id)
        .where(
            FeedItem.feed == "board_meetings",
            FeedItem.pub_date >= since,
            FeedItem.description.ilike("%Meeting Date:%"),
        )
        .order_by(FeedItem.pub_date.asc())  # later intimations overwrite earlier ones below
    ).all()

    latest_results: dict[int, CalendarEvent] = {}
    other: dict[tuple[int, date], CalendarEvent] = {}
    for description, link, _pub, company in rows:
        purpose, when = parse_description(description)
        if when is None:
            continue
        ev = CalendarEvent(
            date=when,
            kind=kind_of(purpose),
            symbol=company.nse_symbol,
            name=company.name,
            sector=company.sector,
            purpose=purpose,
            watched=company.id in watched,
            source_url=link,
        )
        if ev.kind == "results":
            latest_results[company.id] = ev
        else:
            other[(company.id, when)] = ev

    # Past days: who actually filed results then. The feed only holds recent intimations, so
    # without this the days already gone would be empty. A filing replaces that company's
    # announced results on the same day.
    filed = _filed_results(session, start, end, watched, now)
    filed_keys = {(e.symbol, e.date) for e in filed}
    latest_results = {
        cid: e for cid, e in latest_results.items() if (e.symbol, e.date) not in filed_keys
    }

    taken = {(ev.symbol, ev.date) for ev in latest_results.values()} | filed_keys
    out = [
        *filed,
        *latest_results.values(),
        *(e for e in other.values() if (e.symbol, e.date) not in taken),
    ]
    out = [e for e in out if start <= e.date <= end and (e.watched or not only_watched)]
    return sorted(out, key=lambda e: (e.date, not e.watched, e.name))


def _filed_results(
    session: Session, start: date, end: date, watched: set[int], now: datetime | None
) -> list[CalendarEvent]:
    """One event per company and day for results filings made in start..end (IST days)."""
    lo = datetime(start.year, start.month, start.day, tzinfo=IST)
    hi = datetime(end.year, end.month, end.day, tzinfo=IST) + timedelta(days=1)
    rows = session.execute(
        select(Filing.filed_at, Filing.meta, Company)
        .join(Company, Company.id == Filing.company_id)
        .where(
            Filing.kind == "results_xbrl",
            Filing.filed_at >= lo,
            Filing.filed_at < min(hi, (now or datetime.now(UTC)) + timedelta(minutes=1)),
        )
        .order_by(Filing.filed_at.asc())
    ).all()
    seen: dict[tuple[int, date], CalendarEvent] = {}
    for filed_at, meta, company in rows:
        if filed_at is None:
            continue
        day = filed_at.astimezone(IST).date()
        # The readable iXBRL page, never the raw XBRL file (None when NSE listed no iXBRL link).
        url = ((meta or {}).get("links") or {}).get("ixbrl")
        # NSE's "Revision": restated numbers for a quarter already filed. Shown with a badge, and
        # an original filing the same day still wins (it is the news; the revision a follow-up).
        revised = str((meta or {}).get("revision") or "").lower().startswith("revis")
        key = (company.id, day)
        event = CalendarEvent(
            date=day,
            kind="results",
            symbol=company.nse_symbol,
            name=company.name,
            sector=company.sector,
            purpose="Results filed",
            watched=company.id in watched,
            source_url=url,
            status="filed",
            revised=revised,
        )
        current = seen.get(key)
        if current is None:
            seen[key] = event
        elif current.revised and not revised:  # an original arrived: it is the day's filing
            seen[key] = replace(event, source_url=url or current.source_url)
        elif not current.source_url and url:  # a later filing that day has the page
            seen[key] = replace(current, source_url=url)
    return list(seen.values())
