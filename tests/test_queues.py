"""Queues and watchers must keep moving: one bad item, file or document never blocks the rest
(issues 1-4), and a listed file whose listing changed is fetched again (issue 7)."""

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select

from analekh.db.models import Company, FeedItem, Filing
from analekh.ingest.http import PoliteClient
from tests.xbrl_factory import q1_instance, q2_instance

ARCHIVE = "https://nsearchives.nseindia.com/corporate/xbrl/"
LOOKUP = "/api/integrated-filing-results"


def bad_date_instance() -> bytes:
    """Well-formed XML that the parser can't read: a context ends on a day that doesn't exist."""
    return q2_instance().replace(b"2026-09-30</xbrli:endDate>", b"2026-09-31</xbrli:endDate>")


def client_for(routes: dict[str, httpx.Response], lookup_rows: list[dict] | None = None):
    """Mock NSE: the integrated-filing list answers ``lookup_rows``; files answer by URL."""
    asked: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == LOOKUP:
            rows = lookup_rows or []
            return httpx.Response(200, json={"data": rows, "totalCount": len(rows)})
        asked.append(str(request.url))
        return routes[str(request.url)]

    client = PoliteClient(transport=httpx.MockTransport(handler), backoff_base=0, max_attempts=2)
    return client, asked


@pytest.fixture
def company(db):
    c = Company(nse_symbol="DEMOFIN", name="Demo Finance Limited")
    db.add(c)
    db.flush()
    return c


def feed_item(db, company, link: str | None, minute: int) -> FeedItem:
    item = FeedItem(
        feed="financial_results",
        item_key=f"{link}-{minute}",
        title=company.name,
        link=link,
        pub_date=datetime(2026, 10, 20, 10, minute, tzinfo=UTC),
        company_id=company.id,
    )
    db.add(item)
    db.flush()
    return item


def test_one_bad_feed_item_does_not_block_the_queue(db, store, company):
    from analekh.ingest.pipeline import MAX_ATTEMPTS, process_feed_items

    gone, broken, unreadable, good = (ARCHIVE + n for n in ("GONE", "BROKEN", "BADDATE", "GOOD"))
    client, _ = client_for(
        {
            gone: httpx.Response(404),
            broken: httpx.Response(200, content=q2_instance()[:900]),  # cut off partway
            unreadable: httpx.Response(200, content=bad_date_instance()),
            good: httpx.Response(200, content=q2_instance()),
        }
    )
    items = [feed_item(db, company, url, i) for i, url in enumerate([gone, broken, unreadable])]
    items.append(feed_item(db, company, good, 9))
    no_link = feed_item(db, company, None, 10)

    run = process_feed_items(db, store, client, [*items, no_link])
    assert run.done == 2 and run.failed == 3 and run.stopped is None  # good + no_link done
    stored = db.scalars(select(Filing).where(Filing.company_id == company.id)).all()
    assert [f.source_url for f in stored] == [good]

    by_url = {i.link: i for i in items}
    assert by_url[gone].processed_at is not None and "404" in (by_url[gone].error or "")
    assert by_url[broken].processed_at is None and by_url[broken].attempts == 1
    assert by_url[good].processed_at is not None and by_url[good].error is None
    assert no_link.processed_at is not None  # nothing to fetch: never waits in the queue

    for _ in range(MAX_ATTEMPTS - 1):
        process_feed_items(db, store, client, [by_url[broken], by_url[unreadable]])
    for url in (broken, unreadable):
        assert by_url[url].processed_at is not None and by_url[url].attempts == MAX_ATTEMPTS
        assert by_url[url].error  # kept for review


def test_feed_queue_stops_when_nse_refuses_and_keeps_what_it_did(db, store, company):
    from analekh.ingest.pipeline import process_feed_items

    good, blocked, later = (ARCHIVE + n for n in ("GOOD", "BLOCKED", "LATER"))
    client, asked = client_for(
        {
            good: httpx.Response(200, content=q2_instance()),
            blocked: httpx.Response(403),
            later: httpx.Response(200, content=q1_instance()),
        }
    )
    items = [feed_item(db, company, url, i) for i, url in enumerate([good, blocked, later])]
    run = process_feed_items(db, store, client, items)

    assert run.done == 1 and run.stopped and "403" in run.stopped
    assert later not in asked  # no more knocking once NSE refuses
    assert items[1].processed_at is None and not items[1].attempts  # a refusal isn't its fault
    assert items[0].processed_at is not None


def test_a_failed_item_retries_after_fresh_ones(db, store, company):
    """Items that failed before go after ones never tried, so retries can't crowd a batch."""
    from analekh.ingest.pipeline import pending_feed_items

    retried = feed_item(db, company, ARCHIVE + "OLD", 0)
    retried.attempts = 1
    fresh = feed_item(db, company, ARCHIVE + "NEW", 5)
    assert pending_feed_items(db, limit=10) == [fresh, retried]


def stored_doc(db, store, company, data: bytes, name: str) -> Filing:
    from analekh.ingest.pipeline import store_document

    return store_document(db, store, company, data, kind="presentation", source_url=name)


def test_one_bad_document_does_not_block_the_document_queue(db, store, company):
    from analekh.docs.pipeline import process_documents
    from tests.test_docs import make_pdf

    bad = stored_doc(db, store, company, make_pdf(["Cut off"])[:20], "bad")  # cut-off download
    good = stored_doc(db, store, company, make_pdf(["Gold loan AUM 82,000 crore"]), "good")

    run = process_documents(db, store, [bad, good], claude=None, embedder=None)
    assert run.done == 1 and run.failed == 1 and run.stopped is None
    assert good.status == "parsed"
    assert bad.status == "failed" and bad.meta.get("error")


def test_document_queue_stops_on_a_passing_outage_and_leaves_the_rest_waiting(db, store, company, monkeypatch):
    import anthropic

    from analekh.docs import pipeline
    from tests.test_docs import make_pdf

    first = stored_doc(db, store, company, make_pdf(["Page one of the deck"]), "first")
    second = stored_doc(db, store, company, make_pdf(["Page two of the deck"]), "second")

    def overloaded(*_args, **_kwargs):
        raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api"))

    monkeypatch.setattr(pipeline, "process_document", overloaded)
    run = pipeline.process_documents(db, store, [first, second], claude=None, embedder=None)
    assert run.done == 0 and run.stopped and run.failed == 0
    assert first.status == "fetched" and second.status == "fetched"  # tried again next run


def row(company, url: str, qe: str = "30-SEP-2026", **extra) -> dict:
    return {"symbol": company.nse_symbol, "qe_Date": qe, "xbrl": url, **extra}


def test_results_watcher_skips_unreadable_and_failing_files_and_keeps_the_rest(db, store, company):
    from analekh.ingest.integrated import fetch_latest

    unreadable, erroring, good = (ARCHIVE + n for n in ("BADDATE", "ERROR", "GOOD"))
    client, _ = client_for(
        {
            unreadable: httpx.Response(200, content=bad_date_instance()),
            erroring: httpx.Response(500),
            good: httpx.Response(200, content=q2_instance()),
        },
        [row(company, unreadable, "30-JUN-2026"), row(company, erroring), row(company, good)],
    )
    out = fetch_latest(db, store, client)
    assert out.new == 1 and out.stopped is None and len(out.errors) == 2
    assert any(unreadable in e for e in out.errors) and any(erroring in e for e in out.errors)


def test_results_watcher_stops_on_refusal_but_keeps_filings_already_stored(db, store, company):
    from analekh.ingest.integrated import fetch_latest

    good, blocked, later = (ARCHIVE + n for n in ("GOOD", "BLOCKED", "LATER"))
    client, asked = client_for(
        {
            good: httpx.Response(200, content=q1_instance()),
            blocked: httpx.Response(429),
            later: httpx.Response(200, content=q2_instance()),
        },
        [
            row(company, good, "30-JUN-2026"),
            row(company, blocked, "30-SEP-2026"),
            row(company, later, "31-DEC-2026"),
        ],
    )
    out = fetch_latest(db, store, client)
    assert out.new == 1 and out.stopped and "429" in out.stopped
    assert later not in asked
    assert db.scalar(select(Filing).where(Filing.source_url == good)) is not None


def test_per_company_fetch_skips_an_unreadable_file(db, store, company):
    from analekh.ingest.integrated import fetch_results

    unreadable, good = ARCHIVE + "BADDATE", ARCHIVE + "GOOD"
    client, _ = client_for(
        {
            unreadable: httpx.Response(200, content=bad_date_instance()),
            good: httpx.Response(200, content=q2_instance()),
        },
        [row(company, unreadable, "30-JUN-2026"), row(company, good)],
    )
    outcome = fetch_results(db, store, client, company)
    assert outcome.new == 1 and len(outcome.errors) == 1 and outcome.gap is None


def test_feed_etag_is_kept_only_after_the_items_are_stored(monkeypatch):
    from analekh.ingest import feeds

    sent: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request.headers.get("If-None-Match"))
        return httpx.Response(200, content=b"<rss/>", headers={"ETag": '"v1"'})

    watcher = feeds.FeedWatcher(PoliteClient(transport=httpx.MockTransport(handler)))

    def db_down(*_args, **_kwargs):
        raise RuntimeError("database went away")

    monkeypatch.setattr(feeds, "store_items", db_down)
    with pytest.raises(RuntimeError):
        watcher.poll(None, "financial_results")  # type: ignore[arg-type]
    monkeypatch.setattr(feeds, "store_items", lambda *_a, **_k: 0)
    watcher.poll(None, "financial_results")  # type: ignore[arg-type]
    watcher.poll(None, "financial_results")  # type: ignore[arg-type]
    assert sent == [None, None, '"v1"']


def test_listed_file_is_fetched_again_only_when_its_listing_changes(db, store, company):
    from analekh.ingest.integrated import fetch_results

    url = ARCHIVE + "SAME_URL.xml"
    files = {url: httpx.Response(200, content=q2_instance())}
    listed = [row(company, url, broadcast_Date="20-Oct-2026 18:00:00", type_Sub="Original")]
    client, asked = client_for(files, listed)

    assert fetch_results(db, store, client, company).new == 1
    fetch_results(db, store, client, company)
    assert asked.count(url) == 1  # listing unchanged: not downloaded again

    listed[0].update(broadcast_Date="22-Oct-2026 09:30:00", type_Sub="Revision")
    same_file = fetch_results(db, store, client, company)
    assert asked.count(url) == 2 and same_file.new == 0  # same bytes: nothing new stored
    fetch_results(db, store, client, company)
    assert asked.count(url) == 2  # the new listing is remembered: no loop

    files[url] = httpx.Response(200, content=q2_instance(revenue=1_010_000_000))
    listed[0].update(broadcast_Date="23-Oct-2026 09:30:00")
    replaced = fetch_results(db, store, client, company)
    assert replaced.new == 1
    filings = db.scalars(select(Filing).where(Filing.source_url == url)).all()
    assert len(filings) == 2


def test_listing_without_a_broadcast_time_does_not_cause_refetches(db, store, company):
    from analekh.ingest.integrated import fetch_results

    url = ARCHIVE + "NO_TIME.xml"
    client, asked = client_for({url: httpx.Response(200, content=q2_instance())}, [row(company, url)])
    fetch_results(db, store, client, company)
    fetch_results(db, store, client, company)
    assert asked.count(url) == 1
