"""FastAPI application: routes, static frontend, and startup/shutdown."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import state
from app.api import chat, health, portfolio, watchlist
from app.market.factory import create_market_data_source
from app.market.stream import create_stream_router
from app.services.errors import ServiceError

logger = logging.getLogger(__name__)

SNAPSHOT_INTERVAL = 30.0  # seconds (BUILD_CONTRACT B4)
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
LOG_HANDLER_NAME = "finally-stdout"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging() -> None:
    """Send every `app.*` log record to stdout.

    Uvicorn only wires its own `uvicorn.*` loggers, so without this the root
    logger has no handler and our INFO lines vanish (WARNING+ leak out through
    Python's bare last-resort handler with no level or name). Level comes from
    LOG_LEVEL, default INFO. Idempotent: a second call adds nothing.
    """
    root = logging.getLogger()
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    root.setLevel(level if level in logging.getLevelNamesMapping() else "INFO")
    if any(h.get_name() == LOG_HANDLER_NAME for h in root.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.set_name(LOG_HANDLER_NAME)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(handler)


async def _snapshot_loop() -> None:
    """Record a portfolio snapshot every 30s, but only while a client is watching.

    Snapshotting an idle app fills the table with identical rows for nobody.
    """
    from app.services import portfolio_service

    while True:
        await asyncio.sleep(SNAPSHOT_INTERVAL)
        if state.sse_client_count() == 0:
            continue
        try:
            await portfolio_service.snapshot_now()
        except Exception:
            logger.exception("Portfolio snapshot failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the database, the market data feed, and the snapshot task."""
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

    from app.db.init import close_db, init_db
    from app.services.watchlist_service import tracked_tickers

    await init_db()

    source = create_market_data_source(state.price_cache)
    await source.start(await tracked_tickers())
    state.set_market_source(source)

    snapshot_task = asyncio.create_task(_snapshot_loop(), name="portfolio-snapshots")
    logger.info("FinAlly backend started")

    try:
        yield
    finally:
        snapshot_task.cancel()
        with suppress(asyncio.CancelledError):
            await snapshot_task
        await source.stop()
        state.set_market_source(None)
        await close_db()
        logger.info("FinAlly backend stopped")


def create_app() -> FastAPI:
    """Build the application. API routers are mounted before the static
    catch-all so static serving can never shadow /api/*."""
    configure_logging()
    app = FastAPI(title="FinAlly", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(ServiceError)
    async def _service_error(request: Request, exc: ServiceError) -> JSONResponse:
        """Every validation failure reaches the client as 400 {"error": ...}."""
        return JSONResponse(status_code=400, content={"error": str(exc)})

    @app.exception_handler(RequestValidationError)
    async def _request_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """FastAPI's own reply is 422 {"detail": [...]}. The API contract says
        every error is 400 {"error": ...}, so give clients one shape to handle."""
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", ())[1:]) or "request"
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid {field}: {first.get('msg', 'validation failed')}"},
        )

    app.include_router(health.router)
    app.include_router(portfolio.router)
    app.include_router(watchlist.router)
    app.include_router(chat.router)
    app.include_router(create_stream_router(state.price_cache))

    static_dir = Path(os.environ.get("STATIC_DIR", STATIC_DIR))
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    else:
        logger.warning("Static directory %s not found; serving API only", static_dir)

    return app


app = create_app()
