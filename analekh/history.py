"""Results history: every stored quarter's P&L lines for one company on one basis (design doc
19.1, company page), newest last, with an Excel export.

The same lines, derivations and exclusions as the latest-quarter view (glance.py): the company's
own results format, EBITDA left out for lenders and insurers, and filings V11 suspects of the
wrong unit left out.
"""

import io
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import xlsxwriter
from sqlalchemy.orm import Session

from analekh.db.models import Company
from analekh.facts import files_consolidated
from analekh.glance import (
    LINES,
    NOT_FOR_FINANCIALS,
    NOTES,
    ONLY_WHEN_NONZERO,
    Kind,
    _quarters,
    is_financial,
    quarter_label,
    quarter_value,
)
from analekh.units import CRORE

MAX_QUARTERS = 28  # the history stored reaches back to March 2023


@dataclass
class HistoryLine:
    key: str
    label: str
    kind: Kind
    values: list[Decimal | None]  # one per quarter, oldest first
    note: str | None = None


@dataclass
class History:
    consolidated: bool
    taxonomy: str
    quarter_ends: list[date] = field(default_factory=list)
    quarter_labels: list[str] = field(default_factory=list)
    lines: list[HistoryLine] = field(default_factory=list)


def history(
    session: Session, company: Company, consolidated: bool | None = None, quarters: int = 8
) -> History:
    basis = files_consolidated(session, company.id) if consolidated is None else consolidated
    taxonomy = company.results_taxonomy or "indas"
    out = History(consolidated=basis, taxonomy=taxonomy)
    q = _quarters(session, company.id, basis, taxonomy)
    ends = sorted(set(q.get("revenue", {})) | set(q.get("pat", {})))
    ends = ends[-max(1, min(quarters, MAX_QUARTERS)) :]
    if not ends:
        return out
    out.quarter_ends = ends
    out.quarter_labels = [quarter_label(e) for e in ends]

    financial = is_financial(company)
    for name, label, kind in LINES.get(taxonomy, LINES["indas"]):
        if name in NOT_FOR_FINANCIALS and financial:
            continue
        values = [quarter_value(q, name, e) for e in ends]
        if all(v is None for v in values):
            continue
        if name in ONLY_WHEN_NONZERO and all(not v for v in values):
            continue
        if kind == "pct":
            values = [v.quantize(Decimal("0.1")) if v is not None else None for v in values]
        out.lines.append(HistoryLine(name.lstrip("="), label, kind, values, NOTES.get(name)))
    return out


def to_xlsx(h: History, company: Company) -> bytes:
    """The history as a workbook: lines down, quarters across, amounts in INR crore."""
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    ws = wb.add_worksheet("Results")
    bold = wb.add_format({"bold": True})
    head = wb.add_format({"bold": True, "bottom": 1, "align": "right"})
    amount = wb.add_format({"num_format": "#,##0.00"})
    pct = wb.add_format({"num_format": '0.0"%"'})
    eps = wb.add_format({"num_format": "0.00"})
    basis = "Consolidated" if h.consolidated else "Standalone"
    ws.write(
        0, 0, f"{company.name} ({company.nse_symbol})", wb.add_format({"bold": True, "size": 13})
    )
    ws.write(1, 0, f"{basis} quarterly results from the filed XBRL; amounts in INR crore")
    ws.write(3, 0, "Line", wb.add_format({"bold": True, "bottom": 1}))
    for c, label in enumerate(h.quarter_labels, start=1):
        ws.write(3, c, label, head)
    for r, line in enumerate(h.lines, start=4):
        ws.write(r, 0, line.label, bold if line.key in {"revenue", "pat"} else None)
        for c, v in enumerate(line.values, start=1):
            if v is None:
                ws.write(r, c, "")
            elif line.kind == "inr":
                ws.write_number(r, c, float(v / CRORE), amount)
            elif line.kind == "pct":
                ws.write_number(r, c, float(v), pct)
            else:
                ws.write_number(r, c, float(v), eps)
    notes = [f"{line.label}: {line.note}" for line in h.lines if line.note]
    for i, note in enumerate(notes, start=len(h.lines) + 6):
        ws.write(i, 0, note)
    ws.set_column(0, 0, 36)
    ws.set_column(1, len(h.quarter_labels), 12)
    ws.freeze_panes(4, 1)
    wb.close()
    return buf.getvalue()
