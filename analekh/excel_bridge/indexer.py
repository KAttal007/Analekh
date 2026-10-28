"""Find models in watched folders, extract identification hints (design doc 13.1-13.2).

Runs on analyst's machine. Reads .xlsx/.xlsm with openpyxl (macros never executed); collects hidden
tag, header and cover text, modified time, fingerprint; sends only those hints to server. Workbooks
stay on user's machine (section 23).
"""

import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

from openpyxl import Workbook, load_workbook

from analekh.discovery import WorkbookHints
from analekh.excel_bridge import live
from analekh.workbook.fingerprint import fingerprint
from analekh.workbook.tags import read_tag

EXTENSIONS = {".xlsx", ".xlsm"}
SCAN_ROWS, SCAN_COLS, SCAN_SHEETS = 30, 10, 3


def iter_workbooks(folders: list[Path]) -> Iterator[Path]:
    for folder in folders:
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            if (
                path.suffix.lower() in EXTENSIONS and not path.name.startswith(("~$", "."))  # Excel lock files, our own temp files
            ):
                yield path


def _load(path: Path) -> Workbook:
    return load_workbook(path, read_only=False, keep_vba=path.suffix.lower() == ".xlsm", data_only=True)


def _load_even_if_open(path: Path) -> Workbook:
    """Read workbook; if another program holds it, read a copy.

    First a plain copy of saved file; if Windows refuses that too (Excel often holds files
    exclusively), ask Excel itself for a copy of the open workbook (includes unsaved edits). Nothing
    written back to original.
    """
    try:
        return _load(path)
    except PermissionError:
        pass
    with tempfile.TemporaryDirectory(prefix="analekh-") as tmp:
        copy = Path(tmp) / path.name
        try:
            shutil.copyfile(path, copy)
        except PermissionError:
            if not live.save_copy(path, copy):
                raise
        return _load(copy)


def hints_for(path: Path) -> WorkbookHints:
    wb = _load_even_if_open(path)
    tag = read_tag(wb)
    text: list[str] = []
    for ws in wb.worksheets[:SCAN_SHEETS]:
        for row in ws.iter_rows(min_row=1, max_row=SCAN_ROWS, max_col=SCAN_COLS):
            for c in row:
                if isinstance(c.value, str) and 2 <= len(c.value.strip()) <= 120:
                    text.append(c.value.strip())
    return WorkbookHints(
        path=str(path),
        tag_model_id=str(tag.model_id) if tag else None,
        tag_symbol=tag.symbol if tag else None,
        text=text[:400],
        modified=path.stat().st_mtime,
        fingerprint=fingerprint(wb),
    )


def scan(folders: list[Path], skipped: list[tuple[Path, str]] | None = None) -> list[WorkbookHints]:
    """Hints for every workbook found. A file that cannot be read is never dropped silently:
    when `skipped` is given, its path and the reason are appended to it."""
    out = []
    for path in iter_workbooks(folders):
        try:
            out.append(hints_for(path))
        except Exception as exc:  # noqa: BLE001 - one bad file must not stop the scan
            if skipped is not None:
                skipped.append((path, f"{type(exc).__name__}: {exc}"))
    return out
