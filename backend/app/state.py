"""Shared application state.

One module-level holder, created at import and populated in the FastAPI
`lifespan` handler. Everything reads prices from `price_cache`; nothing calls a
data source for a price.
"""

from __future__ import annotations

from threading import Lock

from app.market.cache import PriceCache
from app.market.interface import MarketDataSource

price_cache: PriceCache = PriceCache()
market_source: MarketDataSource | None = None

_sse_clients: int = 0
_sse_lock = Lock()


def get_market_source() -> MarketDataSource:
    """The running market data source. Raises if the app has not started."""
    if market_source is None:
        raise RuntimeError("Market data source not started")
    return market_source


def set_market_source(source: MarketDataSource | None) -> None:
    """Set (or clear, on shutdown) the running market data source."""
    global market_source
    market_source = source


def sse_client_connected() -> None:
    """Register a newly connected SSE client."""
    global _sse_clients
    with _sse_lock:
        _sse_clients += 1


def sse_client_disconnected() -> None:
    """Deregister a departed SSE client. Never goes below zero."""
    global _sse_clients
    with _sse_lock:
        _sse_clients = max(0, _sse_clients - 1)


def sse_client_count() -> int:
    """Number of connected SSE clients (BUILD_CONTRACT B4 snapshot gating)."""
    with _sse_lock:
        return _sse_clients


def reset() -> None:
    """Reset state between tests."""
    global price_cache, market_source, _sse_clients
    price_cache = PriceCache()
    market_source = None
    with _sse_lock:
        _sse_clients = 0
