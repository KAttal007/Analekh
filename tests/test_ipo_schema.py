"""IPO offer tables: keys, checks and exact money (plan Task 1)."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from analekh.db.models import IpoDocument, IpoFinancial, IpoIssue


def _document(db, stage: str = "rhp", status: str = "new", sha: str = "a" * 64, sebi: str = "105274"):
    issue = IpoIssue(stem="jio platforms", name="Jio Platforms Limited")
    db.add(issue)
    db.flush()
    doc = IpoDocument(
        issue_id=issue.id,
        stage=stage,
        sebi_id=sebi,
        entry_url="https://www.sebi.gov.in/filings/public-issues/oct-2026/x_105274.html",
        pdf_url="https://www.sebi.gov.in/sebi_data/attachdocs/oct-2026/1.pdf",
        file_sha256=sha,
        storage_key="ipo/x.pdf",
        filed_on=date(2026, 10, 15),
        status=status,
    )
    db.add(doc)
    db.flush()
    return doc


def _figure(doc, **over) -> IpoFinancial:
    base = dict(
        document_id=doc.id,
        basis="consolidated",
        period_end=date(2026, 3, 31),
        period_label="FY26",
        is_stub=False,
        line="revenue_from_operations",
        amount=Decimal("1234.5678"),
        unit="INR",
        page=120,
    )
    base.update(over)
    return IpoFinancial(**base)


def test_unique_figure_per_document_basis_period_line(db):
    doc = _document(db)
    db.add(_figure(doc))
    db.flush()
    db.add(_figure(doc, amount=Decimal("1")))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_stage_and_status_checks(db):
    with pytest.raises(IntegrityError):
        _document(db, stage="drhp")
        db.flush()
    db.rollback()
    with pytest.raises(IntegrityError):
        _document(db, status="bogus", sha="b" * 64)
        db.flush()
    db.rollback()


def test_basis_and_unit_checks(db):
    doc = _document(db, sha="c" * 64)
    with pytest.raises(IntegrityError):
        db.add(_figure(doc, basis="group"))
        db.flush()
    db.rollback()
    doc = _document(db, sha="d" * 64)
    with pytest.raises(IntegrityError):
        db.add(_figure(doc, unit="INR lakh"))
        db.flush()
    db.rollback()


def test_amount_is_decimal(db):
    doc = _document(db, sha="e" * 64)
    fig = _figure(doc)
    db.add(fig)
    db.flush()
    db.expire_all()
    assert db.get(IpoFinancial, fig.id).amount == Decimal("1234.5678")
    assert isinstance(db.get(IpoFinancial, fig.id).amount, Decimal)
