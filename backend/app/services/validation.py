"""Shared input validation for the service layer."""

from __future__ import annotations

import re

from .errors import ServiceError

TICKER_RE = re.compile(r"^[A-Z]{1,5}$")
VALID_SIDES = ("buy", "sell")


def normalize_ticker(ticker: object) -> str:
    """Uppercase and validate a ticker symbol (BUILD_CONTRACT A3).

    Raises ServiceError("Invalid ticker format") on anything that is not one to
    five ASCII letters.
    """
    if not isinstance(ticker, str):
        raise ServiceError("Invalid ticker format")
    symbol = ticker.strip().upper()
    if not TICKER_RE.match(symbol):
        raise ServiceError("Invalid ticker format")
    return symbol


def normalize_side(side: object) -> str:
    """Validate the trade side. Raises ServiceError on anything else."""
    if not isinstance(side, str) or side.strip().lower() not in VALID_SIDES:
        raise ServiceError("Side must be 'buy' or 'sell'")
    return side.strip().lower()


def normalize_quantity(quantity: object) -> float:
    """Validate quantity > 0 (BUILD_CONTRACT B3).

    Rejects zero, negative, non-numeric and non-finite values.
    """
    if isinstance(quantity, bool):
        raise ServiceError("Quantity must be a positive number")
    try:
        value = float(quantity)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ServiceError("Quantity must be a positive number") from None
    if value != value or value in (float("inf"), float("-inf")):
        raise ServiceError("Quantity must be a positive number")
    if value <= 0:
        raise ServiceError("Quantity must be greater than zero")
    return round(value, 6)
