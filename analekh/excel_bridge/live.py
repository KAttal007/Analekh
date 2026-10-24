"""Talk to a workbook that is open in desktop Excel (xlwings; needs Excel on this machine)."""

from pathlib import Path
from typing import Any


def _same_file(book: Any, path: Path) -> bool:  # pragma: no cover - needs desktop Excel
    full = str(book.fullname)
    if full.lower().startswith(("http://", "https://")):
        # OneDrive-synced workbooks report a web address: fall back to the file name.
        return str(book.name).lower() == path.name.lower()
    return Path(full).resolve() == path.resolve()


def find_open_book(path: Path) -> Any | None:  # pragma: no cover - needs desktop Excel
    """The xlwings book for `path` if some running Excel has it open, else None."""
    try:
        import xlwings as xw
    except ImportError:
        return None
    try:
        for app in xw.apps:
            for book in app.books:
                if _same_file(book, path):
                    return book
    except Exception:  # noqa: BLE001 - Excel busy or closing: treat as not open
        return None
    return None


def save_copy(path: Path, dest: Path) -> bool:
    """Ask Excel for a copy of the open workbook, including unsaved edits. The open workbook
    is not changed or saved. False if the workbook is not open in Excel."""
    book = find_open_book(path)
    if book is None:
        return False
    book.api.SaveCopyAs(str(dest))
    return True
