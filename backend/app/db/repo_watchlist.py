"""Watchlist membership. Ordering is added_at ascending (BUILD_CONTRACT B11)."""

from __future__ import annotations

import uuid

from .connection import get_connection, transaction
from .init import utc_now


async def list_watchlist(*, user_id: str = "default") -> list[str]:
    """Watched tickers, oldest addition first.

    The ten seeded tickers share one timestamp, so rowid breaks the tie and
    keeps the seed order stable.
    """
    conn = await get_connection()
    async with conn.execute(
        "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at ASC, rowid ASC",
        (user_id,),
    ) as cursor:
        rows = await cursor.fetchall()
    return [row["ticker"] for row in rows]


async def add_to_watchlist(ticker: str, *, user_id: str = "default") -> bool:
    """Add a ticker. Returns False if it is already watched (not an error)."""
    async with transaction() as conn:
        cursor = await conn.execute(
            "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at)"
            " VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), user_id, ticker, utc_now()),
        )
        return cursor.rowcount > 0


async def remove_from_watchlist(ticker: str, *, user_id: str = "default") -> bool:
    """Remove a ticker. Returns False if it was not on the watchlist."""
    async with transaction() as conn:
        cursor = await conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?", (user_id, ticker)
        )
        return cursor.rowcount > 0
