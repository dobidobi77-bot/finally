"""Frozen row models returned by the repositories (INTERFACES.md section 1)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Position:
    """One open holding. `avg_cost` is the weighted average buy price."""

    ticker: str
    quantity: float
    avg_cost: float
    updated_at: str


@dataclass(frozen=True, slots=True)
class Trade:
    """One executed fill, append-only."""

    id: str
    ticker: str
    side: str  # "buy" | "sell"
    quantity: float
    price: float
    executed_at: str


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Total portfolio value at a point in time, for the P&L chart."""

    total_value: float
    recorded_at: str


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """One chat turn. `actions` is already JSON-decoded; None for user messages."""

    id: str
    role: str  # "user" | "assistant"
    content: str
    actions: list | None
    created_at: str


@dataclass(frozen=True, slots=True)
class TickerSeed:
    """Persisted simulator parameters for a ticker (BUILD_CONTRACT A3)."""

    ticker: str
    seed_price: float
    drift: float
    volatility: float
