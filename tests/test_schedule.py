"""Results calendar read from the Board Meetings feed. Data is SYNTHETIC but the description
format is the one NSE publishes ("<purpose> |Meeting Date: 27-Oct-2026")."""

from datetime import UTC, date, datetime

from analekh.db.models import Company, FeedItem, Watchlist
from analekh.schedule import events, kind_of, parse_description

NOW = datetime(2026, 10, 21, 12, tzinfo=UTC)


def test_parse_description():
    assert parse_description("Financial Results |Meeting Date: 27-Oct-2026") == (
        "Financial Results",
        date(2026, 10, 27),
    )
    assert parse_description("no date here") == (None, None)
    assert parse_description(None) == (None, None)
    assert kind_of("Financial Results") == "results"
    assert kind_of("Board Meeting Intimation") == "meeting"


def _item(db, company, description, minute, key):
    db.add(
        FeedItem(
            feed="board_meetings",
            item_key=key,
            title=company.name,
            description=description,
            pub_date=datetime(2026, 10, 20, 9, minute, tzinfo=UTC),
            company_id=company.id,
        )
    )


def test_calendar_reschedule_watchlist_and_window(db):
    a = Company(nse_symbol="CALAAA", name="Cal A Ltd", isin="INE000Z01011", sector="S")
    b = Company(nse_symbol="CALBBB", name="Cal B Ltd", isin="INE000Z01029", sector="S")
    db.add_all([a, b])
    db.flush()
    db.add(Watchlist(user_id="cal-test", company_id=b.id))
    _item(db, a, "Financial Results |Meeting Date: 27-Oct-2026", 1, "k1")
    _item(db, a, "Financial Results |Meeting Date: 29-Oct-2026", 5, "k2")  # moved: shown once
    _item(db, b, "Board Meeting Intimation |Meeting Date: 28-Oct-2026", 2, "k3")
    _item(db, b, "Financial Results |Meeting Date: 28-Oct-2026", 3, "k4")  # same day: results wins
    db.flush()

    found = events(db, date(2026, 10, 21), date(2026, 11, 5), watchlist_user="cal-test", now=NOW)
    mine = [(e.symbol, e.date, e.kind, e.watched) for e in found if e.symbol.startswith("CAL")]
    assert mine == [
        ("CALBBB", date(2026, 10, 28), "results", True),
        ("CALAAA", date(2026, 10, 29), "results", False),
    ]

    only = events(
        db,
        date(2026, 10, 21),
        date(2026, 11, 5),
        watchlist_user="cal-test",
        only_watched=True,
        now=NOW,
    )
    assert {e.symbol for e in only if e.symbol.startswith("CAL")} == {"CALBBB"}
    assert not events(db, date(2026, 11, 6), date(2026, 12, 1), now=NOW)  # nothing past the end


def test_past_days_show_results_filed_and_replace_the_announcement(db, store):
    from analekh.db.models import Filing  # noqa: F401
    from analekh.ingest.pipeline import ingest_results_xbrl
    from tests.xbrl_factory import build_instance, pnl

    c = Company(nse_symbol="CALFIL", name="Cal Filed Ltd", isin="INE000X01011", sector="S")
    db.add(c)
    db.flush()
    data = build_instance(
        q_start=date(2026, 7, 1),
        q_end=date(2026, 9, 30),
        ytd_start=date(2026, 4, 1),
        values_q=pnl(900 * 10_000_000, 0, 60 * 10_000_000, 15 * 10_000_000),
    )
    filed_at = datetime(2026, 10, 19, 17, 30, tzinfo=UTC)  # 23:00 IST, still the 19th
    ingest_results_xbrl(db, store, c, data, filed_at=filed_at)
    _item(db, c, "Financial Results |Meeting Date: 19-Oct-2026", 1, "kf1")
    db.flush()

    found = [
        e
        for e in events(db, date(2026, 10, 15), date(2026, 10, 25), now=NOW)
        if e.symbol == "CALFIL"
    ]
    assert [(e.date, e.status) for e in found] == [(date(2026, 10, 19), "filed")]
