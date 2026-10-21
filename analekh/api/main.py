"""REST API (design doc 20). Long tasks return a job id; poll GET /jobs/{id}. Swagger at /docs."""

import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from botocore.exceptions import ConnectTimeoutError, EndpointConnectionError
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from analekh import __version__
from analekh.api.routers import change_sets, companies, comps, models, outputs, system, templates
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
    threading.Thread(target=_warm_up, name="warm-up", daemon=True).start()
    yield


app = FastAPI(
    title="Analekh",
    version=__version__,
    description="The analyst's record, kept for you.",
    lifespan=lifespan,
)
app.add_middleware(GZipMiddleware, minimum_size=1024)  # e.g. the company index: ~300 KB -> ~60 KB
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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
):
    app.include_router(router)


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


@app.get("/health", tags=["ops"])
def health() -> dict:
    return {"ok": True, "version": __version__}
