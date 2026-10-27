"""Recalculation service: headless LibreOffice behind a small HTTP API (design doc 16.5, 22.1).

Runs in its own image on an internal Docker network. Standard library only: it cannot import
``analekh`` and has no pip packages, so its limits come from environment variables that compose
fills from ``.env`` (recorded in docs/design/deviations.md).

POST /recalc   body: an .xlsx or .xlsm; header X-Recalc-Token. 200 with the recalculated workbook
               in the same format (an .xlsm keeps its VBA project; macros are never executed), or
               a JSON {"code": ...} body: 401 unauthorized, 413 too_large, 415 not_xlsx, 503 busy,
               504 timeout, 500 convert_failed or macros_lost (never with detail: paths and
               stderr stay in the log).
GET  /healthz  200 "ok", no token.

The token travels only in a header and is never logged.
"""

import contextlib
import hmac
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
XLSM = "application/vnd.ms-excel.sheet.macroEnabled.12"
ZIP_MAGIC = b"PK\x03\x04"  # an .xlsx or .xlsm is a zip file
DISCARD_LIMIT = 8 * 1024 * 1024  # most of a refused body that is read and dropped

# Written into each run's fresh profile before LibreOffice starts. Macros never executed (CLAUDE.md
# rule 7): execution disabled outright, security level "very high". VBA project loaded only so it
# can be saved back unchanged ("Save original Basic code"), never made executable.
PROFILE_SETTINGS = """<?xml version="1.0" encoding="UTF-8"?>
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

log = logging.getLogger("recalc")


def has_macros(data: bytes) -> bool:
    """Same test as analekh.workbook.reader.has_macros (this service cannot import analekh)."""
    return b"vbaProject.bin" in data


def target(data: bytes) -> tuple[str, str, str]:
    """(file suffix, LibreOffice --convert-to argument, content type) that keeps the format:
    an .xlsm stays an .xlsm with its VBA project, an .xlsx stays an .xlsx."""
    if has_macros(data):
        return ".xlsm", "xlsm:Calc MS Excel 2007 VBA XML", XLSM
    return ".xlsx", "xlsx:Calc MS Excel 2007 XML", XLSX


def _kill_profile_processes(profile: Path) -> None:
    """Kill any process started with this profile (soffice is a wrapper: the real soffice.bin
    keeps running when only the wrapper is killed at the timeout). Linux only; best effort."""
    proc = Path("/proc")
    if not proc.is_dir():
        return
    needle = str(profile).encode()
    me = os.getpid()
    for entry in proc.iterdir():
        if not entry.name.isdigit() or int(entry.name) == me:
            continue
        try:
            if needle in (entry / "cmdline").read_bytes():
                os.kill(int(entry.name), 9)
        except OSError:
            continue


def convert(src: bytes, timeout: float) -> bytes:
    """One LibreOffice run in its own temp dir and its own profile (a shared profile makes
    concurrent runs clash). Raises subprocess.TimeoutExpired, CalledProcessError or OSError."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice is None:
        raise FileNotFoundError("soffice")
    suffix, convert_to, _ = target(src)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        profile = root / "profile"
        (profile / "user").mkdir(parents=True)
        (profile / "user" / "registrymodifications.xcu").write_text(
            PROFILE_SETTINGS, encoding="utf-8"
        )
        source = root / f"in{suffix}"
        out_dir = root / "out"
        source.write_bytes(src)
        try:
            subprocess.run(
                [
                    soffice,
                    "--headless",
                    "--norestore",
                    f"-env:UserInstallation={profile.as_uri()}",
                    "--convert-to",
                    convert_to,
                    "--outdir",
                    str(out_dir),
                    str(source),
                ],
                check=True,
                timeout=timeout,
                capture_output=True,
                env={**os.environ, "HOME": tmp},
            )
        except subprocess.TimeoutExpired:
            _kill_profile_processes(profile)
            raise
        return (out_dir / source.name).read_bytes()


def make_handler(
    token: str,
    max_bytes: int,
    timeout: float,
    slots: threading.BoundedSemaphore,
    convert: Callable[[bytes, float], bytes],
) -> type[BaseHTTPRequestHandler]:
    expected = token.encode()

    class Handler(BaseHTTPRequestHandler):
        server_version = "recalc"
        sys_version = ""
        timeout = 60  # a stalled client cannot hold a thread for ever
        unread = 0  # body bytes the client announced and this handler has not read

        def log_message(self, format: str, *args: object) -> None:
            pass  # one line per request is written by _send

        def _send(self, status: int, body: bytes, content_type: str, started: float) -> None:
            log.info(
                "%s %s -> %d, %d bytes, %d ms",
                self.command,
                self.path.split("?", 1)[0],  # never a query string: nothing secret belongs there
                status,
                len(body),
                (time.monotonic() - started) * 1000,
            )
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            self._discard_unread()

        def _discard_unread(self) -> None:
            """After an early refusal, read (and drop) the start of the body the client is still
            sending. Closing with unread data resets the connection, and the client could lose the
            answer. Bounded in size and time: the refusal has already been sent."""
            remaining = min(self.unread, DISCARD_LIMIT)
            self.unread = 0
            with contextlib.suppress(OSError):
                self.connection.settimeout(2)
                while remaining > 0:
                    chunk = self.rfile.read1(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)

        def _error(self, status: int, code: str, started: float) -> None:
            body = json.dumps({"code": code}).encode()
            self._send(status, body, "application/json", started)

        def do_GET(self) -> None:
            started = time.monotonic()
            if self.path == "/healthz":
                self._send(200, b"ok", "text/plain", started)
            else:
                self._error(404, "not_found", started)

        def do_POST(self) -> None:
            started = time.monotonic()
            if self.path != "/recalc":
                return self._error(404, "not_found", started)
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                length = -1
            self.unread = max(length, 0)
            supplied = self.headers.get("X-Recalc-Token", "").encode()
            if not hmac.compare_digest(supplied, expected):
                return self._error(401, "unauthorized", started)
            if length < 0:
                return self._error(411, "length_required", started)
            if length > max_bytes:
                return self._error(413, "too_large", started)  # before the body is read
            body = self.rfile.read(length)
            self.unread = 0
            if len(body) != length:
                return self._error(400, "bad_request", started)
            if not body.startswith(ZIP_MAGIC):
                return self._error(415, "not_xlsx", started)
            if not slots.acquire(timeout=timeout):
                return self._error(503, "busy", started)
            try:
                out = convert(body, timeout)
            except subprocess.TimeoutExpired:
                log.error("LibreOffice timed out after %s s", timeout)
                return self._error(504, "timeout", started)
            except subprocess.CalledProcessError as exc:
                log.error("LibreOffice failed (exit %s): %r", exc.returncode, exc.stderr)
                return self._error(500, "convert_failed", started)
            except Exception as exc:
                log.error("conversion failed: %s", type(exc).__name__)
                return self._error(500, "convert_failed", started)
            finally:
                slots.release()
            if not out.startswith(ZIP_MAGIC):
                log.error("LibreOffice produced %d bytes that are not a workbook", len(out))
                return self._error(500, "convert_failed", started)
            if has_macros(body) and not has_macros(out):
                log.error("LibreOffice dropped the VBA project of an .xlsm")
                return self._error(500, "macros_lost", started)
            self._send(200, out, target(body)[2], started)

    return Handler


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, stream=sys.stderr, format="%(asctime)s %(levelname)s %(message)s"
    )
    token = os.environ.get("RECALC_TOKEN", "")
    if not token:
        log.error("RECALC_TOKEN is empty: refusing to start")
        sys.exit(1)
    max_bytes = int(os.environ.get("RECALC_MAX_BYTES", "104857600"))
    timeout = float(os.environ.get("RECALC_TIMEOUT_SECONDS", "180"))
    concurrency = int(os.environ.get("RECALC_CONCURRENCY", "2"))
    port = int(os.environ.get("RECALC_PORT", "8080"))
    slots = threading.BoundedSemaphore(concurrency)
    handler = make_handler(token, max_bytes, timeout, slots, convert)
    # All interfaces inside the container: the only network it is on is internal (compose).
    server = ThreadingHTTPServer(("0.0.0.0", port), handler)
    log.info(
        "listening on :%d (concurrency %d, timeout %s s, max %d bytes)",
        port,
        concurrency,
        timeout,
        max_bytes,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
