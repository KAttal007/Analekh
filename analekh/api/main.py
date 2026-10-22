"""REST API (design doc 20). Long tasks return a job id; poll GET /jobs/{id}. Swagger at /docs."""

import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio.to_thread
import structlog
from botocore.exceptions import ConnectTimeoutError, EndpointConnectionError
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import TimeoutError as PoolTimeout

from analekh import __version__
from analekh.api.body_limit import BodySizeLimit
from analekh.api.deps import auth_is_off, check_auth_switch, get_user
from analekh.api.routers import (
    auth,
    change_sets,
    companies,
    comps,
    models,
    outputs,
    public,
    settings_api,
    system,
    templates,
    tokens,
    users,
)
from analekh.config import get_settings
from analekh.ingest.storage import StorageUnavailable

log = structlog.get_logger()


def _warm_up() -> None:
    """Import what the handlers import lazily and run the heavy queries once, so the first
    visitor doesn't pay for it (a cold first call took 0.5-1.7 s). Best effort: a database that
    is not up yet must not stop the API from starting."""
    try:
        from analekh import desk as desk_module  # noqa: F401
        from analekh import glance as glance_module  # noqa: F401
        from analekh import history, prices, restatements  # noqa: F401
        from analekh.db.session import session_scope

        with session_scope() as s:
            desk_module.desk(s, limit=1)
    except Exception as exc:  # noqa: BLE001
        log.warning("warm_up_skipped", error=type(exc).__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    check_auth_switch()
    if auth_is_off():
        log.warning("sign_in_is_off", note="ENV=dev: every request acts as the dev admin")
    # Pin the worker-thread count so the database pool can be sized against it.
    limiter = anyio.to_thread.current_default_thread_limiter()
    limiter.total_tokens = get_settings().api_thread_limit
    threading.Thread(target=_warm_up, name="warm-up", daemon=True).start()
    yield


app = FastAPI(
    title="Analekh",
    version=__version__,
    description="The analyst's record, kept for you.",
    lifespan=lifespan,
)
app.add_middleware(BodySizeLimit)  # oversized bodies refused before they are spooled
app.add_middleware(GZipMiddleware, minimum_size=1024)  # e.g. the company index: ~300 KB -> ~60 KB
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,  # the session cookie travels with cross-origin calls from these origins
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    companies.router,
    templates.router,
    models.router,
    change_sets.router,
    outputs.router,
    comps.router,
    system.router,
    tokens.router,
    users.router,
    settings_api.router,
):
    app.include_router(router, dependencies=[Depends(get_user)])  # every route needs a session

# Open: sign-in itself and the public sign-in-screen data (plus /docs, /openapi.json, /health).
app.include_router(auth.router)
app.include_router(public.router)


def _storage_down(request: Request, exc: Exception) -> JSONResponse:
    endpoint = get_settings().minio_endpoint
    return JSONResponse(
        status_code=503,
        content={
            "detail": f"Object storage (MinIO) is not reachable at {endpoint}. "
            "Start it with: docker compose up -d minio"
        },
    )


# Raised while connecting (StorageUnavailable) or by a later call on the cached store (botocore).
for _exc in (StorageUnavailable, EndpointConnectionError, ConnectTimeoutError):
    app.add_exception_handler(_exc, _storage_down)


def _database_busy(request: Request, exc: Exception) -> JSONResponse:
    """Every database connection is in use: answer at once instead of hanging for 30 s."""
    wait = max(1, round(get_settings().db_pool_timeout_seconds))
    return JSONResponse(
        status_code=503,
        content={"detail": "The server is busy. Try again in a few seconds."},
        headers={"Retry-After": str(wait)},
    )


app.add_exception_handler(PoolTimeout, _database_busy)


@app.get("/health", tags=["ops"])
def health() -> dict:
    return {"ok": True, "version": __version__}
