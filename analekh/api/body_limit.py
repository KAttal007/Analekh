"""Refuse oversized request bodies on arrival (auth design, section 7).

`uploads.read_limited` checks admin's limit only after framework parsed multipart and spooled the
file to disk. This middleware stops bodies above upload ceiling + multipart framing earlier: at
once if Content-Length says so, else once streamed bytes pass it.
"""

import json
from collections.abc import Callable

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from analekh.config import get_settings

MB = 1024 * 1024


def max_body_bytes() -> int:
    s = get_settings()
    return s.max_upload_ceiling_bytes + s.request_body_overhead_bytes


def too_large_message() -> str:
    ceiling = get_settings().max_upload_ceiling_bytes // MB
    return f"This file is larger than {ceiling} MB, the most Analekh accepts."


class BodySizeLimit:
    def __init__(self, app: ASGIApp, limit: Callable[[], int] = max_body_bytes) -> None:
        self.app = app
        self.limit = limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self.limit()
        declared = dict(scope.get("headers", [])).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > limit:
            await _refuse(send)
            return
        received = 0
        started = refused = False

        async def counted_receive() -> Message:
            nonlocal received, refused
            if refused:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    # Answer now; the app sees the client go away (the framework would turn an
                    # exception raised here into a 400) and whatever it sends is dropped.
                    refused = True
                    if not started:
                        await _refuse(send)
                    return {"type": "http.disconnect"}
            return message

        async def tracked_send(message: Message) -> None:
            nonlocal started
            if refused:
                return
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        await self.app(scope, counted_receive, tracked_send)


async def _refuse(send: Send) -> None:
    body = json.dumps({"detail": too_large_message()}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"connection", b"close"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
