"""Apply approved change items (design doc 16.4).

Headless path: openpyxl writes, then LibreOffice recalculates. xlwings path (native Excel
recalculation, formatting kept) lives in analekh.excel_bridge, same item list. Original workbook
never overwritten: caller stores result as new model_version. Macros kept (keep_vba), never
executed.
"""

import io
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from analekh.workbook.reader import load
from analekh.workbook.recalc import recalc_file

__all__ = ["ApprovedItem", "apply_headless", "coerce", "recalc_file"]


@dataclass
class ApprovedItem:
    kind: str
    sheet: str
    cell: str
    value: str | None  # final value (edited or as proposed)
    formula: str | None = None


def coerce(value: str | None) -> object:
    if value is None:
        return None
    try:
        d = Decimal(value)
    except InvalidOperation:
        return value
    return int(d) if d == d.to_integral_value() and abs(d) < 10**15 else float(d)


def apply_headless(workbook: bytes, items: list[ApprovedItem]) -> bytes:
    wb = load(workbook)
    for item in items:
        ws = wb[item.sheet]
        ws[item.cell].value = item.formula if item.formula else coerce(item.value)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
