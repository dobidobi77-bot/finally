"""Fakes for the service and repository layers the LLM module calls.

Those layers belong to other roles and may not exist yet, so every test patches
the single seam in `app.llm.deps` rather than importing them.
"""

from __future__ import annotations

import pytest

from app.db.models import ChatMessage
from app.llm import deps


class FakeStore:
    """Records what the LLM module persisted and what it executed."""

    def __init__(self) -> None:
        self.messages: list[ChatMessage] = []
        self.history_calls: list[int] = []
        self.trades: list[tuple[str, str, float]] = []
        self.watchlist_calls: list[tuple[str, str]] = []
        self.portfolio_calls = 0
        self.watchlist_reads = 0
        self.trade_error: Exception | None = None
        self.watchlist_error: Exception | None = None
        self.fill_price: float = 190.5

    async def add_chat_message(self, role, content, actions=None):
        message = ChatMessage(
            id=f"msg-{len(self.messages)}",
            role=role,
            content=content,
            actions=actions,
            created_at="2026-09-11T00:00:00Z",
        )
        self.messages.append(message)
        return message

    async def list_chat_messages(self, limit: int = 20):
        self.history_calls.append(limit)
        return self.messages[-limit:]

    async def execute_trade(self, ticker, side, quantity):
        self.trades.append((ticker, side, quantity))
        if self.trade_error is not None:
            raise self.trade_error
        return {
            "ok": True,
            "trade": {"ticker": ticker, "side": side, "quantity": quantity, "price": self.fill_price},
            "portfolio": {},
        }

    async def add_ticker(self, ticker):
        self.watchlist_calls.append((ticker, "add"))
        if self.watchlist_error is not None:
            raise self.watchlist_error
        return {"ok": True, "ticker": ticker}

    async def remove_ticker(self, ticker):
        self.watchlist_calls.append((ticker, "remove"))
        if self.watchlist_error is not None:
            raise self.watchlist_error
        return {"ok": True}

    async def get_portfolio(self):
        self.portfolio_calls += 1
        return {
            "cash": 5000.0,
            "total_value": 10500.0,
            "unrealized_pnl": 500.0,
            "positions": [
                {
                    "ticker": "AAPL",
                    "quantity": 10,
                    "avg_cost": 180.0,
                    "current_price": 190.0,
                    "unrealized_pnl": 100.0,
                    "pnl_percent": 5.56,
                }
            ],
        }

    async def get_watchlist(self):
        self.watchlist_reads += 1
        return {"tickers": [{"ticker": "AAPL", "price": 190.0, "change_percent": 1.2}]}


@pytest.fixture
def store(monkeypatch) -> FakeStore:
    """Patch every `deps` function onto a FakeStore."""
    fake = FakeStore()
    for name in (
        "add_chat_message",
        "list_chat_messages",
        "execute_trade",
        "add_ticker",
        "remove_ticker",
        "get_portfolio",
        "get_watchlist",
    ):
        monkeypatch.setattr(deps, name, getattr(fake, name))
    return fake


@pytest.fixture
def mock_mode(monkeypatch):
    """Turn on LLM_MOCK for the duration of a test."""
    monkeypatch.setenv("LLM_MOCK", "true")


@pytest.fixture(autouse=True)
def no_mock_by_default(monkeypatch):
    """Tests opt in to mock mode; the ambient environment must not leak in."""
    monkeypatch.delenv("LLM_MOCK", raising=False)
