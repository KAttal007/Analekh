"""IPO API routes (plan Task 8). Synthetic data; sign-in enforced on every route."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from analekh.api.deps import get_current, get_store, get_user
from analekh.api.main import app
from analekh.db.models import Company, IpoDocument, IpoFinancial, IpoIssue
from analekh.db.models import User as UserRow
from analekh.db.session import get_session
from analekh.ipo import coverage as coverage_module
from analekh.ipo.symbols import link_listed, valid_symbol

ROUTES = [
    ("GET", "/ipo/issues"),
    ("GET", "/ipo/issues/1"),
    ("POST", "/ipo/issues/1/coverage"),
    ("GET", "/ipo/issues/1/coverage"),
    ("POST", "/ipo/issues/1/symbol"),
]


@pytest.fixture
def client(db, store):
    app.dependency_overrides[get_session] = lambda: db
    app.dependency_overrides[get_store] = lambda: store
    admin = UserRow(id="local", email="admin@test.local", name="Admin", role="admin")
    if db.get(UserRow, "local") is None:
        db.add(admin)
        db.flush()
    app.dependency_overrides[get_current] = lambda: admin
    app.dependency_overrides[get_user] = lambda: "local"
    yield TestClient(app)
    app.dependency_overrides.clear()


def _issue(db, stem, name, filed=None, symbol=None) -> IpoIssue:
    issue = IpoIssue(stem=stem, name=name, symbol=symbol)
    db.add(issue)
    db.flush()
    return issue


def _doc(db, issue, stage, sha, sebi, filed, status="extracted") -> IpoDocument:
    doc = IpoDocument(
        issue_id=issue.id,
        stage=stage,
        sebi_id=sebi,
        entry_url="https://www.sebi.gov.in/filings/public-issues/x_1.html",
        pdf_url="https://www.sebi.gov.in/sebi_data/attachdocs/x.pdf",
        file_sha256=sha,
        storage_key=f"{sha}.pdf",
        filed_on=filed,
        status=status,
        meta={},
    )
    db.add(doc)
    db.flush()
    return doc


def _fig(db, doc, basis, period_end, line, amount, label):
    db.add(
        IpoFinancial(
            document_id=doc.id,
            basis=basis,
            period_end=period_end,
            period_label=label,
            is_stub=False,
            line=line,
            amount=Decimal(amount),
            unit="INR",
            page=50,
        )
    )
    db.flush()


def test_requires_sign_in():
    fresh = TestClient(app)
    for method, path in ROUTES:
        resp = fresh.request(method, path, json={"symbol": "ABC"} if method == "POST" else None)
        assert resp.status_code == 401, (method, path)


def test_issues_list_newest_first(client, db):
    older = _issue(db, "older co", "Older Co Limited")
    _doc(db, older, "rhp", "1" * 64, "1", date(2026, 10, 1))
    newer = _issue(db, "newer co", "Newer Co Limited")
    _doc(db, newer, "rhp", "2" * 64, "2", date(2026, 10, 20))
    body = client.get("/ipo/issues").json()
    names = [row["name"] for row in body]
    assert names.index("Newer Co Limited") < names.index("Older Co Limited")
    row = next(r for r in body if r["name"] == "Newer Co Limited")
    assert row["current_stage"] == "rhp"
    assert row["stages"] == ["rhp"]


def test_detail_shows_both_bases_and_restatements(client, db):
    issue = _issue(db, "detail co", "Detail Co Limited")
    rhp = _doc(db, issue, "rhp", "3" * 64, "3", date(2026, 10, 15))
    pro = _doc(db, issue, "prospectus", "4" * 64, "4", date(2026, 10, 26))
    _fig(db, rhp, "consolidated", date(2026, 3, 31), "profit_after_tax", "100", "FY26")
    _fig(db, pro, "consolidated", date(2026, 3, 31), "profit_after_tax", "110", "FY26")
    _fig(db, pro, "standalone", date(2026, 3, 31), "profit_after_tax", "90", "FY26")
    body = client.get(f"/ipo/issues/{issue.id}").json()
    assert body["current_stage"] == "prospectus"
    assert {f["period_label"] for f in body["financials"]["consolidated"]} == {"FY26"}
    assert body["financials"]["standalone"][0]["amount"] == "90.0000"
    assert body["restatements"][0]["old"] == "100.0000"
    assert body["restatements"][0]["new"] == "110.0000"


def test_coverage_409_without_document(client, db):
    issue = _issue(db, "empty co", "Empty Co Limited")
    resp = client.post(f"/ipo/issues/{issue.id}/coverage")
    assert resp.status_code == 409
    assert resp.json()["detail"] == "no offer document yet"


def test_coverage_returns_placeholders(client, db, monkeypatch):
    from analekh.db.models import IpoDraft

    issue = _issue(db, "draft co", "Draft Co Limited")
    doc = _doc(db, issue, "rhp", "5" * 64, "5", date(2026, 10, 15))

    def fake_generate(session, claude, issue_id, user):
        draft = IpoDraft(
            issue_id=issue_id,
            document_id=doc.id,
            sections={
                "mdna": {"key": "mdna", "text": "Revenue grew.", "blocked": False, "unmatched": [], "style_issues": []},
                "rating": coverage_module.RATING_PLACEHOLDER,
                "rationale": coverage_module.RATIONALE_PLACEHOLDER,
                "stage": "rhp",
            },
            created_by=user,
        )
        session.add(draft)
        session.flush()
        return draft

    monkeypatch.setattr("analekh.api.routers.ipo.generate", fake_generate)
    monkeypatch.setattr("analekh.api.routers.ipo.Claude", lambda s: object())
    body = client.post(f"/ipo/issues/{issue.id}/coverage").json()
    assert body["rating"] == "[Analyst to set rating]"
    assert body["rationale"] == "[Analyst rationale]"
    assert body["stage"] == "rhp"


def test_symbol_is_validated(client, db):
    issue = _issue(db, "sym co", "Sym Co Limited")
    assert client.post(f"/ipo/issues/{issue.id}/symbol", json={"symbol": "bad symbol!"}).status_code == 422
    assert client.post(f"/ipo/issues/{issue.id}/symbol", json={"symbol": "A" * 21}).status_code == 422
    ok = client.post(f"/ipo/issues/{issue.id}/symbol", json={"symbol": "M&M-X"})
    assert ok.status_code == 200
    assert valid_symbol("M&M-X") and not valid_symbol("")


def test_bhavcopy_link_needs_one_match(db):
    db.add(Company(nse_symbol="ZZIPOA", name="Zeta Works Limited"))
    db.add(Company(nse_symbol="ZZIPOB", name="Zeta Works Limited"))
    db.add(Company(nse_symbol="ZETAW", name="Zeta Works Limited"))
    issue = _issue(db, "zeta works", "Zeta Works Limited")
    db.add(Company(nse_symbol="UNIQ1", name="Quartz Mills Limited"))
    quartz = _issue(db, "quartz mills", "Quartz Mills Limited")
    linked = link_listed(db)
    db.refresh(issue)
    db.refresh(quartz)
    assert issue.symbol is None  # two candidates: never guessed
    assert quartz.symbol == "UNIQ1"
    assert linked == 1


def test_other_value_errors_are_not_reported_as_409(client, db, monkeypatch):
    """A malformed model reply (a ValueError) must not be passed off as "no offer document yet"."""
    issue = _issue(db, "boom co", "Boom Co Limited")

    def boom(*args, **kwargs):
        raise ValueError("Expecting value: line 1 column 1 (char 0)")

    monkeypatch.setattr("analekh.api.routers.ipo.generate", boom)
    monkeypatch.setattr("analekh.api.routers.ipo.Claude", lambda s: object())
    with pytest.raises(ValueError, match="Expecting value"):
        client.post(f"/ipo/issues/{issue.id}/coverage")
