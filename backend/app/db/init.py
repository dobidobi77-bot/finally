"""Database lifecycle: create the schema and seed defaults. Idempotent."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from .connection import close_connection, get_connection, set_db_path

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")

DEFAULT_USER_ID = "default"
DEFAULT_CASH_BALANCE = 10000.0
DEFAULT_WATCHLIST: tuple[str, ...] = (
    "AAPL",
    "GOOGL",
    "MSFT",
    "AMZN",
    "TSLA",
    "NVDA",
    "META",
    "JPM",
    "V",
    "NFLX",
)


def utc_now() -> str:
    """Current UTC time as an ISO-8601 string. Used for every timestamp column."""
    return datetime.now(timezone.utc).isoformat()


async def init_db(db_path: str | None = None) -> None:
    """Create the schema if missing and seed defaults. Safe to call repeatedly.

    db_path defaults to the DB_PATH env var, else db/finally.db under the project
    root. Seeding is gated on the database being NEW, not on each table being
    empty: the profile insert decides, and the watchlist is seeded only alongside
    it. Gating the two independently would re-seed the ten default tickers on the
    next startup after a user removed them all, silently undoing their choice.
    """
    await set_db_path(db_path)
    conn = await get_connection()
    await conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
    if await _seed_user(conn):
        await _seed_watchlist(conn)
    await conn.commit()


async def close_db() -> None:
    """Close pooled connections. Called from lifespan shutdown."""
    await close_connection()


async def _seed_user(conn: aiosqlite.Connection) -> bool:
    """Insert the default profile with $10,000 cash. True if it was inserted.

    A False return means the database already existed, which is what tells
    init_db to leave the watchlist alone.
    """
    async with conn.execute("SELECT COUNT(*) AS n FROM users_profile") as cursor:
        row = await cursor.fetchone()
    if row["n"]:
        return False
    await conn.execute(
        "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
        (DEFAULT_USER_ID, DEFAULT_CASH_BALANCE, utc_now()),
    )
    return True


async def _seed_watchlist(conn: aiosqlite.Connection) -> None:
    """Insert the ten default tickers. Only called for a new database."""
    now = utc_now()
    await conn.executemany(
        "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
        [(str(uuid.uuid4()), DEFAULT_USER_ID, ticker, now) for ticker in DEFAULT_WATCHLIST],
    )
