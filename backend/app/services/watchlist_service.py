"""Watchlist reads and mutations, and the tracked-ticker set."""

from __future__ import annotations

import logging

from app import state
from app.db import repo_portfolio, repo_seeds, repo_watchlist
from app.market.seed_prices import DEFAULT_PARAMS, DEFAULT_SEED_PRICE
from app.market.seed_resolver import builtin_seed

from .validation import normalize_ticker

logger = logging.getLogger(__name__)


async def get_watchlist() -> dict:
    """Watchlist tickers with their latest cached prices, added_at ascending."""
    tickers = await repo_watchlist.list_watchlist()
    rows = []
    for ticker in tickers:
        update = state.price_cache.get(ticker)
        if update is None:
            rows.append(
                {
                    "ticker": ticker,
                    "price": None,
                    "previous_price": None,
                    "open_price": None,
                    "change": None,
                    "change_percent": None,
                    "direction": "flat",
                    "timestamp": None,
                }
            )
        else:
            rows.append(update.to_dict())
    return {"tickers": rows}


async def add_ticker(ticker: str) -> dict:
    """Persist a seed for an unknown symbol, add it to the watchlist and track it."""
    symbol = normalize_ticker(ticker)

    if builtin_seed(symbol) is None:
        await repo_seeds.upsert_ticker_seed(
            symbol, DEFAULT_SEED_PRICE, DEFAULT_PARAMS["mu"], DEFAULT_PARAMS["sigma"]
        )

    await repo_watchlist.add_to_watchlist(symbol)

    if state.market_source is not None:
        await state.market_source.add_ticker(symbol)

    return {"ok": True, "ticker": symbol}


async def remove_ticker(ticker: str) -> dict:
    """Remove from the watchlist, keeping the ticker tracked if a position is open."""
    symbol = normalize_ticker(ticker)
    await repo_watchlist.remove_from_watchlist(symbol)

    # BUILD_CONTRACT A2: an open position must keep its price feed.
    position = await repo_portfolio.get_position(symbol)
    if position is None or position.quantity <= 0:
        if state.market_source is not None:
            await state.market_source.remove_ticker(symbol)

    return {"ok": True}


async def tracked_tickers() -> list[str]:
    """Watchlist union the tickers with a non-zero position (BUILD_CONTRACT A2)."""
    tickers = list(await repo_watchlist.list_watchlist())
    seen = set(tickers)
    for position in await repo_portfolio.list_positions():
        if position.quantity > 0 and position.ticker not in seen:
            seen.add(position.ticker)
            tickers.append(position.ticker)
    return tickers
