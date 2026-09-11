"""Indirection over the service and repository layers.

Those modules are owned by other roles and are imported at call time rather
than at import time, so `app.llm` stays importable while they are still being
built. It also gives the tests one seam to patch instead of six.

Every mutation here goes through the same service function the manual HTTP
endpoints use (BUILD_CONTRACT B3). There is no second execution path.
"""

from __future__ import annotations

import importlib
from typing import Any

from app.db.errors import InsufficientFunds, InsufficientShares


def _module(path: str) -> Any:
    """Import a module by dotted path. `importlib` caches, so this is cheap."""
    return importlib.import_module(path)


async def get_portfolio() -> dict:
    """Cash, positions with P&L, total value, unrealized P&L."""
    return await _module("app.services.portfolio_service").get_portfolio()


async def execute_trade(ticker: str, side: str, quantity: float) -> dict:
    """Execute a market order through the shared service function."""
    return await _module("app.services.portfolio_service").execute_trade(ticker, side, quantity)


async def get_watchlist() -> dict:
    """Watchlist tickers with their latest cached prices."""
    return await _module("app.services.watchlist_service").get_watchlist()


async def add_ticker(ticker: str) -> dict:
    """Add a ticker to the watchlist and to market-data tracking."""
    return await _module("app.services.watchlist_service").add_ticker(ticker)


async def remove_ticker(ticker: str) -> dict:
    """Remove a ticker from the watchlist."""
    return await _module("app.services.watchlist_service").remove_ticker(ticker)


async def list_chat_messages(limit: int = 20) -> list:
    """The `limit` most recent chat messages, oldest first."""
    return await _module("app.db.repo_chat").list_chat_messages(limit=limit)


async def add_chat_message(role: str, content: str, actions: list | None = None):
    """Persist one chat message and return the stored `ChatMessage`."""
    return await _module("app.db.repo_chat").add_chat_message(role, content, actions)


def user_facing_errors() -> tuple[type[BaseException], ...]:
    """Exception types whose `str()` is safe to put in an action receipt.

    `ServiceError` is resolved lazily because `app.services` may not exist yet.
    """
    errors: list[type[BaseException]] = [InsufficientFunds, InsufficientShares]
    try:
        errors.append(_module("app.services.errors").ServiceError)
    except (ImportError, AttributeError):
        pass
    return tuple(errors)
