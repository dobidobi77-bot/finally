"""Portfolio reads, trade execution, and value snapshots.

The single trade path: the manual HTTP route and the LLM both call
`execute_trade` (BUILD_CONTRACT B3).
"""

from __future__ import annotations

import asyncio
import logging

from app import state
from app.db import repo_portfolio
from app.db.errors import InsufficientFunds, InsufficientShares

from .errors import ServiceError
from .validation import normalize_quantity, normalize_side, normalize_ticker

logger = logging.getLogger(__name__)

FIRST_PRICE_TIMEOUT = 2.0  # seconds to wait for a newly tracked ticker's first tick
FIRST_PRICE_POLL = 0.05


async def get_portfolio() -> dict:
    """Cash, positions valued at live prices, total value and unrealized P&L."""
    cash = await repo_portfolio.get_cash()
    positions = await repo_portfolio.list_positions()

    rows = []
    holdings_value = 0.0
    total_pnl = 0.0
    for position in positions:
        # No cached price yet means the position values at cost — never at zero.
        current_price = state.price_cache.get_price(position.ticker) or position.avg_cost
        market_value = position.quantity * current_price
        pnl = (current_price - position.avg_cost) * position.quantity
        pnl_percent = (
            (current_price - position.avg_cost) / position.avg_cost * 100
            if position.avg_cost
            else 0.0
        )
        holdings_value += market_value
        total_pnl += pnl
        rows.append(
            {
                "ticker": position.ticker,
                "quantity": round(position.quantity, 6),
                "avg_cost": round(position.avg_cost, 2),
                "current_price": round(current_price, 2),
                "unrealized_pnl": round(pnl, 2),
                "pnl_percent": round(pnl_percent, 2),
            }
        )

    return {
        "cash": round(cash, 2),
        "positions": rows,
        "total_value": round(cash + holdings_value, 2),
        "unrealized_pnl": round(total_pnl, 2),
    }


async def execute_trade(ticker: str, side: str, quantity: float) -> dict:
    """Validate, fill at the cached price, persist, and snapshot.

    Raises ServiceError on any validation, funds or shares failure.
    """
    symbol = normalize_ticker(ticker)
    trade_side = normalize_side(side)
    qty = normalize_quantity(quantity)

    price = await _price_for_trade(symbol)

    try:
        trade = await repo_portfolio.execute_trade_tx(symbol, trade_side, qty, price)
    except (InsufficientFunds, InsufficientShares) as e:
        raise ServiceError(str(e)) from e

    await snapshot_now()

    return {
        "ok": True,
        "trade": {
            "id": trade.id,
            "ticker": trade.ticker,
            "side": trade.side,
            "quantity": trade.quantity,
            "price": trade.price,
            "executed_at": trade.executed_at,
        },
        "portfolio": await get_portfolio(),
    }


async def get_history() -> dict:
    """Portfolio value snapshots for the last 24 hours, oldest first."""
    snapshots = await repo_portfolio.list_snapshots()
    return {
        "snapshots": [
            {"total_value": s.total_value, "recorded_at": s.recorded_at} for s in snapshots
        ]
    }


async def snapshot_now() -> None:
    """Compute total portfolio value and record a snapshot."""
    portfolio = await get_portfolio()
    await repo_portfolio.record_snapshot(portfolio["total_value"])


async def _price_for_trade(symbol: str) -> float:
    """Current price for a fill, adding the ticker to tracking if needed.

    BUILD_CONTRACT A4: wait up to 2s for a first tick, then fail loudly rather
    than filling at zero.
    """
    price = state.price_cache.get_price(symbol)
    if price:
        return price

    try:
        await state.get_market_source().add_ticker(symbol)
    except RuntimeError as e:
        raise ServiceError(f"No price available for {symbol}") from e

    deadline = asyncio.get_running_loop().time() + FIRST_PRICE_TIMEOUT
    while asyncio.get_running_loop().time() < deadline:
        price = state.price_cache.get_price(symbol)
        if price:
            return price
        await asyncio.sleep(FIRST_PRICE_POLL)

    raise ServiceError(f"No price available for {symbol}")
