"""Auto-execution of the actions the model asked for.

Every attempt produces a receipt, success or failure. The model writes its prose
before these run, so the receipts are the authoritative record of what happened
(BUILD_CONTRACT B6) - a failure is a receipt, never an exception.
"""

from __future__ import annotations

import logging

from app.llm import deps
from app.llm.schema import ChatResponse, TradeInstruction, WatchlistChange

logger = logging.getLogger(__name__)


async def execute_actions(response: ChatResponse) -> list[dict]:
    """Run every trade then every watchlist change, returning their receipts."""
    receipts = [await _run_trade(trade) for trade in response.trades]
    receipts += [await _run_watchlist_change(change) for change in response.watchlist_changes]
    return receipts


async def _run_trade(trade: TradeInstruction) -> dict:
    """Execute one trade through the shared service function."""
    receipt = {
        "type": "trade",
        "ticker": trade.ticker,
        "side": trade.side,
        "quantity": trade.quantity,
    }
    try:
        result = await deps.execute_trade(trade.ticker, trade.side, trade.quantity)
    except deps.user_facing_errors() as exc:
        return {**receipt, "ok": False, "error": str(exc)}
    except Exception:
        logger.exception("Unexpected failure executing trade for %s", trade.ticker)
        return {**receipt, "ok": False, "error": "Trade failed unexpectedly"}
    filled = (result or {}).get("trade") or {}
    return {**receipt, "ok": True, "price": filled.get("price")}


async def _run_watchlist_change(change: WatchlistChange) -> dict:
    """Apply one watchlist add or remove through the shared service function."""
    receipt = {"type": "watchlist", "ticker": change.ticker, "action": change.action}
    try:
        if change.action == "add":
            await deps.add_ticker(change.ticker)
        else:
            await deps.remove_ticker(change.ticker)
    except deps.user_facing_errors() as exc:
        return {**receipt, "ok": False, "error": str(exc)}
    except Exception:
        logger.exception("Unexpected failure changing watchlist for %s", change.ticker)
        return {**receipt, "ok": False, "error": "Watchlist change failed unexpectedly"}
    return {**receipt, "ok": True}
