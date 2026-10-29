"""Reading offer documents, versions and restatements (plan Task 5). Synthetic PDFs, scripted Claude."""

from datetime import date
from decimal import Decimal
from typing import Any

import pymupdf
from sqlalchemy import func, select

from analekh.db.models import IpoChunk, IpoDocument, IpoFinancial, IpoIssue
from analekh.ingest.storage import LocalStore
from analekh.ipo.read import read_document, read_pending
from analekh.ipo.versions import current_document, restatements

STATEMENT = "Restated consolidated statement of profit and loss\nRevenue from operations 1,000 1,200 1,500\nProfit after tax 100 120 150"


def make_pdf(pages: list[str]) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


class EmptyClaude:
    def create_json(self, purpose: str, schema: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return {"tables": []}


class BrokenClaude:
    def create_json(self, purpose: str, schema: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("upstream down")


def _issue(db, stem="jio platforms") -> IpoIssue:
    issue = IpoIssue(stem=stem, name="Jio Platforms Limited")
    db.add(issue)
    db.flush()
    return issue


def _doc(db, issue, stage, sebi, sha, storage_key="x.pdf", status="extracted") -> IpoDocument:
    doc = IpoDocument(
        issue_id=issue.id,
        stage=stage,
        sebi_id=sebi,
        entry_url="https://www.sebi.gov.in/filings/public-issues/x_1.html",
        pdf_url="https://www.sebi.gov.in/sebi_data/attachdocs/x.pdf",
        file_sha256=sha,
        storage_key=storage_key,
        status=status,
    )
    db.add(doc)
    db.flush()
    return doc


def _figure(db, doc, line, amount, period_end=date(2026, 3, 31)):
    db.add(
        IpoFinancial(
            document_id=doc.id,
            basis="consolidated",
            period_end=period_end,
            period_label="FY26",
            is_stub=False,
            line=line,
            amount=Decimal(amount),
            unit="INR",
            page=10,
        )
    )
    db.flush()


def test_prospectus_figures_supersede_rhp(db):
    issue = _issue(db)
    _doc(db, issue, "rhp", "1", "1" * 64)
    pro = _doc(db, issue, "prospectus", "2", "2" * 64)
    assert current_document(db, issue.id).id == pro.id


def test_current_document_falls_back_to_rhp_when_prospectus_failed(db):
    issue = _issue(db, "acme")
    rhp = _doc(db, issue, "rhp", "3", "3" * 64)
    _doc(db, issue, "prospectus", "4", "4" * 64, status="failed")
    assert current_document(db, issue.id).id == rhp.id


def test_restatements_list_only_changed_amounts(db):
    issue = _issue(db)
    rhp = _doc(db, issue, "rhp", "5", "5" * 64)
    pro = _doc(db, issue, "prospectus", "6", "6" * 64)
    _figure(db, rhp, "revenue_from_operations", "1000")
    _figure(db, rhp, "profit_after_tax", "100")
    _figure(db, pro, "revenue_from_operations", "1000")  # unchanged
    _figure(db, pro, "profit_after_tax", "110")  # restated
    changed = restatements(db, issue.id)
    assert [(r.line, r.old, r.new) for r in changed] == [("profit_after_tax", Decimal("100"), Decimal("110"))]


def test_no_restatements_with_one_stage(db):
    issue = _issue(db, "solo")
    rhp = _doc(db, issue, "rhp", "7", "7" * 64)
    _figure(db, rhp, "revenue_from_operations", "1000")
    assert restatements(db, issue.id) == []


def test_failed_document_does_not_stop_the_batch(db, tmp_path):
    store = LocalStore(tmp_path)
    issue = _issue(db, "batch")
    store.put("good.pdf", make_pdf(["cover", STATEMENT]), "application/pdf")
    good = _doc(db, issue, "rhp", "8", "8" * 64, storage_key="good.pdf", status="new")
    bad = _doc(db, issue, "rhp", "9", "9" * 64, storage_key="missing.pdf", status="new")
    done = read_pending(db, store, EmptyClaude())
    db.refresh(good)
    db.refresh(bad)
    assert done == 2
    assert good.status == "extracted"
    assert bad.status == "failed"
    assert "error" in bad.meta


def test_claude_failure_marks_only_that_document(db, tmp_path):
    store = LocalStore(tmp_path)
    issue = _issue(db, "claudefail")
    store.put("c.pdf", make_pdf(["cover", STATEMENT]), "application/pdf")
    doc = _doc(db, issue, "rhp", "10", "a" * 64, storage_key="c.pdf", status="new")
    read_document(db, store, BrokenClaude(), doc)
    db.refresh(doc)
    assert doc.status == "failed"
    assert "upstream down" in doc.meta["error"]


def test_chunks_are_searchable(db, tmp_path):
    store = LocalStore(tmp_path)
    issue = _issue(db, "searchable")
    store.put("s.pdf", make_pdf(["cover page", STATEMENT]), "application/pdf")
    doc = _doc(db, issue, "rhp", "11", "b" * 64, storage_key="s.pdf", status="new")
    read_document(db, store, EmptyClaude(), doc)
    hit = db.scalar(
        select(IpoChunk.page).where(
            IpoChunk.document_id == doc.id,
            IpoChunk.tsv.op("@@")(func.plainto_tsquery("english", "profit loss")),
        )
    )
    assert hit == 2
