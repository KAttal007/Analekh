from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from analekh.db.models import Company, Fact, FeedItem, Filing
from analekh.ingest.backfill import run_backfill
from analekh.ingest.feeds import item_key, parse_pub_date, parse_rss, store_items
from analekh.ingest.http import DisallowedHostError, PoliteClient, identity_headers
from analekh.ingest.linking import CompanyIndex, normalise_name
from analekh.ingest.pipeline import classify_announcement, ingest_results_xbrl
from analekh.universe.sectors import taxonomy_for_sector
from tests.xbrl_factory import q1_instance, q2_instance

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<title>Financial Results</title><ttl>5</ttl>
<item><title>Demo Finance Limited</title>
<link>https://nsearchives.nseindia.com/corporate/xbrl/INDAS_1.xml</link>
<description>Financial results for the quarter ended 30-Sep-2026</description>
<pubDate>Tue, 10 Nov 2026 18:05:00 +0530</pubDate></item>
<item><title>Unknown Co Ltd</title><link>https://nsearchives.nseindia.com/x.xml</link>
<pubDate>Tue, 10 Nov 2026 18:06:00 +0530</pubDate></item>
</channel></rss>"""


def test_parse_rss_and_item_key():
    items = parse_rss(RSS)
    assert len(items) == 2
    assert items[0].pub_date is not None and items[0].pub_date.year == 2026
    assert items[0].item_key == item_key(items[0].link, items[0].pub_date_raw)
    assert items[0].item_key != items[1].item_key


def test_parse_rss_nse_pub_date():
    rss = b"""<rss version="2.0"><channel><item><title>Asian Hotels (West) Limited</title>
<link>https://nsearchives.nseindia.com/corporate/xbrl/INDAS_1.xml</link>
<pubDate>24-Aug-2026 17:39:16</pubDate></item></channel></rss>"""
    (item,) = parse_rss(rss)
    assert item.pub_date_raw == "24-Aug-2026 17:39:16"
    assert item.pub_date == datetime(2026, 8, 24, 12, 9, 16, tzinfo=UTC)  # 17:39:16 IST
    assert parse_pub_date("not a date") is None
    assert parse_pub_date(None) is None


def test_name_matching():
    c = Company(id=1, nse_symbol="DEMOFIN", name="Demo Finance Limited", isin="INE000D01011")
    other = Company(id=2, nse_symbol="ACME", name="Acme Industries Ltd")
    index = CompanyIndex.build([c, other])
    assert normalise_name("Demo Finance Ltd.") == normalise_name("DEMO FINANCE LIMITED")
    assert index.match("Demo Finance Limited") is c
    assert index.match("ACME - results") is other
    assert index.match("Results", "ISIN INE000D01011 quarter ended") is c
    assert index.match("Totally Different Corp") is None


def test_taxonomy_guess():
    assert taxonomy_for_sector("Banks") == "banking"
    assert taxonomy_for_sector("Financial Services", "NBFC") == "nbfc"
    assert taxonomy_for_sector("Insurance") == "insurance"
    assert taxonomy_for_sector("Capital Goods") == "indas"


def test_announcement_classifier():
    assert classify_announcement("Transcript of Earnings Call") == "transcript"
    assert classify_announcement("Investor Presentation Q2FY27") == "presentation"
    assert classify_announcement("Change in Directors") == "other"


def test_client_refuses_other_hosts():
    with pytest.raises(DisallowedHostError):
        PoliteClient().get("https://www.bseindia.com/anything")


def test_client_allows_only_the_integrated_filing_lookup_on_nseindia():
    client = PoliteClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"{}")), backoff_base=0
    )
    assert client.get("https://www.nseindia.com/").status == 200
    assert (
        client.get("https://www.nseindia.com/api/integrated-filing-results?symbol=X").status == 200
    )
    for path in ("/api/anything", "/get-quotes/equity", "/companies-listing/corporate-filings"):
        with pytest.raises(DisallowedHostError):
            client.get("https://www.nseindia.com" + path)


def test_client_allows_niftyindices_constituent_lists_only():
    client = PoliteClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"x")), backoff_base=0
    )
    assert (
        client.get("https://niftyindices.com/IndexConstituent/ind_nifty500list.csv").status == 200
    )
    with pytest.raises(DisallowedHostError):
        client.get("https://niftyindices.com/Backpage.aspx/getHistoricaldatatabletoString")


def test_client_retries_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        assert request.headers["User-Agent"].startswith("Analekh")
        return httpx.Response(200, content=b"ok", headers={"ETag": "abc"})

    client = PoliteClient(transport=httpx.MockTransport(handler), backoff_base=0)
    result = client.get("https://nsearchives.nseindia.com/content/RSS/Financial_Results.xml")
    assert result.content == b"ok" and result.etag == "abc" and calls["n"] == 3


# --- database integration (needs PostgreSQL) ---------------------------------------------------


@pytest.fixture
def company(db):
    c = Company(nse_symbol="DEMOFIN", name="Demo Finance Limited")
    db.add(c)
    db.flush()
    return c


def test_store_items_is_idempotent_and_links_companies(db, company):
    items = parse_rss(RSS)
    assert store_items(db, "financial_results", items) == 2
    assert store_items(db, "financial_results", items) == 0
    linked = db.scalar(select(FeedItem).where(FeedItem.title == "Demo Finance Limited"))
    assert linked is not None and linked.company_id == company.id


def test_ingest_dedupes_and_handles_restatement(db, store, company):
    first = ingest_results_xbrl(db, store, company, q1_instance())
    assert not first.skipped and first.report is not None
    assert first.filing.period_type == "Q" and first.filing.consolidated is True
    assert company.results_taxonomy == "indas"

    assert ingest_results_xbrl(db, store, company, q1_instance()).skipped

    q2 = ingest_results_xbrl(db, store, company, q2_instance())
    assert q2.report is not None and not q2.report.blocks_auto_apply
    v5 = next(r for r in q2.report.results if r.rule == "V5")
    assert v5.status == "pass"  # used Q1 from history

    restated = ingest_results_xbrl(db, store, company, q2_instance(revenue=1_010_000_000))
    v9 = next(r for r in restated.report.results if r.rule == "V9")
    assert v9.status == "fail"

    rows = db.scalars(
        select(Fact).where(
            Fact.company_id == company.id,
            Fact.element == "RevenueFromOperations",
            Fact.period_start == date(2026, 7, 1),
        )
    ).all()
    assert len(rows) == 2
    latest = [r for r in rows if r.is_latest]
    assert len(latest) == 1 and latest[0].value == Decimal("1010000000")
    assert store.exists(restated.filing.storage_key)


def test_backfill_from_import_folder(db, store, company, tmp_path):
    folder = tmp_path / "import" / "DEMOFIN"
    folder.mkdir(parents=True)
    (folder / "2026-06-30_results.xml").write_bytes(q1_instance())
    (folder / "2026-09-30_results.xml").write_bytes(q2_instance())
    (tmp_path / "import" / "NOSUCH").mkdir()
    summary = run_backfill(db, store, tmp_path / "import")
    assert len(summary.ingested) == 2 and summary.unknown_symbols == ["NOSUCH"]
    assert len(db.scalars(select(Filing).where(Filing.company_id == company.id)).all()) == 2


def test_s3_store_unreachable_raises_storage_unavailable():
    from botocore.exceptions import EndpointConnectionError

    from analekh.ingest.storage import S3Store, StorageUnavailable

    class Down:
        def head_bucket(self, **_):
            raise EndpointConnectionError(endpoint_url="http://localhost:9000/analekh")

    with pytest.raises(StorageUnavailable, match="not reachable"):
        S3Store(client=Down())


def test_identity_headers_keep_contact_out_of_user_agent():
    # NSE's CDN stalls any request whose User-Agent holds an email or a URL.
    assert identity_headers("Analekh/0.1 (contact: me@example.in)") == {
        "User-Agent": "Analekh/0.1",
        "From": "me@example.in",
    }
    assert identity_headers("Analekh/0.1 me@example.in https://x.org", "you@example.com") == {
        "User-Agent": "Analekh/0.1",
        "From": "you@example.com",
    }
    assert identity_headers("Analekh/0.1 (research)") == {"User-Agent": "Analekh/0.1 (research)"}


def test_integrated_filing_lookup_parses_rows_and_stays_on_allowed_paths():
    from analekh.ingest.integrated import lookup

    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        row = {
            "symbol": "DEMO",
            "qe_Date": "30-SEP-2026",
            "consolidated": "Standalone",
            "broadcast_Date": "13-Oct-2026 21:42:13",
            "type_Sub": "Original",
            "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_1.xml",
            "ixbrl": "https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_1.html",
            "pdf_attach": None,
        }
        return httpx.Response(200, json={"data": [row], "totalCount": 1, "page": 0, "size": 50})

    client = PoliteClient(transport=httpx.MockTransport(handler), backoff_base=0)
    (f,) = lookup(client, "demo")
    assert f.symbol == "DEMO" and f.period_end == date(2026, 9, 30) and f.consolidated is False
    assert f.broadcast_at == datetime(2026, 10, 13, 16, 12, 13, tzinfo=UTC)  # 21:42:13 IST
    assert f.xbrl_url and f.xbrl_url.startswith("https://nsearchives.nseindia.com/")
    assert set(f.links) == {"ixbrl", "xbrl"}  # no PDF attached
    (req,) = seen
    assert req.url.path == "/api/integrated-filing-results"
    assert req.url.params["index"] == "equity" and req.url.params["symbol"] == "DEMO"
    assert req.headers["Accept"] == "application/json" and "Referer" in req.headers
    assert req.headers["User-Agent"].startswith("Analekh")


def test_select_filings_newest_quarters_one_basis_originals_first():
    from analekh.ingest.integrated import IntegratedFiling, select_filings

    def filing(end: date, consolidated: bool, revision: str = "Original") -> IntegratedFiling:
        url = f"https://nsearchives.nseindia.com/x/{end}-{consolidated}-{revision}.xml"
        return IntegratedFiling("DEMO", end, consolidated, url, None, revision)

    listed = [
        filing(date(2026, 9, 30), True),
        filing(date(2026, 9, 30), False),
        filing(date(2026, 6, 30), False, "Revision"),
        filing(date(2026, 6, 30), False),
        filing(date(2026, 3, 31), True),
    ]
    picked = select_filings(listed, set(), quarters=2, one_basis=True)
    assert [(f.period_end, f.consolidated, f.revision) for f in picked] == [
        (date(2026, 6, 30), False, "Original"),  # no consolidated that quarter: standalone
        (date(2026, 6, 30), False, "Revision"),
        (date(2026, 9, 30), True, "Original"),  # consolidated wins
    ]
    assert select_filings(listed, {f.xbrl_url for f in listed if f.xbrl_url}) == []


def test_refused_tells_blocking_from_a_bad_file():
    from analekh.ingest.integrated import refused

    def status(code: int) -> httpx.HTTPStatusError:
        request = httpx.Request("GET", "https://www.nseindia.com/")
        return httpx.HTTPStatusError("x", request=request, response=httpx.Response(code))

    assert refused(status(403)) and refused(status(429)) and refused(httpx.ReadTimeout("stall"))
    assert not refused(status(404)) and not refused(ValueError("bad XBRL"))


def test_client_rate_can_be_set_per_run():
    assert PoliteClient(rate_per_second=0.2).limiter.interval == 5.0


def test_no_filings_list_records_reason_and_drops_resolved(tmp_path):
    import csv

    from analekh.ingest.integrated import FetchOutcome, record_gap

    path = tmp_path / "no-filings.csv"
    abbott = Company(nse_symbol="ABBOTINDIA", name="Abbott India Limited", series="EQ")
    demo = Company(nse_symbol="DEMO", name="Demo Limited", series="EQ")
    nothing = FetchOutcome(listed=0, with_xbrl=0, results=[])
    assert nothing.gap == "no integrated financials filings listed on NSE"
    assert FetchOutcome(listed=3, with_xbrl=0, results=[]).gap.startswith("3 filings listed")
    record_gap(path, abbott, nothing.gap, nothing)
    record_gap(path, demo, "error: ValueError: bad XBRL", None)
    with path.open(newline="", encoding="utf-8") as fh:
        rows = {r["symbol"]: r for r in csv.DictReader(fh)}
    assert rows["ABBOTINDIA"]["reason"] == nothing.gap and rows["ABBOTINDIA"]["listed"] == "0"
    assert rows["DEMO"]["reason"].startswith("error:")

    record_gap(path, demo, None, FetchOutcome(listed=6, with_xbrl=6, results=[]))  # resolved
    with path.open(newline="", encoding="utf-8") as fh:
        assert [r["symbol"] for r in csv.DictReader(fh)] == ["ABBOTINDIA"]


def test_fetch_results_skips_a_missing_file_and_keeps_the_rest(db, store, company):
    from analekh.ingest.integrated import fetch_results

    good = "https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_GOOD.xml"
    gone = "https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_GONE.xml"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/integrated-filing-results":
            rows = [
                {"symbol": company.nse_symbol, "qe_Date": "30-JUN-2026", "xbrl": gone},
                {"symbol": company.nse_symbol, "qe_Date": "30-SEP-2026", "xbrl": good},
            ]
            return httpx.Response(200, json={"data": rows, "totalCount": 2})
        if str(request.url) == gone:
            return httpx.Response(404)
        return httpx.Response(200, content=q2_instance())

    client = PoliteClient(transport=httpx.MockTransport(handler), backoff_base=0)
    outcome = fetch_results(db, store, client, company)
    assert outcome.missing == [gone] and outcome.new == 1 and outcome.gap is None


def test_fetch_latest_makes_one_list_request_and_stores_only_new_filings(db, store, company):
    from analekh.ingest.integrated import fetch_latest

    new = "https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_NEW.xml"
    other = "https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_OTHER.xml"
    lookups: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/integrated-filing-results":
            lookups.append(request)
            rows = [
                {"symbol": company.nse_symbol, "qe_Date": "30-SEP-2026", "xbrl": new},
                {"symbol": "NOTOURS", "qe_Date": "30-SEP-2026", "xbrl": other},
            ]
            return httpx.Response(200, json={"data": rows, "totalCount": 2})
        return httpx.Response(200, content=q2_instance())

    client = PoliteClient(transport=httpx.MockTransport(handler), backoff_base=0)
    first = fetch_latest(db, store, client)
    assert first.new == 1 and first.unknown_symbols == ["NOTOURS"]
    (req,) = lookups
    assert "symbol" not in req.url.params and req.url.params["size"] == "500"

    second = fetch_latest(db, store, client)  # same list again: nothing new to download
    assert second.new == 0 and len(lookups) == 2


def test_integrated_filing_null_attachment_is_no_link():
    from analekh.ingest.integrated import IntegratedFiling

    row = {
        "symbol": "DEMO",
        "qe_Date": "30-SEP-2026",
        "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/X.xml",
        "pdf_attach": "https://nsearchives.nseindia.com/corporate/null",  # as NSE sends it
    }
    f = IntegratedFiling.from_row(row)
    assert f.pdf_url is None and set(f.links) == {"xbrl"}
