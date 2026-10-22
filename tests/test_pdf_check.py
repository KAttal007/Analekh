"""Only real PDFs are stored as documents: an HTML error page, an empty body or anything else that
NSE answers with a 200 is refused before it reaches storage (issue 5)."""

import httpx
import pytest
from sqlalchemy import func, select

from analekh.db.models import Company, FeedItem, Filing
from analekh.ingest.http import PoliteClient
from tests.test_docs import make_pdf

ARCHIVE = "https://nsearchives.nseindia.com/corporate/"


@pytest.fixture
def company(db):
    c = Company(nse_symbol="DEMOFIN", name="Demo Finance Limited")
    db.add(c)
    db.flush()
    return c


def count(db, company) -> int:
    return db.scalar(
        select(func.count()).select_from(Filing).where(Filing.company_id == company.id)
    )


def store_it(db, store, company, data: bytes, **kw):
    from analekh.ingest.pipeline import store_document

    return store_document(db, store, company, data, kind="presentation", **kw)


@pytest.mark.parametrize(
    ("data", "label"),
    [
        (b"<html><body>Service Unavailable</body></html>", "html"),
        (b"<!DOCTYPE html><html>Access Denied</html>", "html"),
        (b"  \n<?xml version='1.0'?><Error/>", "xml"),  # also NSE's announcement XML files
        (b"", "empty"),
        (b"   \r\n  ", "empty"),
        (b"PK\x03\x04 this is a zip", "zip"),  # e.g. a company's KMP document
        (b'{"error": "too many requests"}', "unknown"),
    ],
)
def test_a_file_that_is_not_a_pdf_is_refused_and_nothing_is_stored(db, store, company, data, label):
    from analekh.ingest.pipeline import NotAPdf

    with pytest.raises(NotAPdf, match=label):
        store_it(db, store, company, data, source_url=ARCHIVE + "deck.pdf")
    assert count(db, company) == 0
    assert not any(p.is_file() for p in store.root.rglob("*"))  # no object written either


def test_a_real_pdf_is_stored(db, store, company):
    filing = store_it(db, store, company, make_pdf(["Investor presentation"]))
    assert filing.status == "fetched" and store.exists(filing.storage_key)


def test_a_pdf_with_a_little_leading_whitespace_is_accepted(db, store, company):
    """Blank space before the header is fine; anything else before it is not."""
    data = b"\n\r\n " + make_pdf(["Annual report"])
    assert store_it(db, store, company, data).status == "fetched"


def test_a_pdf_header_after_other_content_is_not_accepted(db, store, company):
    from analekh.ingest.pipeline import NotAPdf

    with pytest.raises(NotAPdf):
        store_it(db, store, company, b"<html>" + b" " * 2000 + b"%PDF-1.7")


def test_the_same_bad_bytes_twice_still_store_nothing(db, store, company):
    from analekh.ingest.pipeline import NotAPdf

    for _ in range(2):
        with pytest.raises(NotAPdf):
            store_it(db, store, company, b"<html>nope</html>")
    assert count(db, company) == 0


@pytest.mark.parametrize("cut_at", [20, 120, 610])  # PyMuPDF: raises, reads 0 pages, raises
def test_a_truncated_pdf_is_stored_and_the_document_queue_marks_it_failed(
    db, store, company, cut_at
):
    """The header can't tell a cut-off download from a good one; opening the file does. A file
    that opens with no pages is as unreadable as one that doesn't open."""
    from analekh.docs.pipeline import process_documents

    cut = make_pdf(["Gold loan AUM 82,000 crore", "Second page text here"])[:cut_at]
    filing = store_it(db, store, company, cut)
    assert filing.status == "fetched"
    run = process_documents(db, store, [filing], claude=None, embedder=None)
    assert run.failed == 1 and filing.status == "failed" and filing.meta.get("error")


def test_a_feed_item_with_an_error_page_is_given_up_at_once_and_the_queue_goes_on(
    db, store, company
):
    from analekh.ingest.pipeline import process_feed_items

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("bad.pdf"):
            return httpx.Response(200, content=b"<html>Service Unavailable</html>")
        return httpx.Response(200, content=make_pdf(["Investor presentation"]))

    client = PoliteClient(
        transport=httpx.MockTransport(handler), backoff_base=0, rate_per_second=100_000
    )
    items = []
    for name in ("bad.pdf", "good.pdf"):
        item = FeedItem(
            feed="announcements",
            item_key=name,
            title="Investor presentation",
            link=ARCHIVE + name,
            company_id=company.id,
        )
        db.add(item)
        items.append(item)
    db.flush()

    run = process_feed_items(db, store, client, items)
    bad, good = items
    assert run.done == 1 and run.failed == 1 and run.stopped is None
    assert bad.processed_at is not None and "html" in (bad.error or "").lower()  # no retries
    assert good.processed_at is not None and good.error is None
    assert count(db, company) == 1
