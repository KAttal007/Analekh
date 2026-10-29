"""Offer terms and listed peers (plan Task 6). Synthetic PDFs, scripted Claude."""

from typing import Any

import pymupdf

from analekh.docs.pdf import read_pages
from analekh.ipo.terms import extract_terms, select_terms_pages

TERMS_PAGE = "Price band of Rs 700 to Rs 750 per equity share of face value Rs 10\nFresh issue of equity shares aggregating to Rs 2,000 crore"
PEERS_PAGE = "Comparison with listed industry peers\nPeer A 45.2 12.5 14.1%\nPeer B 38.0 9.1 11.0%"


def make_pdf(pages: list[str]) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


class ScriptedClaude:
    def __init__(self, answer: dict[str, Any]):
        self.answer = answer

    def create_json(self, purpose: str, schema: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return self.answer


def test_select_terms_pages():
    pages = read_pages(make_pdf(["cover", TERMS_PAGE, PEERS_PAGE, "risk factors"]), ocr=False)
    assert select_terms_pages(pages) == [2, 3]


def test_terms_amounts_in_rupees():
    answer = {
        "page": 2,
        "price_band_low": "700",
        "price_band_high": "750",
        "face_value": "10",
        "fresh_issue_amount": "2,000",
        "offer_for_sale_amount": None,
        "amount_unit": "INR crore",
        "post_issue_shares": "1,000,000",
        "peers": [],
    }
    terms = extract_terms(ScriptedClaude(answer), make_pdf(["cover", TERMS_PAGE]), [2])
    assert terms["fresh_issue_amount"] == "20000000000"
    assert terms["price_band_low"] == "700"
    assert terms["post_issue_shares"] == "1000000"


def test_peers_kept_with_page():
    answer = {
        "page": 3,
        "price_band_low": None,
        "price_band_high": None,
        "face_value": None,
        "fresh_issue_amount": None,
        "offer_for_sale_amount": None,
        "amount_unit": "INR",
        "post_issue_shares": None,
        "peers": [
            {"name": "Peer A", "pe": "45.2", "eps": "12.5", "ronw": "14.1", "page": 3},
            {"name": "Peer B", "pe": "38.0", "eps": "9.1", "ronw": "11.0", "page": 3},
        ],
    }
    terms = extract_terms(ScriptedClaude(answer), make_pdf(["cover", "x", PEERS_PAGE]), [3])
    assert [p["name"] for p in terms["peers"]] == ["Peer A", "Peer B"]
    assert all(p["page"] == 3 for p in terms["peers"])
    assert terms["peers"][0]["pe"] == "45.2"


def test_missing_price_band_returns_none_not_zero():
    answer = {
        "page": 2,
        "price_band_low": None,
        "price_band_high": None,
        "face_value": None,
        "fresh_issue_amount": None,
        "offer_for_sale_amount": None,
        "amount_unit": "INR",
        "post_issue_shares": None,
        "peers": [],
    }
    terms = extract_terms(ScriptedClaude(answer), make_pdf(["cover", TERMS_PAGE]), [2])
    assert terms["price_band_low"] is None
    assert terms["price_band_high"] is None
    assert terms["face_value"] is None


def test_read_document_stores_terms_in_meta(db, tmp_path):
    from datetime import date

    from analekh.db.models import IpoDocument, IpoIssue
    from analekh.ingest.storage import LocalStore
    from analekh.ipo.read import read_document

    class Both:
        def create_json(self, purpose, schema, **kwargs):
            if purpose == "ipo_terms":
                return {
                    "page": 2,
                    "price_band_low": "700",
                    "price_band_high": "750",
                    "face_value": "10",
                    "fresh_issue_amount": None,
                    "offer_for_sale_amount": None,
                    "amount_unit": "INR",
                    "post_issue_shares": None,
                    "peers": [],
                }
            return {"tables": []}

    store = LocalStore(tmp_path)
    store.put("t.pdf", make_pdf(["cover", TERMS_PAGE]), "application/pdf")
    issue = IpoIssue(stem="terms co", name="Terms Co Limited")
    db.add(issue)
    db.flush()
    doc = IpoDocument(
        issue_id=issue.id,
        stage="rhp",
        sebi_id="900",
        entry_url="e",
        pdf_url="p",
        file_sha256="9" * 64,
        storage_key="t.pdf",
        status="new",
        filed_on=date(2026, 10, 1),
    )
    db.add(doc)
    db.flush()
    read_document(db, store, Both(), doc)
    assert doc.status == "extracted"
    assert doc.meta["terms"]["price_band_low"] == "700"
    assert doc.meta["terms"]["price_band_high"] == "750"
