"""Headless recalculation (design doc 15.1 step 5, 16.5).

- ``evaluate``: computes every formula with ``formulas`` library, returns values; runs Checks
  before a template is activated or built model saved.
- ``recalc_file``: round-trips through headless LibreOffice so saved file carries fresh cached
  values. LibreOffice runs in own ``recalc`` container (RECALC_URL), not application image; see
  ``recalc_file`` for retry and fallback rules. Desktop Excel (xlwings bridge) recalculates
  natively instead.
"""

import io
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import warnings
from pathlib import Path
from typing import Any

import httpx

from analekh.config import Settings, get_settings
from analekh.workbook.reader import excel_kind, has_macros

log = logging.getLogger(__name__)

_ZIP_MAGIC = b"PK\x03\x04"  # an .xlsx or .xlsm is a zip file
# Written into each local run's fresh profile: macros are never executed (rule 7); the VBA project
_PROFILE_SETTINGS = """<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" \
xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Office.Common/Security/Scripting">\
<prop oor:name="DisableMacrosExecution" oor:op="fuse"><value>true</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Security/Scripting">\
<prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>
<item oor:path="/org.openoffice.Office.Calc/Filter/Import/VBA">\
<prop oor:name="Load" oor:op="fuse"><value>true</value></prop></item>
<item oor:path="/org.openoffice.Office.Calc/Filter/Import/VBA">\
<prop oor:name="Executable" oor:op="fuse"><value>false</value></prop></item>
<item oor:path="/org.openoffice.Office.Calc/Filter/Import/VBA">\
<prop oor:name="Save" oor:op="fuse"><value>true</value></prop></item>
</oor:items>
"""
_transport: httpx.BaseTransport | None = None

_KEY = re.compile(r"^'?\[(?P<book>[^\]]+)\](?P<sheet>[^!]+?)'?!(?P<ref>[A-Z]+\d+(?::[A-Z]+\d+)?)$")


def evaluate(workbook: bytes) -> dict[tuple[str, str], Any]:
    """{(sheet, "A1"): value} for every cell the formulas model knows. Sheet names upper-case."""
    os.environ.setdefault("TQDM_DISABLE", "1")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        import formulas

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "book.xlsx"
        path.write_bytes(workbook)
        model = formulas.ExcelModel().loads(str(path)).finish()
        solution = model.calculate()
    values: dict[tuple[str, str], Any] = {}
    for key, ranges in solution.items():
        m = _KEY.match(str(key))
        if not m or ":" in m.group("ref"):
            continue
        raw = getattr(ranges, "value", ranges)
        try:
            value = raw[0][0]
        except (TypeError, IndexError):
            value = raw
        values[(m.group("sheet").upper(), m.group("ref"))] = _plain(value)
    return values


def _plain(value: Any) -> Any:
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, AttributeError):
            return value
    return value


def lookup(values: dict[tuple[str, str], Any], sheet: str, cell: str) -> Any:
    return values.get((sheet.upper(), cell.replace("$", "").upper()))


class RecalcUnavailable(Exception):
    """The workbook could not be recalculated right now. Nothing was converted, so the caller
    must save nothing; the same request can be tried again later. The message never holds the
    service token."""


class _Retry(Exception):
    """A failure worth one more try: the service was down, restarting, slow to answer or busy."""


class RecalcCannotCompute(Exception):
    """LibreOffice converted workbook but couldn't compute some cells: they call a function it
    lacks, e.g. analyst's VBA (macros never run, rule 7). Saving would replace analyst's values with
    """

    def __init__(self, cells: list[str]) -> None:
        self.cells = cells
        super().__init__(f"{len(cells)} cell(s) could not be computed")


def recalc_file(workbook: bytes, reference: bytes | None = None) -> bytes:
    """Workbook with fresh cached values, or RecalcCannotCompute when cells can't be computed by
    LibreOffice. ``reference`` = version the changes were made on: a cell already #NAME? there is
    analyst's own, doesn't count.

    See ``_convert`` for conversion, retry and fallback.
    """
    converted = _convert(workbook)
    if converted is not workbook:  # unchanged means no LibreOffice ran: nothing to check
        cells = _uncomputable(converted, reference)
        if cells:
            log.error("recalculation left %d cell(s) as #NAME?: %s", len(cells), cells[:10])
            raise RecalcCannotCompute(cells)
    return converted


def _uncomputable(converted: bytes, reference: bytes | None) -> list[str]:
    """Cells that are #NAME? after conversion and were not #NAME? in the reference version."""
    before = _name_errors(reference) if reference is not None else set()
    return sorted(c for c in _name_errors(converted) if c not in before)


def _name_errors(data: bytes) -> set[str]:
    from openpyxl import load_workbook

    found: set[str] = set()
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    if cell.value == "#NAME?":
                        found.add(f"{ws.title}!{cell.coordinate}")
    finally:
        wb.close()
    return found


def _convert(workbook: bytes) -> bytes:
    """Workbook through LibreOffice.

    - RECALC_URL set: `recalc` service converts (one retry on connection failure, read timeout or
    busy
      503). Still unavailable: RECALC_FALLBACK=local converts with local LibreOffice; default
      ("fail") raises RecalcUnavailable.
    - RECALC_URL empty: local LibreOffice if installed, else input unchanged.
    """
    s = get_settings()
    if not s.recalc_url:
        converted = _local(workbook, s.recalc_timeout_seconds)
        return workbook if converted is None else _kept_macros(workbook, converted)
    try:
        return _kept_macros(workbook, _remote(workbook, s))
    except RecalcUnavailable as unavailable:
        if s.recalc_fallback != "local":
            raise
        log.warning("recalc service unavailable (%s): trying a local LibreOffice", unavailable)
        try:
            converted = _local(workbook, s.recalc_timeout_seconds)
        except (subprocess.SubprocessError, OSError) as err:
            raise RecalcUnavailable(f"{unavailable}; local LibreOffice failed too") from err
        if converted is None:
            raise RecalcUnavailable(f"{unavailable}; no local LibreOffice") from None
        return _kept_macros(workbook, converted)


def _kept_macros(source: bytes, converted: bytes) -> bytes:
    """The converted workbook, or RecalcUnavailable when an .xlsm lost its VBA project on the way:
    a version without the analyst's macros is never saved (rule 7: VBA kept, never run)."""
    if has_macros(source) and not has_macros(converted):
        log.error("recalculation dropped the VBA project of an .xlsm")
        raise RecalcUnavailable("recalculation dropped the workbook's macros")
    return converted


def _remote(workbook: bytes, s: Settings) -> bytes:
    attempts = 1 + max(s.recalc_retries, 0)
    delay = s.recalc_retry_delay_seconds
    for attempt in range(1, attempts + 1):
        try:
            return _post(workbook, s)
        except _Retry as retry:
            if attempt == attempts:
                raise RecalcUnavailable(f"recalc service unavailable: {retry}") from None
            log.warning("recalc service: %s; retrying in %s s", retry, delay)
            time.sleep(delay)
    raise AssertionError("unreachable")  # the loop returns or raises on its last attempt


def _post(workbook: bytes, s: Settings) -> bytes:
    url = s.recalc_url.rstrip("/") + "/recalc"
    headers = {"X-Recalc-Token": s.recalc_token, "Content-Type": excel_kind(workbook)[1]}
    try:
        with httpx.Client(transport=_transport, timeout=s.recalc_timeout_seconds + 15) as client:
            res = client.post(url, content=workbook, headers=headers)
    except httpx.TransportError as err:  # refused, reset, timed out, name not found
        raise _Retry(type(err).__name__) from None
    if res.status_code == 200:
        if not res.content.startswith(_ZIP_MAGIC):
            log.error("recalc service answered 200 with a body that is not an xlsx")
            raise RecalcUnavailable("recalc service returned something that is not a workbook")
        return res.content
    code = _error_code(res)
    if res.status_code == 503:
        raise _Retry(f"busy ({code})")
    log.error("recalc service answered HTTP %d %s", res.status_code, code)
    raise RecalcUnavailable(f"recalc service answered HTTP {res.status_code} ({code})")


def _error_code(res: httpx.Response) -> str:
    try:
        return str(res.json().get("code", "?"))[:40]
    except (ValueError, AttributeError):
        return "?"


def _local(workbook: bytes, timeout: float) -> bytes | None:
    """Round-trip through a LibreOffice on this machine; None when it is not installed."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice is None:
        return None
    suffix = excel_kind(workbook)[0]
    convert_to = "xlsm:Calc MS Excel 2007 VBA XML" if suffix == ".xlsm" else "xlsx"
    with tempfile.TemporaryDirectory() as tmp:
        profile = Path(tmp) / "profile"
        (profile / "user").mkdir(parents=True)
        (profile / "user" / "registrymodifications.xcu").write_text(_PROFILE_SETTINGS, encoding="utf-8")
        src = Path(tmp) / f"in{suffix}"
        src.write_bytes(workbook)
        out_dir = Path(tmp) / "out"
        subprocess.run(
            [
                soffice,
                "--headless",
                "--norestore",
                f"-env:UserInstallation={profile.as_uri()}",
                "--calc",
                "--convert-to",
                convert_to,
                "--outdir",
                str(out_dir),
                str(src),
            ],
            check=True,
            timeout=timeout,
            capture_output=True,
        )
        return (out_dir / src.name).read_bytes()
