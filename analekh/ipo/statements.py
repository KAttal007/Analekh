"""Locate and extract restated statements from an offer document (RHP or Prospectus).

Money: every amount is a Decimal, converted to full rupees with the table's stated unit. EPS is
kept in rupees per share. Figures that disagree with each other are flagged, never stored clean.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from analekh.db.models import IpoDocument, IpoFinancial
from analekh.docs.pdf import PageText, read_pages, subset
from analekh.genai.client import Claude

LINES: tuple[str, ...] = (
    "revenue_from_operations",
    "other_income",
    "total_income",
    "total_expenses",
    "finance_costs",
    "depreciation",
    "profit_before_tax",
    "tax_expense",
    "profit_after_tax",
    "eps_basic",
    "eps_diluted",
    "total_assets",
    "total_equity",
    "total_borrowings",
    "cash_from_operations",
    "cash_from_investing",
    "cash_from_financing",
)
EPS_LINES = frozenset({"eps_basic", "eps_diluted"})
UNIT_FACTORS: dict[str, Decimal] = {
    "INR": Decimal(1),
    "INR thousand": Decimal(10) ** 3,
    "INR lakh": Decimal(10) ** 5,
    "INR million": Decimal(10) ** 6,
    "INR crore": Decimal(10) ** 7,
    "INR billion": Decimal(10) ** 9,
}
MAX_STATEMENT_PAGES = 40
TOLERANCE = Decimal("0.01")
_STATEMENT_RE = re.compile(
    r"restated (consolidated |standalone )?(financial information|statement of "
    r"(profit and loss|assets and liabilities|cash flows))|summary of (restated )?financial information",
    re.IGNORECASE,
)
_DASHES = {"-", "—", "–"}
_BASES = ("consolidated", "standalone")

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tables"],
    "properties": {
        "tables": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["basis", "unit", "page", "columns", "rows"],
                "properties": {
                    "basis": {"type": "string", "enum": list(_BASES)},
                    "unit": {"type": "string"},
                    "page": {"type": "integer"},
                    "columns": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["period_label", "period_end", "is_stub"],
                            "properties": {
                                "period_label": {"type": "string"},
                                "period_end": {"type": "string", "description": "YYYY-MM-DD"},
                                "is_stub": {"type": "boolean"},
                            },
                        },
                    },
                    "rows": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["line", "values"],
                            "properties": {
                                "line": {"type": "string", "enum": list(LINES)},
                                "values": {"type": "array", "items": {"type": ["string", "null"]}},
                            },
                        },
                    },
                },
            },
        }
    },
}

_PROMPT = (
    "The pages below are restated financial statements from an Indian offer document. For each "
    "table, return its basis (consolidated or standalone), the unit stated in its heading, the "
    "PDF page it is on, its columns (period label, period end date YYYY-MM-DD, stub flag) and the "
    "rows that match the allowed line names. Numbers are strings exactly as printed. A bracket "
    "means negative, a dash means nil. Do not compute anything. Do not guess: leave a value null "
    "when it is not printed.\n\n"
)


@dataclass
class ExtractedFigure:
    basis: str
    period_end: date
    period_label: str
    is_stub: bool
    line: str
    amount: Decimal
    unit: str
    page: int
    flagged: bool = False


def select_statement_pages(pages: list[PageText]) -> list[int]:
    """1-based page numbers that carry restated statements, the most table-like first (at most
    MAX_STATEMENT_PAGES), returned in page order."""
    matches = [p for p in pages if _STATEMENT_RE.search(p.text)]
    best = sorted(matches, key=lambda p: p.numeric_density, reverse=True)[:MAX_STATEMENT_PAGES]
    return sorted(p.number for p in best)


def to_rupees(raw: str, unit_label: str) -> Decimal:
    """A printed amount in its table's unit, as full rupees. Brackets are negative; a dash is 0."""
    factor = UNIT_FACTORS.get(unit_label)
    if factor is None:
        raise ValueError(f"unknown unit: {unit_label!r}")
    text = raw.strip()
    if text in _DASHES:
        return Decimal(0)
    negative = text.startswith("(") and text.endswith(")")
    core = text.strip("()").replace(",", "").strip()
    try:
        value = Decimal(core)
    except InvalidOperation as exc:
        raise ValueError(f"not a number: {raw!r}") from exc
    if not value.is_finite():
        raise ValueError(f"not a number: {raw!r}")
    if negative:
        value = -value
    return value * factor


def _figures_from(answer: dict[str, Any], allowed_pages: set[int]) -> list[ExtractedFigure]:
    out: list[ExtractedFigure] = []
    for table in answer.get("tables", []):
        page = int(table.get("page", 0))
        basis = table.get("basis")
        if page not in allowed_pages or basis not in _BASES:
            continue
        try:
            columns = [
                (
                    date.fromisoformat(col["period_end"]),
                    str(col["period_label"]),
                    bool(col["is_stub"]),
                )
                for col in table["columns"]
            ]
        except (KeyError, TypeError, ValueError):
            continue
        for row in table.get("rows", []):
            line = row.get("line")
            values = row.get("values") or []
            if line not in LINES or len(values) != len(columns):
                continue
            for (period_end, label, stub), raw in zip(columns, values, strict=True):
                if raw is None or not str(raw).strip():
                    continue
                try:
                    if line in EPS_LINES:
                        amount, unit = to_rupees(str(raw), "INR"), "INR/share"
                    else:
                        amount, unit = to_rupees(str(raw), table["unit"]), "INR"
                except ValueError:
                    continue
                out.append(
                    ExtractedFigure(
                        basis=basis,
                        period_end=period_end,
                        period_label=label,
                        is_stub=stub,
                        line=line,
                        amount=amount,
                        unit=unit,
                        page=page,
                    )
                )
    return out


def extract_figures(claude: Claude, pdf: bytes, page_numbers: list[int]) -> list[ExtractedFigure]:
    if not page_numbers:
        return []
    pages = read_pages(subset(pdf, page_numbers))
    body = "\n".join(f"=== PDF page {page_numbers[p.number - 1]} ===\n{p.text}" for p in pages)
    answer = claude.create_json(
        "ipo_statements",
        _SCHEMA,
        messages=[{"role": "user", "content": _PROMPT + body}],
    )
    return _figures_from(answer, set(page_numbers))


def _one(group: list[ExtractedFigure]) -> ExtractedFigure | None:
    return group[0] if group else None


def check_figures(figures: list[ExtractedFigure]) -> list[str]:
    """Cross-checks inside each (basis, period). Returns problems and marks the figures involved."""
    problems: list[str] = []
    by_key: dict[tuple[str, date], dict[str, list[ExtractedFigure]]] = {}
    for f in figures:
        by_key.setdefault((f.basis, f.period_end), {}).setdefault(f.line, []).append(f)

    def _close(total: Decimal, part: Decimal) -> bool:
        return abs(total - part) <= max(abs(total) * TOLERANCE, Decimal(1))

    for (basis, period_end), lines in by_key.items():
        where = f"{basis} {period_end.isoformat()}"
        ti, te, pbt = (_one(lines.get(k, [])) for k in ("total_income", "total_expenses", "profit_before_tax"))
        if ti and te and pbt and not _close(pbt.amount, ti.amount - te.amount):
            problems.append(f"{where}: total income less total expenses differs from profit before tax")
            for f in (ti, te, pbt):
                f.flagged = True
        tax, pat = (_one(lines.get(k, [])) for k in ("tax_expense", "profit_after_tax"))
        if pbt and tax and pat and not _close(pat.amount, pbt.amount - tax.amount):
            problems.append(f"{where}: profit before tax less tax differs from profit after tax")
            for f in (pbt, tax, pat):
                f.flagged = True

    groups: dict[tuple[str, date, str], list[ExtractedFigure]] = {}
    for f in figures:
        groups.setdefault((f.basis, f.period_end, f.line), []).append(f)
    for (basis, period_end, line), dupes in groups.items():
        for i, a in enumerate(dupes):
            for b in dupes[i + 1 :]:
                if _is_power_of_ten_apart(a.amount, b.amount):
                    problems.append(f"{basis} {period_end.isoformat()} {line}: same figure, units differ by a power of ten")
                    a.flagged = b.flagged = True
    return problems


def _is_power_of_ten_apart(x: Decimal, y: Decimal) -> bool:
    x, y = abs(x), abs(y)
    if x == 0 or y == 0 or x == y:
        return False
    big, small = max(x, y), min(x, y)
    return any(big == small * (Decimal(10) ** k) for k in range(1, 13))


def store_figures(session: Session, document: IpoDocument, figures: list[ExtractedFigure]) -> None:
    """One row per (basis, period, line). If the same figure came out twice, the first is kept and
    flagged: a conflict is never stored clean."""
    kept: dict[tuple[str, date, str], ExtractedFigure] = {}
    conflict: set[tuple[str, date, str]] = set()
    for f in figures:
        key = (f.basis, f.period_end, f.line)
        if key in kept:
            conflict.add(key)
            kept[key].flagged = True
        else:
            kept[key] = f
    for key, f in kept.items():
        session.add(
            IpoFinancial(
                document_id=document.id,
                basis=f.basis,
                period_end=f.period_end,
                period_label=f.period_label,
                is_stub=f.is_stub,
                line=f.line,
                amount=f.amount,
                unit=f.unit,
                page=f.page,
                flagged=f.flagged or key in conflict,
            )
        )
    document.status = "flagged" if any(f.flagged for f in kept.values()) else "extracted"
    session.flush()
