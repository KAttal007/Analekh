"""Results history: every stored quarter's P&L lines for one company on one basis (design doc 19.1,
company page), newest last, with Excel export.

Same lines, derivations and exclusions as latest-quarter view (glance.py): company's own results
format, EBITDA left out for lenders and insurers, filings V11 suspects of wrong unit left out.
"""

import io
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import xlsxwriter
from sqlalchemy import select
from sqlalchemy.orm import Session

from analekh.db.models import Company, ReportedRatio
from analekh.facts import files_consolidated
from analekh.glance import (
    LINES,
    NOTES,
    ONLY_WHEN_NONZERO,
    Kind,
    _quarters,
    hidden_lines,
    quarter_label,
    quarter_value,
    raw_value,
    suspect_filings,
)
from analekh.interest import AVERAGE_NOTE, Ratios, balances, is_lender, ratios
from analekh.interest import KEYS as INTEREST_KEYS
from analekh.interest import LABELS as INTEREST_LABELS
from analekh.interest import NOTES as INTEREST_NOTES
from analekh.units import CRORE

MAX_QUARTERS = 28  # the history stored reaches back to March 2023


@dataclass
class HistoryLine:
    key: str
    label: str
    kind: Kind
    values: list[Decimal | None]  # one per quarter, oldest first
    note: str | None = None
    source: str | None = None  # lenders' ratios only: "calculated" (by us, from the filings) or "reported" (investor deck)


@dataclass
class History:
    consolidated: bool
    taxonomy: str
    quarter_ends: list[date] = field(default_factory=list)
    quarter_labels: list[str] = field(default_factory=list)
    lines: list[HistoryLine] = field(default_factory=list)


def history(session: Session, company: Company, consolidated: bool | None = None, quarters: int = 8) -> History:
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

    hidden = hidden_lines(company)
    for name, label, kind in LINES.get(taxonomy, LINES["indas"]):
        if name in hidden:
            continue
        values = [quarter_value(q, name, e) for e in ends]
        if all(v is None for v in values):
            continue
        if name in ONLY_WHEN_NONZERO and all(not v for v in values):
            continue
        if kind == "pct":
            values = [v.quantize(Decimal("0.1")) if v is not None else None for v in values]
        out.lines.append(HistoryLine(name.lstrip("="), label, kind, values, NOTES.get(name)))
    if is_lender(company):
        out.lines += _interest_lines(session, company, basis, q, ends)
        out.lines += _reported_lines(session, company, basis, ends)
    return out


def _interest_lines(session: Session, company: Company, basis: bool, q: dict, ends: list[date]) -> list[HistoryLine]:
    """NIM, yield, cost of borrowing and spread per quarter (interest.py); lines with no value in
    any quarter are left out."""
    parts = balances(session, [company.id], suspect_filings(session, [company.id])).get((company.id, basis), {})
    per_quarter = []
    for e in ends:
        hit = q.get("interest_income", {}).get(e) or q.get("interest_expense", {}).get(e)
        if hit is None:
            per_quarter.append(Ratios())
            continue
        income, expense = raw_value(q, "interest_income", e), raw_value(q, "interest_expense", e)
        revenue = raw_value(q, "revenue", e)
        per_quarter.append(ratios(income, expense, parts, hit[0], e, revenue).rounded())
    lines = []
    for key in INTEREST_KEYS:
        values = [r.get(key) for r in per_quarter]
        if all(v is None for v in values):
            continue
        note = f"{INTEREST_NOTES[key]}. {AVERAGE_NOTE}"
        lines.append(HistoryLine(key, INTEREST_LABELS[key], "pct", values, note, "calculated"))
    return lines


REPORTED_LINES = (
    ("nim", "nim_reported", "Net interest margin"),
    ("cof", "cof_reported", "Cost of funds"),
)
REPORTED_NOTE = (
    "As the company reports it in its investor presentation, not worked out by Analekh. It can differ from the calculated "
    "rows: companies define margin and funding differently. Where a deck gives only one basis, that figure is shown."
)


def _reported_lines(session: Session, company: Company, basis: bool, ends: list[date]) -> list[HistoryLine]:
    """What the company reports for itself (decks): its own basis first, then 'all', then the other."""
    got: dict[tuple[str, date], dict[str, Decimal]] = {}
    for row in session.execute(
        select(ReportedRatio.metric, ReportedRatio.period_end, ReportedRatio.basis, ReportedRatio.value).where(
            ReportedRatio.company_id == company.id, ReportedRatio.metric.in_(("nim", "cof")), ReportedRatio.period_end.in_(ends)
        )
    ):
        got.setdefault((row.metric, row.period_end), {})[row.basis] = row.value
    own, other = ("consolidated", "standalone") if basis else ("standalone", "consolidated")
    lines = []
    for metric, key, label in REPORTED_LINES:
        values = []
        for e in ends:
            by_basis = got.get((metric, e), {})
            values.append(next((by_basis[b] for b in (own, "all", other) if b in by_basis), None))
        if any(v is not None for v in values):
            lines.append(HistoryLine(key, label, "pct", values, REPORTED_NOTE, "reported"))
    return lines


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
    ws.write(0, 0, f"{company.name} ({company.nse_symbol})", wb.add_format({"bold": True, "size": 13}))
    ws.write(1, 0, f"{basis} quarterly results from the filed XBRL; amounts in INR crore")
    ws.write(3, 0, "Line", wb.add_format({"bold": True, "bottom": 1}))
    for c, label in enumerate(h.quarter_labels, start=1):
        ws.write(3, c, label, head)
    for r, line in enumerate(h.lines, start=4):
        label = f"{line.label} ({line.source})" if line.source else line.label
        ws.write(r, 0, label, bold if line.key in {"revenue", "pat"} else None)
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
