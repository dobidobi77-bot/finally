"""Massive (Polygon.io) API client for real market data."""

from __future__ import annotations

import asyncio
import logging
import time

from massive import RESTClient

from .cache import PriceCache
from .interface import MarketDataSource

logger = logging.getLogger(__name__)

# The library's own SnapshotMarketType enum is not a str-enum, so passing it
# renders "SnapshotMarketType.STOCKS" into the URL and every poll 404s
# (massive 2.2.0). The plain string is what the endpoint path needs.
SNAPSHOT_MARKET_TYPE = "stocks"


def _bar_value(snap, bar: str, field: str) -> float | None:
    """Read `snap.<bar>.<field>` and return it only if it is a positive number."""
    value = getattr(getattr(snap, bar, None), field, None)
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return float(value)
    return None


def _ms_to_seconds(ms: float | None) -> float:
    """Massive bar timestamps are Unix milliseconds; fall back to now."""
    return ms / 1000.0 if ms else time.time()


def resolve_price(snap) -> tuple[float, float] | None:
    """Pick the freshest (price, timestamp_seconds) a snapshot carries.

    `last_trade` needs a trades entitlement that the free/Starter plans lack
    (the API answers NOT_AUTHORIZED), so it is None at every hour there.
    The aggregate bars are always present, so fall through them: latest
    minute bar, then today's day bar, then the prior session's close.
    """
    for bar, price_field, ts_field in (
        ("last_trade", "price", "timestamp"),
        ("min", "close", "timestamp"),
    ):
        price = _bar_value(snap, bar, price_field)
        if price is not None:
            return price, _ms_to_seconds(_bar_value(snap, bar, ts_field))

    price = _bar_value(snap, "day", "close") or _bar_value(snap, "prev_day", "close")
    if price is None:
        return None
    updated_ns = getattr(snap, "updated", None)  # snapshot-level, nanoseconds
    if isinstance(updated_ns, (int, float)) and updated_ns > 0:
        return price, updated_ns / 1e9
    return price, time.time()


def resolve_open_price(snap) -> float | None:
    """Session baseline for daily change % (BUILD_CONTRACT A1).

    Massive clears snapshot data at 12am ET and repopulates it from the first
    trade of the new session (as early as 4am ET pre-market), per the
    RESTClient.get_snapshot_all docstring. So between midnight and the first
    trade `day` is all zeros and the prior close is the only sane baseline;
    once trading starts `day.open` is this session's first print. Outside
    hours `day` is the most recent completed session, so the change % shown
    is that session's move.
    """
    return _bar_value(snap, "day", "open") or _bar_value(snap, "prev_day", "close")


class MassiveDataSource(MarketDataSource):
    """MarketDataSource backed by the Massive (Polygon.io) REST API.

    Polls GET /v2/snapshot/locale/us/markets/stocks/tickers for all watched
    tickers in a single API call, then writes results to the PriceCache.

    Rate limits:
      - Free tier: 5 req/min → poll every 15s (default)
      - Paid tiers: higher limits → poll every 2-5s
    """

    def __init__(
        self,
        api_key: str,
        price_cache: PriceCache,
        poll_interval: float = 15.0,
    ) -> None:
        self._api_key = api_key
        self._cache = price_cache
        self._interval = poll_interval
        self._tickers: list[str] = []
        self._task: asyncio.Task | None = None
        self._client: RESTClient | None = None

    async def start(self, tickers: list[str]) -> None:
        self._client = RESTClient(api_key=self._api_key)
        self._tickers = list(tickers)

        # Do an immediate first poll so the cache has data right away
        await self._poll_once()

        self._task = asyncio.create_task(self._poll_loop(), name="massive-poller")
        logger.info(
            "Massive poller started: %d tickers, %.1fs interval",
            len(tickers),
            self._interval,
        )

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self._client = None
        logger.info("Massive poller stopped")

    async def add_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        if ticker not in self._tickers:
            self._tickers.append(ticker)
            logger.info("Massive: added ticker %s (will appear on next poll)", ticker)

    async def remove_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        self._tickers = [t for t in self._tickers if t != ticker]
        self._cache.remove(ticker)
        logger.info("Massive: removed ticker %s", ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    # --- Internal ---

    async def _poll_loop(self) -> None:
        """Poll on interval. First poll already happened in start()."""
        while True:
            await asyncio.sleep(self._interval)
            await self._poll_once()

    async def _poll_once(self) -> None:
        """Execute one poll cycle: fetch snapshots, update cache."""
        if not self._tickers or not self._client:
            return

        try:
            # The Massive RESTClient is synchronous — run in a thread to
            # avoid blocking the event loop.
            snapshots = await asyncio.to_thread(self._fetch_snapshots)
            processed = 0
            for snap in snapshots:
                ticker = getattr(snap, "ticker", None)
                resolved = resolve_price(snap)
                if not ticker or resolved is None:
                    logger.warning("Skipping snapshot for %s: no price in payload", ticker or "???")
                    continue
                price, timestamp = resolved
                self._cache.update(ticker=ticker, price=price, timestamp=timestamp)
                open_price = resolve_open_price(snap)
                if open_price is not None:
                    self._cache.set_open_price(ticker, open_price)
                processed += 1
            logger.debug("Massive poll: updated %d/%d tickers", processed, len(self._tickers))

        except Exception as e:
            logger.error("Massive poll failed: %s", e)
            # Don't re-raise — the loop will retry on the next interval.
            # Common failures: 401 (bad key), 429 (rate limit), network errors.

    def _fetch_snapshots(self) -> list:
        """Synchronous call to the Massive REST API. Runs in a thread."""
        return self._client.get_snapshot_all(
            market_type=SNAPSHOT_MARKET_TYPE,
            tickers=self._tickers,
        )
