"""Capture the diagram panels of docs/design/architecture.html as PNGs for the Word document
(headless Microsoft Edge over the DevTools protocol; Windows path below).

    uv run python scripts/diagram_panels.py file:///<repo>/docs/design/architecture.html OUT_DIR
"""

import asyncio
import base64
import json
import subprocess
import sys
import tempfile
import time
import urllib.request

import websockets

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 9341


async def main(url: str, out: str) -> None:
    profile = tempfile.mkdtemp(prefix="edge-cdp-")
    proc = subprocess.Popen(
        [
            EDGE,
            "--headless=new",
            "--disable-gpu",
            f"--remote-debugging-port={PORT}",
            f"--user-data-dir={profile}",
            "about:blank",
        ]
    )
    try:
        for _ in range(50):
            try:
                targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
                page = next(t for t in targets if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.2)
        async with websockets.connect(page["webSocketDebuggerUrl"], max_size=80_000_000) as ws:
            n = 0

            async def call(method: str, **params):
                nonlocal n
                n += 1
                await ws.send(json.dumps({"id": n, "method": method, "params": params}))
                while True:
                    msg = json.loads(await ws.recv())
                    if msg.get("id") == n:
                        return msg.get("result", {})

            await call("Page.enable")
            await call(
                "Emulation.setDeviceMetricsOverride",
                width=1300,
                height=2400,
                deviceScaleFactor=2.5,
                mobile=False,
            )
            await call("Page.navigate", url=url)
            await asyncio.sleep(3)
            res = await call(
                "Runtime.evaluate",
                returnByValue=True,
                expression="""
              [...document.querySelectorAll('.panel')].map(p => {
                const r = p.getBoundingClientRect();
                return [r.left + scrollX, r.top + scrollY, r.width, r.height];
              })""",
            )
            for i, (x, y, w, h) in enumerate(res["result"]["value"], 1):
                shot = await call(
                    "Page.captureScreenshot",
                    format="png",
                    captureBeyondViewport=True,
                    clip={"x": x, "y": y, "width": w, "height": h, "scale": 1},
                )
                with open(f"{out}/panel{i}.png", "wb") as fh:
                    fh.write(base64.b64decode(shot["data"]))
                print("panel", i, round(w), round(h))
    finally:
        proc.terminate()


asyncio.run(main(sys.argv[1], sys.argv[2]))
