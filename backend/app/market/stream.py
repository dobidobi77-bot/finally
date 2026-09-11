"""SSE streaming endpoint for live price updates."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .cache import PriceCache

logger = logging.getLogger(__name__)

KEEPALIVE_INTERVAL = 15.0  # seconds between ": keepalive" comments


def create_stream_router(price_cache: PriceCache) -> APIRouter:
    """Create the SSE streaming router bound to a price cache.

    The APIRouter is created here, not at module scope, so each call returns an
    independent router bound to the cache passed in. A module-level router would
    accumulate a duplicate route on every call and keep serving the first cache.
    """
    router = APIRouter(prefix="/api/stream", tags=["streaming"])

    @router.get("/prices")
    async def stream_prices(request: Request) -> StreamingResponse:
        """SSE endpoint for live price updates (BUILD_CONTRACT A5).

        One unnamed event whose data is a JSON object keyed by ticker, emitted
        only when the cache version changes:

            data: {"AAPL": {"ticker": "AAPL", "price": 190.50, ...}, ...}

        Sends `retry: 1000` on connect so the browser auto-reconnects, and a
        `: keepalive` comment every 15s so proxies do not close an idle stream.
        """
        return StreamingResponse(
            _generate_events(price_cache, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering if proxied
            },
        )

    return router


async def _generate_events(
    price_cache: PriceCache,
    request: Request,
    interval: float = 0.5,
) -> AsyncGenerator[str, None]:
    """Async generator that yields SSE-formatted price events.

    Pushes the full price map whenever the cache version changes, and a
    keepalive comment during quiet periods. Exits when the client disconnects.
    """
    from app import state

    last_version = -1
    last_sent = time.monotonic()
    client_ip = request.client.host if request.client else "unknown"

    # Registered before the first yield so the snapshot gate (B4) counts this
    # client from the moment the stream opens, not one iteration later.
    state.sse_client_connected()
    logger.info("SSE client connected: %s (%d total)", client_ip, state.sse_client_count())

    try:
        # Tell the client to retry after 1 second if the connection drops
        yield "retry: 1000\n\n"

        while True:
            # Check for client disconnect
            if await request.is_disconnected():
                logger.info("SSE client disconnected: %s", client_ip)
                break

            current_version = price_cache.version
            if current_version != last_version:
                last_version = current_version
                prices = price_cache.get_all()

                if prices:
                    data = {ticker: update.to_dict() for ticker, update in prices.items()}
                    yield f"data: {json.dumps(data)}\n\n"
                    last_sent = time.monotonic()
            elif time.monotonic() - last_sent >= KEEPALIVE_INTERVAL:
                yield ": keepalive\n\n"
                last_sent = time.monotonic()

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("SSE stream cancelled for: %s", client_ip)
    finally:
        state.sse_client_disconnected()
