"""The recalc service (deploy/recalc/server.py): token, limits, xlsx checks, slots, timeouts and a
LibreOffice profile of its own per conversion. LibreOffice itself is never run here."""

import importlib.util
import json
import subprocess
import threading
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

import pytest

SERVER = Path(__file__).resolve().parents[1] / "deploy" / "recalc" / "server.py"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
OK = b"PK\x03\x04done"
BODY = b"PK\x03\x04input"
XLSM = "application/vnd.ms-excel.sheet.macroEnabled.12"
BODY_M = b"PK\x03\x04input xl/vbaProject.bin"  # an .xlsm: the zip lists a VBA project
OK_M = b"PK\x03\x04done xl/vbaProject.bin"


def _load():
    spec = importlib.util.spec_from_file_location("recalc_server", SERVER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


server_module = _load()


@pytest.fixture
def start():
    """start(convert, ...) serves the handler on a free port and returns that port."""
    servers: list = []

    def _start(convert, *, token="tok", max_bytes=1000, timeout=0.5, concurrency=2) -> int:
        handler = server_module.make_handler(token, max_bytes, timeout, threading.BoundedSemaphore(concurrency), convert)
        httpd = server_module.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        servers.append(httpd)
        return httpd.server_address[1]

    yield _start
    for httpd in servers:
        httpd.shutdown()
        httpd.server_close()


def _post(port: int, body: bytes = BODY, token: str | None = "tok"):
    conn = HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"X-Recalc-Token": token} if token is not None else {}
    conn.request("POST", "/recalc", body=body, headers=headers)
    res = conn.getresponse()
    data = res.read()
    conn.close()
    return res, data


def _code(data: bytes) -> str:
    return json.loads(data)["code"]


class Recorder:
    def __init__(self, result: bytes = OK) -> None:
        self.calls = 0
        self.result = result

    def __call__(self, src: bytes, timeout: float) -> bytes:
        self.calls += 1
        return self.result


def test_missing_or_wrong_token_is_401(start):
    fake = Recorder()
    port = start(fake)
    for token in (None, "wrong", ""):
        res, data = _post(port, token=token)
        assert res.status == 401
        assert _code(data) == "unauthorized"
    assert fake.calls == 0


def test_body_over_limit_is_413(start):
    fake = Recorder()
    port = start(fake, max_bytes=100)
    conn = HTTPConnection("127.0.0.1", port, timeout=10)
    conn.putrequest("POST", "/recalc")
    conn.putheader("X-Recalc-Token", "tok")
    conn.putheader("Content-Length", "101")  # no body is sent: the answer comes before it is read
    conn.endheaders()
    res = conn.getresponse()
    assert res.status == 413
    assert _code(res.read()) == "too_large"
    conn.close()
    assert fake.calls == 0


def test_non_xlsx_is_415(start):
    fake = Recorder()
    port = start(fake)
    res, data = _post(port, b"<html>not a workbook</html>")
    assert res.status == 415
    assert _code(data) == "not_xlsx"
    assert fake.calls == 0


def test_success_returns_converted_bytes(start):
    port = start(Recorder())
    res, data = _post(port)
    assert res.status == 200
    assert data == OK
    assert res.getheader("Content-Type") == XLSX


def test_convert_timeout_is_504_and_frees_slot(start):
    outcomes = [subprocess.TimeoutExpired("soffice", 1)]

    def fake(src: bytes, timeout: float) -> bytes:
        if outcomes:
            raise outcomes.pop()
        return OK

    port = start(fake, concurrency=1)
    res, data = _post(port)
    assert res.status == 504
    assert _code(data) == "timeout"
    res, data = _post(port)  # the single slot was given back
    assert res.status == 200
    assert data == OK


def test_busy_is_503(start):
    entered, release = threading.Event(), threading.Event()

    def fake(src: bytes, timeout: float) -> bytes:
        entered.set()
        release.wait(10)
        return OK

    port = start(fake, concurrency=1, timeout=0.3)
    first: list = []
    t = threading.Thread(target=lambda: first.append(_post(port)))
    t.start()
    try:
        assert entered.wait(5)
        res, data = _post(port)
        assert res.status == 503
        assert _code(data) == "busy"
    finally:
        release.set()
        t.join(10)
    assert first[0][0].status == 200


def test_convert_failure_is_500_without_detail(start):
    def fake(src: bytes, timeout: float) -> bytes:
        raise subprocess.CalledProcessError(1, "soffice", stderr=b"secret path /tmp/xyz")

    port = start(fake)
    res, data = _post(port)
    assert res.status == 500
    assert _code(data) == "convert_failed"
    assert b"secret path" not in data


def test_converted_output_that_is_not_xlsx_is_500(start):
    port = start(Recorder(b"<html>error</html>"))
    res, data = _post(port)
    assert res.status == 500
    assert _code(data) == "convert_failed"


def test_healthz_needs_no_token(start):
    port = start(Recorder())
    conn = HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("GET", "/healthz")
    res = conn.getresponse()
    assert res.status == 200
    assert res.read() == b"ok"
    conn.close()


def test_token_is_not_logged(start, caplog):
    port = start(Recorder(), token="s3cret-token-value")
    with caplog.at_level("INFO", logger="recalc"):
        _post(port, token="s3cret-token-value")
        _post(port, token="wrong-token-guess")
    assert caplog.records  # one line per request
    assert "s3cret-token-value" not in caplog.text
    assert "wrong-token-guess" not in caplog.text


def test_convert_uses_own_profile_per_call(monkeypatch):
    seen: list[tuple[str, Path]] = []

    def fake_run(args, **kwargs):
        profile = next(a for a in args if a.startswith("-env:UserInstallation="))
        out_dir = Path(args[args.index("--outdir") + 1])
        source = Path(args[-1])
        seen.append((profile.split("=", 1)[1], source.parent))
        out_dir.mkdir()
        (out_dir / source.name).write_bytes(OK)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(server_module.shutil, "which", lambda name: "/usr/bin/soffice")
    monkeypatch.setattr(server_module.subprocess, "run", fake_run)
    assert server_module.convert(BODY, 5) == OK
    assert server_module.convert(BODY, 5) == OK
    (uri_a, dir_a), (uri_b, dir_b) = seen
    assert uri_a != uri_b
    for uri, tmp in ((uri_a, dir_a), (uri_b, dir_b)):
        assert uri.startswith("file:///")
        assert uri == (tmp / "profile").as_uri()  # under this call's own temp dir


def _fake_run(seen: list[list[str]], result: bytes):
    """subprocess.run stand-in: records the arguments and writes `result` where soffice would."""

    def run(args, **kwargs):
        seen.append(list(args))
        out_dir = Path(args[args.index("--outdir") + 1])
        source = Path(args[-1])
        uri = next(a for a in args if a.startswith("-env:")).split("=", 1)[1]
        settings = Path(url2pathname(urlparse(uri).path)) / "user" / "registrymodifications.xcu"
        seen.append([settings.read_text(encoding="utf-8")] if settings.exists() else [])
        out_dir.mkdir()
        (out_dir / source.name).write_bytes(result)
        return subprocess.CompletedProcess(args, 0)

    return run


def test_xlsx_is_converted_to_xlsx(monkeypatch):
    seen: list[list[str]] = []
    monkeypatch.setattr(server_module.shutil, "which", lambda name: "/usr/bin/soffice")
    monkeypatch.setattr(server_module.subprocess, "run", _fake_run(seen, OK))
    assert server_module.convert(BODY, 5) == OK
    args = seen[0]
    assert args[args.index("--convert-to") + 1] == "xlsx:Calc MS Excel 2007 XML"
    assert args[-1].endswith("in.xlsx")


def test_xlsm_is_converted_with_the_vba_filter(monkeypatch):
    seen: list[list[str]] = []
    monkeypatch.setattr(server_module.shutil, "which", lambda name: "/usr/bin/soffice")
    monkeypatch.setattr(server_module.subprocess, "run", _fake_run(seen, OK_M))
    assert server_module.convert(BODY_M, 5) == OK_M
    args = seen[0]
    assert args[args.index("--convert-to") + 1] == "xlsm:Calc MS Excel 2007 VBA XML"
    assert args[-1].endswith("in.xlsm")


def test_profile_disables_macro_execution(monkeypatch):
    seen: list[list[str]] = []
    monkeypatch.setattr(server_module.shutil, "which", lambda name: "/usr/bin/soffice")
    monkeypatch.setattr(server_module.subprocess, "run", _fake_run(seen, OK_M))
    server_module.convert(BODY_M, 5)
    (settings,) = seen[1]  # the profile's settings file existed before LibreOffice started
    assert '"DisableMacrosExecution" oor:op="fuse"><value>true<' in settings
    assert '"MacroSecurityLevel" oor:op="fuse"><value>3<' in settings
    assert '"Executable" oor:op="fuse"><value>false<' in settings
    assert '"Save" oor:op="fuse"><value>true<' in settings


def test_xlsm_reply_has_the_macro_enabled_type(start):
    port = start(Recorder(OK_M))
    res, data = _post(port, BODY_M)
    assert res.status == 200
    assert data == OK_M
    assert res.getheader("Content-Type") == XLSM


def test_xlsm_that_lost_its_macros_is_refused(start):
    port = start(Recorder(OK))  # LibreOffice wrote a workbook without the VBA project
    res, data = _post(port, BODY_M)
    assert res.status == 500
    assert _code(data) == "macros_lost"
