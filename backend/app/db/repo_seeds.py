"""Persisted simulator seeds so an unknown ticker keeps one price across restarts.

Without this the simulator picks a random seed price per process, and an open
position in that ticker is revalued at a different number after every restart
(BUILD_CONTRACT A3).
"""

from __future__ import annotations

from .connection import get_connection, transaction
from .init import utc_now
from .models import TickerSeed


async def get_ticker_seed(ticker: str) -> TickerSeed | None:
    """The stored seed for a ticker, or None when it has never been seeded."""
    conn = await get_connection()
    async with conn.execute(
        "SELECT ticker, seed_price, drift, volatility FROM ticker_seeds WHERE ticker = ?",
        (ticker,),
    ) as cursor:
        row = await cursor.fetchone()
    if row is None:
        return None
    return TickerSeed(
        ticker=row["ticker"],
        seed_price=float(row["seed_price"]),
        drift=float(row["drift"]),
        volatility=float(row["volatility"]),
    )


async def upsert_ticker_seed(
    ticker: str, seed_price: float, drift: float, volatility: float
) -> TickerSeed:
    """Insert the seed, or overwrite the stored parameters if it already exists.

    `created_at` is preserved on overwrite. Callers that want a seed to stay
    fixed should check `get_ticker_seed` first.
    """
    seed = TickerSeed(
        ticker=ticker,
        seed_price=float(seed_price),
        drift=float(drift),
        volatility=float(volatility),
    )
    async with transaction() as conn:
        await conn.execute(
            "INSERT INTO ticker_seeds (ticker, seed_price, drift, volatility, created_at)"
            " VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(ticker) DO UPDATE SET"
            " seed_price = excluded.seed_price,"
            " drift = excluded.drift,"
            " volatility = excluded.volatility",
            (seed.ticker, seed.seed_price, seed.drift, seed.volatility, utc_now()),
        )
    return seed
