"""Resolve simulator seed prices, persisting them for unknown tickers.

BUILD_CONTRACT A3: a symbol with no entry in `seed_prices.py` gets 100.00 and
default GBM parameters, stored in the `ticker_seeds` table so the same ticker
starts at the same price after a restart.
"""

from __future__ import annotations

import logging

from .seed_prices import DEFAULT_PARAMS, DEFAULT_SEED_PRICE, SEED_PRICES, TICKER_PARAMS

logger = logging.getLogger(__name__)


def builtin_seed(ticker: str) -> dict[str, float] | None:
    """The compiled-in seed for a ticker, or None if it is unknown."""
    if ticker not in SEED_PRICES:
        return None
    params = TICKER_PARAMS.get(ticker, DEFAULT_PARAMS)
    return {
        "seed_price": SEED_PRICES[ticker],
        "mu": params["mu"],
        "sigma": params["sigma"],
    }


async def resolve_seed(ticker: str) -> dict[str, float]:
    """Seed parameters for one ticker: built-in, else stored, else persisted new.

    Falls back to the in-memory default if the database is unavailable, so the
    simulator still runs.
    """
    known = builtin_seed(ticker)
    if known is not None:
        return known

    default = {
        "seed_price": DEFAULT_SEED_PRICE,
        "mu": DEFAULT_PARAMS["mu"],
        "sigma": DEFAULT_PARAMS["sigma"],
    }
    try:
        from app.db import repo_seeds

        stored = await repo_seeds.get_ticker_seed(ticker)
        if stored is None:
            stored = await repo_seeds.upsert_ticker_seed(
                ticker, DEFAULT_SEED_PRICE, DEFAULT_PARAMS["mu"], DEFAULT_PARAMS["sigma"]
            )
        return {
            "seed_price": stored.seed_price,
            "mu": stored.drift,
            "sigma": stored.volatility,
        }
    except Exception:
        logger.warning("Ticker seed lookup failed for %s; using default", ticker, exc_info=True)
        return default


async def resolve_seeds(tickers: list[str]) -> dict[str, dict[str, float]]:
    """Seed parameters for a batch of tickers."""
    return {ticker: await resolve_seed(ticker) for ticker in tickers}
