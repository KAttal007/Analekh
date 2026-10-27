"""Results seasons: when results watcher asks NSE for new filings (design doc 9.6).

SEBI: quarterly results within 45 days of quarter end, year's results within 60 days (LODR 33).
Season runs from day 5 after quarter end to two days past deadline (XBRL can follow a last-day
board meeting by up to 24 hours):

    Q1  5 Jul - 16 Aug     Q2  5 Oct - 16 Nov     Q3  5 Jan - 16 Feb     Q4  5 Apr - 1 Jun

In season watcher runs hourly 09:00 to 23:00 IST; outside, once a day at 21:00 for late filers and
revisions. NSE shows a filing ~1 second after filed and under 1% of filings come between midnight
and 09:00 (checked 2026-10-18): misses almost nothing, ~45% fewer requests than hourly all year.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from analekh.ingest.feeds import IST

QUARTER_ENDS = ((3, 31), (6, 30), (9, 30), (12, 31))
OPENS_AFTER_DAYS = 5  # the earliest filers report around day 8
GRACE_DAYS = 2  # past the deadline, for XBRL that follows the board meeting
SEASON_HOURS = range(9, 24)  # 09:00 to 23:00 IST
OFF_SEASON_HOUR = 21


def deadline_days(quarter_end: date) -> int:
    """SEBI's deadline: 60 days when the quarter closes the financial year, else 45."""
    return 60 if quarter_end.month == 3 else 45


@dataclass(frozen=True)
class Season:
    quarter_end: date
    opens: date
    closes: date  # last day of the season, inclusive


def _season(quarter_end: date) -> Season:
    return Season(
        quarter_end=quarter_end,
        opens=quarter_end + timedelta(days=OPENS_AFTER_DAYS),
        closes=quarter_end + timedelta(days=deadline_days(quarter_end) + GRACE_DAYS),
    )


def _seasons_around(day: date) -> list[Season]:
    return [
        _season(date(year, month, last))
        for year in (day.year - 1, day.year, day.year + 1)
        for month, last in QUARTER_ENDS
    ]


def season_for(day: date) -> Season | None:
    """The results season `day` falls in, if any."""
    return next((s for s in _seasons_around(day) if s.opens <= day <= s.closes), None)


def next_season(day: date) -> Season:
    """The first season that opens after `day`."""
    return next(s for s in _seasons_around(day) if s.opens > day)


def watch_due(now: datetime | None = None) -> tuple[bool, str]:
    """Whether the results watcher should ask NSE now, and why (IST)."""
    local = (now or datetime.now(UTC)).astimezone(IST)
    today = local.date()
    season = season_for(today)
    if season is not None:
        if local.hour in SEASON_HOURS:
            return (
                True,
                f"results season for the quarter ended {season.quarter_end} (to {season.closes})",
            )
        return False, "results season, overnight: runs resume at 09:00 IST"
    if local.hour == OFF_SEASON_HOUR:
        return True, "off season: the daily 21:00 run"
    upcoming = next_season(today)
    return False, f"off season: one run a day at 21:00 IST until {upcoming.opens}"


# The hours the watcher is started (results_watch_cron, "0 9-23 * * *", IST); each start either
# asks NSE or records a skip, as watch_due decides.
RUN_HOURS = tuple(range(9, 24))


def _slots(day: date) -> list[datetime]:
    return [datetime(day.year, day.month, day.day, h, tzinfo=IST) for h in RUN_HOURS]


def previous_start(now: datetime | None = None) -> datetime:
    """The latest scheduled start at or before `now` (IST)."""
    local = (now or datetime.now(UTC)).astimezone(IST)
    for day in (local.date(), local.date() - timedelta(days=1)):
        past = [s for s in _slots(day) if s <= local]
        if past:
            return past[-1]
    raise AssertionError("unreachable: yesterday always has a 23:00 start")


def next_ask(now: datetime | None = None) -> datetime:
    """When the watcher will next ask NSE: the next scheduled start that watch_due allows."""
    local = (now or datetime.now(UTC)).astimezone(IST)
    day = local.date()
    for _ in range(3):  # off season runs daily at 21:00, so this always finds one
        for slot in _slots(day):
            if slot > local and watch_due(slot)[0]:
                return slot
        day += timedelta(days=1)
    raise AssertionError("unreachable: every day has a due start")
