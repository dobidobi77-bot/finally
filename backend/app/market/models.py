"""Data models for market data."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PriceUpdate:
    """Immutable snapshot of a single ticker's price at a point in time.

    `previous_price` is the price one tick ago and drives the flash animation.
    `open_price` is the session baseline set when the ticker was first tracked
    and drives the daily change % (BUILD_CONTRACT A1). When omitted it defaults
    to `price`, which is correct for a ticker's very first update.
    """

    ticker: str
    price: float
    previous_price: float
    open_price: float | None = None
    timestamp: float = field(default_factory=time.time)  # Unix seconds

    def __post_init__(self) -> None:
        if self.open_price is None:
            object.__setattr__(self, "open_price", self.price)

    @property
    def change(self) -> float:
        """Absolute price change from previous update."""
        return round(self.price - self.previous_price, 4)

    @property
    def change_percent(self) -> float:
        """Percentage change from previous update."""
        if self.previous_price == 0:
            return 0.0
        return round((self.price - self.previous_price) / self.previous_price * 100, 4)

    @property
    def direction(self) -> str:
        """'up', 'down', or 'flat'."""
        if self.price > self.previous_price:
            return "up"
        elif self.price < self.previous_price:
            return "down"
        return "flat"

    def to_dict(self) -> dict:
        """Serialize for JSON / SSE transmission."""
        return {
            "ticker": self.ticker,
            "price": self.price,
            "previous_price": self.previous_price,
            "open_price": self.open_price,
            "timestamp": self.timestamp,
            "change": self.change,
            "change_percent": self.change_percent,
            "direction": self.direction,
        }
