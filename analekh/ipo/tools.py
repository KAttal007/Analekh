"""Tools for the IPO coverage report. Each reads only the issue's current offer document (the
Prospectus if filed, else the RHP), and every result names its source (document id and page).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from analekh.db.models import IpoChunk, IpoDocument, IpoFinancial
from analekh.genai.tools import TOOL_DEFS, ToolExecutor
from analekh.ipo.versions import current_document

BASES = ("consolidated", "standalone")
MAX_LINES = 30
MAX_HITS = 10


def _tool(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }


_CALC = next(t for t in TOOL_DEFS if t["name"] == "calc")

IPO_TOOL_DEFS: list[dict[str, Any]] = [
    _CALC,
    _tool(
        "get_ipo_financials",
        "Restated figures from the offer document (full rupees, or rupees per share for EPS), with source.",
        {
            "basis": {"type": "string", "enum": list(BASES)},
            "lines": {"type": "array", "items": {"type": "string"}, "maxItems": MAX_LINES},
        },
        ["basis", "lines"],
    ),
    _tool(
        "get_offer_terms",
        "Price band, face value, issue amounts, post-issue shares and listed peers from the offer document.",
        {},
        [],
    ),
    _tool(
        "search_offer_text",
        "Full-text search over the offer document's pages. Returns page, text and source.",
        {
            "query": {"type": "string"},
            "k": {"type": "integer", "minimum": 1, "maximum": MAX_HITS},
        },
        ["query", "k"],
    ),
]


class IpoToolExecutor(ToolExecutor):
    def __init__(self, session: Session, issue_id: int) -> None:
        super().__init__(session)
        self.issue_id = issue_id

    def _document(self) -> IpoDocument | None:
        return current_document(self.session, self.issue_id)

    def _t_get_ipo_financials(self, basis: str, lines: list[str]) -> list[dict[str, Any]]:
        if basis not in BASES:
            raise ValueError(f"unknown basis {basis!r}")
        doc = self._document()
        if doc is None or not lines:
            return []
        rows = self.session.scalars(
            select(IpoFinancial)
            .where(
                IpoFinancial.document_id == doc.id,
                IpoFinancial.basis == basis,
                IpoFinancial.line.in_(lines[:MAX_LINES]),
            )
            .order_by(IpoFinancial.period_end, IpoFinancial.line)
        ).all()
        return [
            {
                "period_label": r.period_label,
                "period_end": r.period_end.isoformat(),
                "is_stub": r.is_stub,
                "line": r.line,
                "amount": format(r.amount, "f"),
                "unit": r.unit,
                "flagged": r.flagged,
                "source": f"ipo_doc:{doc.id} page:{r.page}",
            }
            for r in rows
        ]

    def _t_get_offer_terms(self) -> dict[str, Any]:
        doc = self._document()
        if doc is None:
            return {}
        terms = dict((doc.meta or {}).get("terms") or {})
        if not terms:
            return {}
        terms["source"] = f"ipo_doc:{doc.id} page:{terms.get('page')}"
        return terms

    def _t_search_offer_text(self, query: str, k: int) -> list[dict[str, Any]]:
        doc = self._document()
        if doc is None or not query.strip():
            return []
        k = max(1, min(int(k), MAX_HITS))
        q = func.plainto_tsquery("english", query)
        rows = self.session.scalars(select(IpoChunk).where(IpoChunk.document_id == doc.id, IpoChunk.tsv.op("@@")(q)).order_by(func.ts_rank(IpoChunk.tsv, q).desc(), IpoChunk.page).limit(k)).all()
        return [{"page": r.page, "text": r.text, "source": f"ipo_doc:{doc.id} page:{r.page}"} for r in rows]
