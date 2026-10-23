"""NSE's latest-results list is read in ONE request per watcher run (rule 1). The page size adapts:
a truncated page is detected from NSE's own totalCount, the next run asks for more (doubling, up
to a cap), and a full run goes back to the default. Rows past the page are picked up later."""

import httpx
import pytest
from sqlalchemy import select

from analekh.config import get_settings
from analekh.db.models import Company, Filing
from analekh.ingest.http import PoliteClient
from tests.xbrl_factory import q2_instance

ARCHIVE = "https://nsearchives.nseindia.com/corporate/xbrl/"
LOOKUP = "/api/integrated-filing-results"


def list_client(rows: list[dict], total: int | None, files: dict[str, bytes] | None = None):
    """Mock NSE's latest list: ``rows`` with ``totalCount`` = ``total`` (left out if None)."""
    sizes: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == LOOKUP:
            sizes.append(request.url.params["size"])
            body: dict = {"data": rows}
            if total is not None:
                body["totalCount"] = total
            return httpx.Response(200, json=body)
        return httpx.Response(200, content=(files or {}).get(str(request.url), q2_instance()))

    # No real waiting between mock requests (the production rate is 1 per second).
    client = PoliteClient(
        transport=httpx.MockTransport(handler), backoff_base=0, rate_per_second=100_000
    )
    return client, sizes


def row(symbol: str, n: int) -> dict:
    return {"symbol": symbol, "qe_Date": "30-SEP-2026", "xbrl": f"{ARCHIVE}F{n}.xml"}


@pytest.fixture
def company(db):
    c = Company(nse_symbol="DEMOFIN", name="Demo Finance Limited")
    db.add(c)
    db.flush()
    return c


# --- detecting a truncated page --------------------------------------------------------------


def test_truncated_page_is_detected_from_nses_total_count(db, store, company):
    from analekh.ingest.integrated import fetch_latest

    rows = [row("DEMOFIN", i) for i in range(3)]
    client, _ = list_client(rows, total=1200)
    out = fetch_latest(db, store, client, size=get_settings().latest_page_size)
    assert out.truncated is True and out.total == 1200 and out.listed == 3


def test_page_holding_every_row_is_not_truncated(db, store, company):
    from analekh.ingest.integrated import fetch_latest

    client, _ = list_client([row("DEMOFIN", 1), row("DEMOFIN", 2)], total=2)
    out = fetch_latest(db, store, client, size=get_settings().latest_page_size)
    assert out.truncated is False and out.total == 2


def test_nse_capping_the_page_below_what_we_asked_is_truncation(db, store, company):
    """We ask for the default size, NSE returns 500 of 800: a truncated page, whatever it holds."""
    from analekh.ingest.integrated import fetch_latest

    rows = [row("DEMOFIN", i) for i in range(500)]
    client, sizes = list_client(rows, total=800)
    out = fetch_latest(db, store, client, size=get_settings().latest_page_size)
    assert sizes == [str(get_settings().latest_page_size)] and out.truncated is True


def test_empty_list_with_zero_total_is_not_truncated(db, store, company):
    from analekh.ingest.integrated import fetch_latest

    client, _ = list_client([], total=0)
    out = fetch_latest(db, store, client, size=get_settings().latest_page_size)
    assert out.truncated is False and out.listed == 0


def test_without_total_count_a_full_page_counts_as_truncated(db, store, company):
    """No totalCount in the answer: we can only guess, so a page as big as we asked is suspect."""
    from analekh.ingest.integrated import fetch_latest

    full = [row("DEMOFIN", i) for i in range(5)]
    client, _ = list_client(full, total=None)
    assert fetch_latest(db, store, client, size=5).truncated is True
    client, _ = list_client(full[:3], total=None)
    assert fetch_latest(db, store, client, size=5).truncated is False
    assert fetch_latest(db, store, client, size=5).total is None


def test_truncated_run_still_stores_the_rows_it_received(db, store, company):
    from analekh.ingest.integrated import fetch_latest

    rows = [row("DEMOFIN", 1)]
    client, _ = list_client(rows, total=50)
    out = fetch_latest(db, store, client, size=get_settings().latest_page_size)
    assert out.truncated and out.new == 1
    assert db.scalar(select(Filing).where(Filing.source_url == rows[0]["xbrl"])) is not None


# --- the size for the next run ---------------------------------------------------------------


def test_first_run_asks_for_the_default_size():
    from analekh.ingest.integrated import next_page_size

    default = get_settings().latest_page_size
    assert next_page_size(None) == default
    assert next_page_size({}) == default


def test_a_truncated_run_doubles_the_size_for_the_next(db):
    from analekh.ingest.integrated import next_page_size

    s = get_settings()
    once = {"page_size": s.latest_page_size, "truncated": True}
    assert next_page_size(once) == min(s.latest_page_size * 2, s.latest_max_page_size)


def test_size_never_goes_past_the_cap():
    from analekh.ingest.integrated import next_page_size

    cap = get_settings().latest_max_page_size
    assert next_page_size({"page_size": cap, "truncated": True}) == cap
    assert next_page_size({"page_size": cap - 1, "truncated": True}) == cap


def test_a_full_run_goes_back_to_the_default():
    from analekh.ingest.integrated import next_page_size

    s = get_settings()
    default = s.latest_page_size
    assert next_page_size({"page_size": s.latest_max_page_size, "truncated": False}) == default
    assert next_page_size({"page_size": default * 2, "truncated": False}) == default


def test_a_damaged_summary_falls_back_to_the_default():
    from analekh.ingest.integrated import next_page_size

    default = get_settings().latest_page_size
    assert next_page_size({"truncated": True}) == default * 2  # no size kept: start from default
    assert next_page_size({"page_size": "lots", "truncated": True}) == default * 2
    assert next_page_size({"page_size": -5, "truncated": False}) == default


# --- at the cap -----------------------------------------------------------------------------


def test_truncated_at_the_cap_is_flagged_for_a_bulk_run(db, store, company):
    from analekh.ingest.integrated import fetch_latest

    client, _ = list_client([row("DEMOFIN", 1)], total=9000)
    out = fetch_latest(db, store, client, size=4000)
    assert out.truncated and out.capped
    assert out.warning and "bulk" in out.warning.lower()


def test_truncated_below_the_cap_is_not_flagged_as_capped(db, store, company):
    from analekh.ingest.integrated import fetch_latest

    client, _ = list_client([row("DEMOFIN", 1)], total=900)
    out = fetch_latest(db, store, client, size=get_settings().latest_page_size)
    assert out.truncated and not out.capped and out.warning is None
