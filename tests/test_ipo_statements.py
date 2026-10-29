"""Restated statements from offer documents (plan Task 4). Synthetic PDFs and a scripted Claude."""

from datetime import date
from decimal import Decimal
from typing import Any

import pymupdf
import pytest

from analekh.docs.pdf import read_pages
from analekh.ipo.statements import (
    ExtractedFigure,
    check_figures,
    extract_figures,
    select_statement_pages,
    store_figures,
    to_rupees,
)


def make_pdf(pages: list[str]) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


RESTATED_PL = "Restated consolidated statement of profit and loss\nRevenue from operations 1,000 1,200 1,500\nProfit after tax 100 120 150"


class ScriptedClaude:
    """Returns one canned JSON answer; records the last call."""

    def __init__(self, answer: dict[str, Any]):
        self.answer = answer
        self.calls: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    def create_json(self, purpose: str, schema: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        self.calls.append((purpose, schema, kwargs))
        return self.answer


def _fig(line, amount, period_end=date(2026, 3, 31), page=10, basis="consolidated", is_stub=False):
    return ExtractedFigure(
        basis=basis,
        period_end=period_end,
        period_label=f"FY{period_end.year % 100}",
        is_stub=is_stub,
        line=line,
        amount=Decimal(amount),
        unit="INR",
        page=page,
    )


# --- units -------------------------------------------------------------------------------


def test_to_rupees_lakh_crore_million():
    assert to_rupees("1,234.5", "INR crore") == Decimal("1234.5") * Decimal("10000000")
    assert to_rupees("12", "INR lakh") == Decimal("1200000")
    assert to_rupees("2", "INR million") == Decimal("2000000")


def test_brackets_are_negative_and_dash_is_zero():
    assert to_rupees("(1,234.5)", "INR lakh") == Decimal("-1234.5") * Decimal("100000")
    assert to_rupees("-", "INR crore") == Decimal("0")
    assert to_rupees("—", "INR crore") == Decimal("0")


def test_unknown_unit_raises():
    with pytest.raises(ValueError):
        to_rupees("1", "INR lakh crore")


def test_text_that_is_not_a_number_raises():
    with pytest.raises(ValueError):
        to_rupees("n.a.", "INR")


# --- locating pages ----------------------------------------------------------------------


def test_select_pages_finds_restated_statements():
    data = make_pdf(["Cover page of the red herring prospectus", RESTATED_PL, "Risk factors: we may lose key clients"])
    pages = read_pages(data, ocr=False)
    assert select_statement_pages(pages) == [2]


# --- checks ------------------------------------------------------------------------------


def test_check_flags_unit_slip():
    figures = [
        _fig("revenue_from_operations", "1000", page=10),
        _fig("revenue_from_operations", "10", page=55),  # 100x too small: same key, power of ten
    ]
    problems = check_figures(figures)
    assert problems
    assert all(f.flagged for f in figures)


def test_check_flags_pbt_mismatch():
    figures = [
        _fig("total_income", "1000"),
        _fig("total_expenses", "900"),
        _fig("profit_before_tax", "500"),  # 1000 - 900 = 100, not 500
    ]
    problems = check_figures(figures)
    assert problems
    assert any(f.flagged for f in figures)


def test_check_skips_when_a_side_is_missing():
    figures = [_fig("total_income", "1000"), _fig("profit_before_tax", "500")]
    assert check_figures(figures) == []
    assert not any(f.flagged for f in figures)


def test_store_marks_document_flagged_on_unit_slip(db):
    from analekh.db.models import IpoDocument, IpoIssue

    issue = IpoIssue(stem="x", name="X Limited")
    db.add(issue)
    db.flush()
    doc = IpoDocument(
        issue_id=issue.id,
        stage="rhp",
        sebi_id="1",
        entry_url="e",
        pdf_url="p",
        file_sha256="f" * 64,
        storage_key="k",
        status="read",
    )
    db.add(doc)
    db.flush()
    figures = [_fig("revenue_from_operations", "1000", page=10), _fig("revenue_from_operations", "10", page=55)]
    check_figures(figures)
    store_figures(db, doc, figures)
    assert doc.status == "flagged"


# --- extraction --------------------------------------------------------------------------


def _table(columns, rows, unit="INR crore", page=2, basis="consolidated"):
    return {"basis": basis, "unit": unit, "page": page, "columns": columns, "rows": rows}


def test_extract_orders_years_by_period_end_not_column():
    answer = {
        "tables": [
            _table(
                columns=[
                    {"period_label": "FY24", "period_end": "2024-03-31", "is_stub": False},
                    {"period_label": "FY25", "period_end": "2025-03-31", "is_stub": False},
                    {"period_label": "FY26", "period_end": "2026-03-31", "is_stub": False},
                ],
                rows=[{"line": "revenue_from_operations", "values": ["1000", "1200", "1500"]}],
            )
        ]
    }
    data = make_pdf(["cover", RESTATED_PL])
    figures = extract_figures(ScriptedClaude(answer), data, [2])
    by_year = {f.period_end: f.amount for f in figures}
    assert by_year[date(2026, 3, 31)] == Decimal("1500") * Decimal("10000000")
    assert by_year[date(2024, 3, 31)] == Decimal("1000") * Decimal("10000000")


def test_stub_period_is_marked():
    answer = {
        "tables": [
            _table(
                columns=[
                    {"period_label": "FY26", "period_end": "2026-03-31", "is_stub": False},
                    {"period_label": "Apr-Jun 26", "period_end": "2026-06-30", "is_stub": True},
                ],
                rows=[{"line": "revenue_from_operations", "values": ["1500", "400"]}],
            )
        ]
    }
    data = make_pdf(["cover", RESTATED_PL])
    figures = extract_figures(ScriptedClaude(answer), data, [2])
    stub = [f for f in figures if f.is_stub]
    assert len(stub) == 1
    assert stub[0].period_end == date(2026, 6, 30)


def test_extract_ignores_tables_off_the_selected_pages():
    answer = {
        "tables": [
            _table(
                columns=[{"period_label": "FY26", "period_end": "2026-03-31", "is_stub": False}],
                rows=[{"line": "revenue_from_operations", "values": ["1500"]}],
                page=99,
            )
        ]
    }
    data = make_pdf(["cover", RESTATED_PL])
    assert extract_figures(ScriptedClaude(answer), data, [2]) == []


def test_extract_sends_only_the_selected_pages_with_schema():
    claude = ScriptedClaude({"tables": []})
    data = make_pdf(["cover", RESTATED_PL, "risk"])
    extract_figures(claude, data, [2])
    purpose, schema, kwargs = claude.calls[0]
    assert purpose
    assert schema.get("additionalProperties") is False
    assert "messages" in kwargs
