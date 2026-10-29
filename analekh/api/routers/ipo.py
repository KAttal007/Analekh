"""IPO coverage: issues, restated figures, drafts and the NSE symbol (plan Task 8). Every route
needs a signed-in user (registered with get_user in main.py; rule 9)."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from analekh.api import schemas
from analekh.api.deps import DB, User
from analekh.db.models import Company, IpoDocument, IpoDraft, IpoFinancial, IpoIssue
from analekh.genai.client import Claude
from analekh.ipo.coverage import SECTIONS, NoOfferDocument, generate
from analekh.ipo.symbols import valid_symbol
from analekh.ipo.versions import current_document, restatements

router = APIRouter(prefix="/ipo", tags=["ipo"])
BASES = ("consolidated", "standalone")


def _issue_or_404(db: DB, issue_id: int) -> IpoIssue:
    issue = db.get(IpoIssue, issue_id)
    if issue is None:
        raise HTTPException(404, "issue not found")
    return issue


def _money(value: Any) -> str:
    return format(value, "f")


@router.get("/issues")
def list_issues(db: DB) -> list[dict[str, Any]]:
    """Newest filing first."""
    rows: list[dict[str, Any]] = []
    for issue in db.scalars(select(IpoIssue)).all():
        docs = db.scalars(select(IpoDocument).where(IpoDocument.issue_id == issue.id)).all()
        current = current_document(db, issue.id)
        filed = max((d.filed_on for d in docs if d.filed_on), default=None)
        rows.append(
            {
                "id": issue.id,
                "name": issue.name,
                "stages": sorted({d.stage for d in docs}),
                "current_stage": current.stage if current else None,
                "status": current.status if current else "no document",
                "filed_on": filed.isoformat() if filed else None,
                "company_symbol": issue.symbol,
                "_sort": filed or date.min,
            }
        )
    rows.sort(key=lambda r: (r["_sort"], r["id"]), reverse=True)
    for row in rows:
        del row["_sort"]
    return rows


@router.get("/issues/{issue_id}")
def issue_detail(issue_id: int, db: DB) -> dict[str, Any]:
    issue = _issue_or_404(db, issue_id)
    current = current_document(db, issue.id)
    financials: dict[str, list[dict[str, Any]]] = {basis: [] for basis in BASES}
    terms = None
    if current is not None:
        terms = (current.meta or {}).get("terms")
        for row in db.scalars(select(IpoFinancial).where(IpoFinancial.document_id == current.id).order_by(IpoFinancial.period_end, IpoFinancial.line)).all():
            financials[row.basis].append(
                {
                    "period_label": row.period_label,
                    "period_end": row.period_end.isoformat(),
                    "is_stub": row.is_stub,
                    "line": row.line,
                    "amount": _money(row.amount),
                    "unit": row.unit,
                    "page": row.page,
                    "flagged": row.flagged,
                }
            )
    return {
        "id": issue.id,
        "name": issue.name,
        "current_stage": current.stage if current else None,
        "financials": financials,
        "restatements": [
            {
                "basis": r.basis,
                "period_end": r.period_end.isoformat(),
                "line": r.line,
                "old": _money(r.old),
                "new": _money(r.new),
            }
            for r in restatements(db, issue.id)
        ],
        "terms": terms,
    }


def _draft_out(draft: IpoDraft) -> dict[str, Any]:
    sections = draft.sections
    return {
        "draft_id": draft.id,
        "stage": sections.get("stage"),
        "sections": {key: sections.get(key) for key in SECTIONS},
        "rating": sections.get("rating"),
        "rationale": sections.get("rationale"),
    }


@router.post("/issues/{issue_id}/coverage")
def create_coverage(issue_id: int, db: DB, user: User) -> dict[str, Any]:
    _issue_or_404(db, issue_id)
    try:
        draft = generate(db, Claude(db), issue_id, user)
    except NoOfferDocument as exc:
        raise HTTPException(409, str(exc)) from exc
    return _draft_out(draft)


@router.get("/issues/{issue_id}/coverage")
def latest_coverage(issue_id: int, db: DB) -> dict[str, Any]:
    _issue_or_404(db, issue_id)
    draft = db.scalars(select(IpoDraft).where(IpoDraft.issue_id == issue_id).order_by(IpoDraft.id.desc()).limit(1)).first()
    if draft is None:
        raise HTTPException(404, "no coverage draft yet")
    return _draft_out(draft)


@router.post("/issues/{issue_id}/symbol")
def set_symbol(issue_id: int, body: schemas.IpoSymbolIn, db: DB) -> dict[str, Any]:
    """The analyst's NSE symbol for the issue (entered once bids open). Linked to a company when
    that symbol is already listed."""
    issue = _issue_or_404(db, issue_id)
    symbol = body.symbol.strip().upper()
    if not valid_symbol(symbol):
        raise HTTPException(422, "symbol: 1 to 20 capitals, digits, & or -")
    company = db.scalar(select(Company).where(Company.nse_symbol == symbol))
    issue.symbol = symbol
    issue.company_id = company.id if company else None
    db.flush()
    return {"id": issue.id, "symbol": issue.symbol, "company_id": issue.company_id}
