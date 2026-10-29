"""SEBI offer-document watcher (plan Task 3). Mocked HTTP only; nothing reaches sebi.gov.in."""

import httpx
from sqlalchemy import select

from analekh.db.models import IpoDocument, IpoIssue
from analekh.ingest.http import PoliteClient
from analekh.ingest.storage import LocalStore
from analekh.ipo.watch import watch

BASE = "https://www.sebi.gov.in"
RHP_ENTRY = f"{BASE}/filings/public-issues/oct-2026/jio-platforms-limited-rhp_105274.html"
PRO_ENTRY = f"{BASE}/filings/public-issues/oct-2026/jio-platforms-ltd-prospectus_105427.html"
RHP_PDF = f"{BASE}/sebi_data/attachdocs/oct-2026/1792045029108.pdf"
PRO_PDF = f"{BASE}/sebi_data/attachdocs/oct-2026/1793005577827.pdf"


def _list(rows: list[tuple[str, str, str]]) -> str:
    body = "".join(f"<tr role='row'><td>{date}</td><td><a href='{url}' title='{title}'>{title}</a></td></tr>" for date, url, title in rows)
    return f"<table><tbody>{body}</tbody></table>"


def _entry(pdf: str) -> str:
    return f"<iframe src='../../../web/?file={pdf}' width='100%'></iframe>"


class Site:
    """Serves the lists, entry pages and PDFs; records every request URL."""

    def __init__(self, rhp_rows=None, pro_rows=None, pages=None, pdfs=None, deny=()):
        self.rhp_rows = rhp_rows or []
        self.pro_rows = pro_rows or []
        self.pages = pages or {}
        self.pdfs = pdfs or {}
        self.deny = set(deny)
        self.requests: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.requests.append(url)
        if url in self.deny:
            return httpx.Response(403)
        if "smid=11" in url:
            return httpx.Response(200, text=_list(self.rhp_rows))
        if "smid=12" in url:
            return httpx.Response(200, text=_list(self.pro_rows))
        if url in self.pages:
            return httpx.Response(200, text=self.pages[url])
        if url in self.pdfs:
            return httpx.Response(200, content=self.pdfs[url])
        return httpx.Response(404)


def _run(db, site: Site, tmp_path):
    client = PoliteClient(transport=httpx.MockTransport(site), backoff_base=0, rate_per_second=1000)
    return watch(db, LocalStore(tmp_path), client)


def _full_site(rhp_pdf=b"%PDF-rhp", pro_pdf=b"%PDF-pro") -> Site:
    return Site(
        rhp_rows=[("Oct 15, 2026", RHP_ENTRY, "Jio Platforms Limited – RHP")],
        pro_rows=[("Oct 26, 2026", PRO_ENTRY, "Jio Platforms Ltd.- Prospectus")],
        pages={RHP_ENTRY: _entry(RHP_PDF), PRO_ENTRY: _entry(PRO_PDF)},
        pdfs={RHP_PDF: rhp_pdf, PRO_PDF: pro_pdf},
    )


def test_new_entries_become_documents(db, tmp_path):
    result = _run(db, _full_site(), tmp_path)
    assert result.new == 2
    assert result.stopped is None
    docs = db.scalars(select(IpoDocument).order_by(IpoDocument.stage)).all()
    assert [d.stage for d in docs] == ["prospectus", "rhp"]
    assert all(d.status == "new" for d in docs)
    assert {d.sebi_id for d in docs} == {"105274", "105427"}


def test_second_run_adds_nothing(db, tmp_path):
    site = _full_site()
    _run(db, site, tmp_path)
    again = _run(db, site, tmp_path)
    assert again.new == 0
    assert again.skipped == 2
    assert db.scalar(select(IpoDocument.id).limit(1)) is not None
    assert len(db.scalars(select(IpoDocument)).all()) == 2


def test_same_pdf_under_two_entries_stored_once(db, tmp_path):
    same = b"%PDF-same"
    site = Site(
        rhp_rows=[("Oct 15, 2026", RHP_ENTRY, "Jio Platforms Limited – RHP")],
        pro_rows=[("Oct 26, 2026", PRO_ENTRY, "Jio Platforms Ltd.- Prospectus")],
        pages={RHP_ENTRY: _entry(RHP_PDF), PRO_ENTRY: _entry(PRO_PDF)},
        pdfs={RHP_PDF: same, PRO_PDF: same},
    )
    result = _run(db, site, tmp_path)
    assert result.new == 1
    assert len(db.scalars(select(IpoDocument)).all()) == 1


def test_rhp_and_prospectus_join_one_issue(db, tmp_path):
    _run(db, _full_site(), tmp_path)
    issues = db.scalars(select(IpoIssue)).all()
    assert len(issues) == 1
    assert issues[0].stem == "jio platforms"
    assert issues[0].name == "Jio Platforms Limited"
    assert len({d.issue_id for d in db.scalars(select(IpoDocument)).all()}) == 1


def test_403_stops_the_run(db, tmp_path):
    site = Site(
        rhp_rows=[
            ("Oct 15, 2026", RHP_ENTRY, "Jio Platforms Limited – RHP"),
            ("Oct 13, 2026", f"{BASE}/filings/public-issues/oct-2026/other-rhp_105195.html", "Other Limited – RHP"),
        ],
        pages={RHP_ENTRY: _entry(RHP_PDF)},
        pdfs={RHP_PDF: b"%PDF-rhp"},
        deny={RHP_ENTRY},
    )
    result = _run(db, site, tmp_path)
    assert result.stopped is not None
    assert result.new == 0
    assert not any("other-rhp_105195" in u for u in site.requests)
    assert not any("smid=12" in u for u in site.requests)


def test_drhp_list_is_never_requested(db, tmp_path):
    site = _full_site()
    _run(db, site, tmp_path)
    assert site.requests
    assert not any("smid=10" in u for u in site.requests)
