"""Thread-safe in-memory price cache."""

from __future__ import annotations

import time
from threading import Lock

from .models import PriceUpdate


class PriceCache:
    """Thread-safe in-memory cache of the latest price for each ticker.

    Writers: SimulatorDataSource or MassiveDataSource (one at a time).
    Readers: SSE streaming endpoint, portfolio valuation, trade execution.

    Also holds a per-ticker `open_price` — the session baseline for the daily
    change % (BUILD_CONTRACT A1). It is set the first time a ticker is written,
    or explicitly via `set_open_price()` when the source knows a better value
    (the Massive daily-bar open).
    """

    def __init__(self) -> None:
        self._prices: dict[str, PriceUpdate] = {}
        self._open_prices: dict[str, float] = {}
        self._lock = Lock()
        self._version: int = 0  # Monotonically increasing; bumped on every change

    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:
        """Record a new price for a ticker. Returns the created PriceUpdate.

        Automatically computes direction and change from the previous price.
        If this is the first update for the ticker, previous_price == price
        (direction='flat') and open_price is seeded from this price.
        """
        with self._lock:
            ts = timestamp or time.time()
            prev = self._prices.get(ticker)
            previous_price = prev.price if prev else price
            rounded = round(price, 2)

            open_price = self._open_prices.setdefault(ticker, rounded)

            update = PriceUpdate(
                ticker=ticker,
                price=rounded,
                previous_price=round(previous_price, 2),
                open_price=open_price,
                timestamp=ts,
            )
            self._prices[ticker] = update
            self._version += 1
            return update

    def set_open_price(self, ticker: str, open_price: float) -> None:
        """Set the session baseline for a ticker, overwriting any seeded value.

        Used by the Massive source, which learns the real daily-bar open only
        after its first poll.
        """
        with self._lock:
            rounded = round(open_price, 2)
            if self._open_prices.get(ticker) == rounded:
                return
            self._open_prices[ticker] = rounded
            current = self._prices.get(ticker)
            if current is not None:
                self._prices[ticker] = PriceUpdate(
                    ticker=current.ticker,
                    price=current.price,
                    previous_price=current.previous_price,
                    open_price=rounded,
                    timestamp=current.timestamp,
                )
            self._version += 1

    def get_open_price(self, ticker: str) -> float | None:
        """Session baseline for a ticker, or None if it has never been priced."""
        with self._lock:
            return self._open_prices.get(ticker)

    def get(self, ticker: str) -> PriceUpdate | None:
        """Get the latest price for a single ticker, or None if unknown."""
        with self._lock:
            return self._prices.get(ticker)

    def get_all(self) -> dict[str, PriceUpdate]:
        """Snapshot of all current prices. Returns a shallow copy."""
        with self._lock:
            return dict(self._prices)

    def get_price(self, ticker: str) -> float | None:
        """Convenience: get just the price float, or None."""
        update = self.get(ticker)
        return update.price if update else None

    def remove(self, ticker: str) -> None:
        """Remove a ticker from the cache (e.g., when removed from watchlist).

        Bumps the version so the SSE generator pushes the removal to clients;
        without it a removed ticker lingers in every open tab.
        """
        with self._lock:
            removed = self._prices.pop(ticker, None)
            self._open_prices.pop(ticker, None)
            if removed is not None:
                self._version += 1

    @property
    def version(self) -> int:
        """Current version counter. Useful for SSE change detection."""
        return self._version

    def __len__(self) -> int:
        with self._lock:
            return len(self._prices)

    def __contains__(self, ticker: str) -> bool:
        with self._lock:
            return ticker in self._prices
