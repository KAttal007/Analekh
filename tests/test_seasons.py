"""Results seasons and the watcher's schedule (analekh.seasons; design doc 9.6)."""

from datetime import date, datetime

import pytest

from analekh import seasons
from analekh.ingest.feeds import IST
from analekh.seasons import next_season, season_for, watch_due


@pytest.mark.parametrize(
    ("day", "quarter_end"),
    [
        (date(2026, 7, 4), None),
        (date(2026, 7, 5), date(2026, 6, 30)),  # Q1 opens on day 5
        (date(2026, 8, 16), date(2026, 6, 30)),  # deadline 14 Aug, plus two days
        (date(2026, 8, 17), None),
        (date(2026, 10, 18), date(2026, 9, 30)),
        (date(2026, 11, 16), date(2026, 9, 30)),
        (date(2027, 1, 5), date(2026, 12, 31)),  # Q3 belongs to the previous calendar year
        (date(2027, 2, 16), date(2026, 12, 31)),
        (date(2027, 2, 17), None),
        (date(2027, 4, 5), date(2027, 3, 31)),
        (date(2027, 6, 1), date(2027, 3, 31)),  # year end: 60 days, to 30 May, plus two
        (date(2027, 6, 2), None),
    ],
)
def test_seasons_follow_sebis_deadlines(day, quarter_end):
    season = season_for(day)
    assert (season.quarter_end if season else None) == quarter_end


def test_next_season_after_a_quiet_spell():
    assert next_season(date(2026, 8, 20)).opens == date(2026, 10, 5)
    assert next_season(date(2026, 12, 1)).opens == date(2027, 1, 5)


def ist(y, m, d, h):
    return datetime(y, m, d, h, tzinfo=IST)


def test_in_season_runs_every_slot_from_nine_to_eleven():
    assert watch_due(ist(2026, 10, 20, 9))[0]
    assert watch_due(ist(2026, 10, 20, 23))[0]
    due, why = watch_due(ist(2026, 10, 20, 3))
    assert not due and "09:00" in why


def test_off_season_runs_once_a_day_at_nine_in_the_evening():
    assert watch_due(ist(2026, 9, 10, 21))[0]
    due, why = watch_due(ist(2026, 9, 10, 19))
    assert not due and "2026-10-05" in why  # says when the next season opens


def test_watcher_skips_without_touching_nse_or_the_database(monkeypatch):
    from analekh.jobs import status
    from analekh.jobs.tasks import watch_results

    recorded = []
    monkeypatch.setattr(seasons, "watch_due", lambda now=None: (False, "off season: test"))
    monkeypatch.setattr(status, "record", lambda *args: recorded.append(args))
    assert watch_results() == {"skipped": "off season: test"}
    # The skipped run is noted for the Settings screen (and here, kept out of the database).
    assert recorded == [("results_watch", "skipped", {"skipped": "off season: test"})]


def test_next_ask_and_previous_start():
    from analekh.seasons import next_ask, previous_start

    # In season at 10:30: next ask 11:00, last start 10:00 (hourly).
    assert next_ask(ist(2026, 10, 20, 10).replace(minute=30)) == ist(2026, 10, 20, 11)
    assert previous_start(ist(2026, 10, 20, 10).replace(minute=30)) == ist(2026, 10, 20, 10)
    # Off season after 21:00: tomorrow at 21:00; at 02:00 the last start was 23:00 yesterday.
    assert next_ask(ist(2026, 9, 10, 22)) == ist(2026, 9, 11, 21)
    assert previous_start(ist(2026, 9, 10, 2)) == ist(2026, 9, 9, 23)
    # The day before a season opens: the next ask is that evening's 21:00 run.
    assert next_ask(ist(2026, 10, 4, 12)) == ist(2026, 10, 4, 21)
