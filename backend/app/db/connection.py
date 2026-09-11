"""aiosqlite connection handling.

One shared connection per process. SQLite is single-writer, so every write goes
through `transaction()`, which serialises callers with an asyncio lock and wraps
the body in a single BEGIN IMMEDIATE ... COMMIT.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import aiosqlite

# db/finally.db relative to the project root (this file is backend/app/db/connection.py)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DB_PATH = _PROJECT_ROOT / "db" / "finally.db"

_db_path: Path | None = None
_conn: aiosqlite.Connection | None = None
_write_lock = asyncio.Lock()


def resolve_db_path(db_path: str | None = None) -> Path:
    """Explicit argument wins, then the DB_PATH env var, then db/finally.db."""
    if db_path:
        return Path(db_path)
    env_path = os.getenv("DB_PATH")
    if env_path:
        return Path(env_path)
    return _DEFAULT_DB_PATH


async def set_db_path(db_path: str | None = None) -> Path:
    """Point the layer at a database file, closing any connection to another one."""
    global _db_path
    path = resolve_db_path(db_path).resolve()
    if _db_path is not None and path != _db_path:
        await close_connection()
    _db_path = path
    return path


async def get_connection() -> aiosqlite.Connection:
    """The shared connection, opened on first use with the required pragmas."""
    global _conn
    if _conn is None:
        path = _db_path or await set_db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        # isolation_level=None: no implicit transactions, `transaction()` is explicit.
        _conn = await aiosqlite.connect(str(path), isolation_level=None)
        _conn.row_factory = aiosqlite.Row
        await _conn.execute("PRAGMA journal_mode = WAL")
        await _conn.execute("PRAGMA busy_timeout = 5000")
        await _conn.execute("PRAGMA foreign_keys = ON")
    return _conn


@asynccontextmanager
async def transaction() -> AsyncIterator[aiosqlite.Connection]:
    """Run the body inside one write transaction; roll back on any exception."""
    conn = await get_connection()
    async with _write_lock:
        await conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except BaseException:
            await conn.rollback()
            raise
        await conn.commit()


async def close_connection() -> None:
    """Close the shared connection. Safe to call when nothing is open."""
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None
