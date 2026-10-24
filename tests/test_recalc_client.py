"""recalc_file with a recalc service configured: the request, the retry, the fallbacks and the
refusals. Replies are injected with httpx.MockTransport; nothing sleeps and no LibreOffice runs."""

import logging
import subprocess
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

import httpx
import pytest

from analekh.config import Settings
from analekh.workbook import recalc
from analekh.workbook.recalc import RecalcUnavailable, recalc_file

WB = b"PK\x03\x04workbook"
TOKEN = "tok-9f2c1d7a"
WB_M = b"PK\x03\x04workbook xl/vbaProject.bin"  # an .xlsm
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
XLSM = "application/vnd.ms-excel.sheet.macroEnabled.12"


def _book(macros: bool = False, **cells: object) -> bytes:
    """A real workbook with these cells on Sheet1 ("#NAME?" is stored as an error value). With
    `macros` the zip also lists a VBA project, which is what makes it an .xlsm here."""
    import io
    import zipfile

    from openpyxl import Workbook

    wb = Workbook()
    wb.active.title = "Sheet1"
    for address, value in cells.items():
        wb.active[address] = value
    out = io.BytesIO()
    wb.save(out)
    if macros:
        with zipfile.ZipFile(out, "a") as z:
            z.writestr("xl/vbaProject.bin", b"vba")
    return out.getvalue()


FRESH = _book(A1=1)
FRESH_M = _book(macros=True, A1=1)


@pytest.fixture(autouse=True)
def sleeps(monkeypatch) -> list[float]:
    slept: list[float] = []
    monkeypatch.setattr(recalc.time, "sleep", slept.append)
    return slept


@pytest.fixture
def configure(monkeypatch):
    """configure(**settings) installs settings that point at the service."""

    def _configure(**overrides) -> Settings:
        base = {"recalc_url": "http://recalc:8080", "recalc_token": TOKEN}
        settings = Settings(**{**base, **overrides})
        monkeypatch.setattr(recalc, "get_settings", lambda: settings)
        return settings

    return _configure


@pytest.fixture
def serve(monkeypatch):
    """serve(handler) answers every request with handler(request); returns the requests seen."""

    def _serve(handler) -> list[httpx.Request]:
        seen: list[httpx.Request] = []

        def wrapped(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return handler(request)

        monkeypatch.setattr(recalc, "_transport", httpx.MockTransport(wrapped))
        return seen

    return _serve


def _refused(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("refused")


def _answer(status: int, code: str):
    return lambda request: httpx.Response(status, json={"code": code})


def test_no_url_uses_local_and_passes_through_without_soffice(configure, monkeypatch):
    configure(recalc_url="")
    monkeypatch.setattr(recalc.shutil, "which", lambda name: None)
    assert recalc_file(WB) == WB


def test_no_url_converts_locally_when_soffice_is_installed(configure, monkeypatch):
    settings = configure(recalc_url="", recalc_timeout_seconds=42.0)
    given: list[tuple[bytes, float]] = []
    monkeypatch.setattr(recalc, "_local", lambda b, t: given.append((b, t)) or FRESH)
    assert recalc_file(WB) == FRESH
    assert given == [(WB, settings.recalc_timeout_seconds)]  # the limit comes from settings


def test_service_success_returns_body(configure, serve):
    configure()
    seen = serve(lambda request: httpx.Response(200, content=FRESH))
    assert recalc_file(WB) == FRESH
    assert len(seen) == 1
    assert seen[0].method == "POST"
    assert str(seen[0].url) == "http://recalc:8080/recalc"
    assert seen[0].content == WB


def test_token_sent_in_header_not_url(configure, serve):
    configure()
    seen = serve(lambda request: httpx.Response(200, content=FRESH))
    recalc_file(WB)
    assert seen[0].url.query == b""
    assert TOKEN not in str(seen[0].url)
    assert seen[0].headers["X-Recalc-Token"] == TOKEN


def test_client_waits_longer_than_the_service(configure, serve):
    configure(recalc_timeout_seconds=100.0)
    seen = serve(lambda request: httpx.Response(200, content=FRESH))
    recalc_file(WB)
    assert seen[0].extensions["timeout"]["read"] == 115.0  # the service's 504 arrives first


def test_connect_error_then_success_retries_once(configure, serve, sleeps):
    configure(recalc_retry_delay_seconds=2.0)
    replies = iter([_refused, lambda request: httpx.Response(200, content=FRESH)])
    seen = serve(lambda request: next(replies)(request))
    assert recalc_file(WB) == FRESH
    assert len(seen) == 2
    assert sleeps == [2.0]


def test_read_timeout_is_retried(configure, serve):
    configure()

    def timed_out(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    replies = iter([timed_out, lambda request: httpx.Response(200, content=FRESH)])
    seen = serve(lambda request: next(replies)(request))
    assert recalc_file(WB) == FRESH
    assert len(seen) == 2


def test_busy_503_retried_then_fail_raises(configure, serve, sleeps):
    configure()
    seen = serve(_answer(503, "busy"))
    with pytest.raises(RecalcUnavailable):
        recalc_file(WB)
    assert len(seen) == 2  # the first try and one retry
    assert sleeps == [2.0]


def test_down_for_good_raises_after_one_retry(configure, serve):
    configure()
    seen = serve(_refused)
    with pytest.raises(RecalcUnavailable):
        recalc_file(WB)
    assert len(seen) == 2


def test_retries_setting_is_honoured(configure, serve):
    configure(recalc_retries=0)
    seen = serve(_refused)
    with pytest.raises(RecalcUnavailable):
        recalc_file(WB)
    assert len(seen) == 1


def test_504_not_retried(configure, serve, sleeps):
    configure()
    seen = serve(_answer(504, "timeout"))  # the same file would hang again
    with pytest.raises(RecalcUnavailable):
        recalc_file(WB)
    assert len(seen) == 1
    assert sleeps == []


def test_401_not_retried_and_token_not_in_message(configure, serve, caplog):
    configure()
    seen = serve(_answer(401, "unauthorized"))
    with caplog.at_level(logging.DEBUG), pytest.raises(RecalcUnavailable) as excinfo:
        recalc_file(WB)
    assert len(seen) == 1
    assert TOKEN not in str(excinfo.value)
    assert TOKEN not in caplog.text
    assert "401" in caplog.text  # the cause is in the server log


@pytest.mark.parametrize("body", [b"", b"<html>502 Bad Gateway</html>"])
def test_non_xlsx_200_raises(configure, serve, body):
    configure()
    serve(lambda request: httpx.Response(200, content=body))
    with pytest.raises(RecalcUnavailable):
        recalc_file(WB)


def test_error_reply_without_json_still_raises_cleanly(configure, serve):
    configure()
    serve(lambda request: httpx.Response(500, content=b"<html>oops</html>"))
    with pytest.raises(RecalcUnavailable):
        recalc_file(WB)


def test_fallback_local_used_when_service_down(configure, serve, monkeypatch):
    configure(recalc_fallback="local")
    serve(_refused)
    monkeypatch.setattr(recalc, "_local", lambda b, t: FRESH)
    assert recalc_file(WB) == FRESH


def test_fallback_local_without_soffice_raises(configure, serve, monkeypatch):
    configure(recalc_fallback="local")
    serve(_refused)
    monkeypatch.setattr(recalc, "_local", lambda b, t: None)
    with pytest.raises(RecalcUnavailable):
        recalc_file(WB)


def test_fallback_local_failure_raises_unavailable(configure, serve, monkeypatch):
    configure(recalc_fallback="local")
    serve(_refused)

    def broken(b: bytes, t: float) -> bytes:
        raise subprocess.CalledProcessError(1, "soffice")

    monkeypatch.setattr(recalc, "_local", broken)
    with pytest.raises(RecalcUnavailable):
        recalc_file(WB)


def test_fallback_fail_never_runs_local(configure, serve, monkeypatch):
    configure(recalc_fallback="fail")
    serve(_refused)

    def not_called(b: bytes, t: float) -> bytes:
        raise AssertionError("the local LibreOffice must not run in fail mode")

    monkeypatch.setattr(recalc, "_local", not_called)
    with pytest.raises(RecalcUnavailable):
        recalc_file(WB)


def test_content_type_follows_the_workbook(configure, serve):
    configure()
    seen = serve(lambda request: httpx.Response(200, content=FRESH_M))
    recalc_file(WB)
    recalc_file(WB_M)
    assert [r.headers["Content-Type"] for r in seen] == [XLSX, XLSM]


def test_xlsm_round_trip_keeps_macros(configure, serve):
    configure()
    serve(lambda request: httpx.Response(200, content=FRESH_M))
    assert recalc_file(WB_M) == FRESH_M


def test_service_dropping_macros_raises(configure, serve):
    configure()
    serve(lambda request: httpx.Response(200, content=FRESH))  # no VBA project any more
    with pytest.raises(RecalcUnavailable, match="macros"):
        recalc_file(WB_M)


def test_local_dropping_macros_raises(configure, monkeypatch):
    configure(recalc_url="")
    monkeypatch.setattr(recalc, "_local", lambda b, t: FRESH)
    with pytest.raises(RecalcUnavailable, match="macros"):
        recalc_file(WB_M)


def test_local_uses_the_vba_filter_for_xlsm(configure, monkeypatch):
    configure(recalc_url="")
    seen: list[list[str]] = []

    def run(args, **kwargs):
        seen.append(list(args))
        uri = next(a for a in args if a.startswith("-env:")).split("=", 1)[1]
        profile = Path(url2pathname(urlparse(uri).path))
        assert "DisableMacrosExecution" in (
            profile / "user" / "registrymodifications.xcu"
        ).read_text(encoding="utf-8")
        out_dir = Path(args[args.index("--outdir") + 1])
        out_dir.mkdir()
        (out_dir / Path(args[-1]).name).write_bytes(FRESH_M)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(recalc.shutil, "which", lambda name: "soffice")
    monkeypatch.setattr(recalc.subprocess, "run", run)
    assert recalc_file(WB_M) == FRESH_M
    args = seen[0]
    assert args[args.index("--convert-to") + 1] == "xlsm:Calc MS Excel 2007 VBA XML"
    assert args[-1].endswith("in.xlsm")


def test_name_errors_after_conversion_raise_with_the_cells(configure, serve):
    configure()
    serve(lambda request: httpx.Response(200, content=_book(A1=5, E2="#NAME?", E3="#NAME?")))
    with pytest.raises(recalc.RecalcCannotCompute) as raised:
        recalc_file(WB)
    assert raised.value.cells == ["Sheet1!E2", "Sheet1!E3"]


def test_name_errors_already_in_the_reference_are_the_analysts_own(configure, serve):
    configure()
    converted = _book(A1=5, E2="#NAME?")
    serve(lambda request: httpx.Response(200, content=converted))
    assert recalc_file(WB, reference=_book(E2="#NAME?")) == converted


def test_only_new_name_errors_are_reported(configure, serve):
    configure()
    serve(lambda request: httpx.Response(200, content=_book(E2="#NAME?", E3="#NAME?")))
    with pytest.raises(recalc.RecalcCannotCompute) as raised:
        recalc_file(WB, reference=_book(E2="#NAME?"))
    assert raised.value.cells == ["Sheet1!E3"]


def test_other_errors_are_not_name_errors(configure, serve):
    configure()
    converted = _book(A1="#DIV/0!", B1=3)  # a division by zero is the model's own business
    serve(lambda request: httpx.Response(200, content=converted))
    assert recalc_file(WB) == converted


def test_local_conversion_is_checked_too(configure, monkeypatch):
    configure(recalc_url="")
    monkeypatch.setattr(recalc, "_local", lambda b, t: _book(E2="#NAME?"))
    with pytest.raises(recalc.RecalcCannotCompute):
        recalc_file(WB)


def test_passthrough_without_libreoffice_is_not_checked(configure, monkeypatch):
    configure(recalc_url="")
    monkeypatch.setattr(recalc.shutil, "which", lambda name: None)
    assert recalc_file(WB) == WB
