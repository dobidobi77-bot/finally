"""Cash, positions, trades and portfolio snapshots."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import aiosqlite

from .connection import get_connection, transaction
from .errors import InsufficientFunds, InsufficientShares
from .init import utc_now
from .models import Position, Snapshot, Trade

# Money is stored as REAL, so rounding rules keep it from drifting (BUILD_CONTRACT B2).
CASH_DP = 2
QUANTITY_DP = 6
MIN_QUANTITY = 1e-6  # A position below this is closed, not left as 1e-15
_TOLERANCE = 1e-9  # Guards float comparisons in the funds/shares checks

SNAPSHOT_RETENTION_HOURS = 24


async def get_cash(*, user_id: str = "default") -> float:
    """Cash balance, or 0.0 when the profile does not exist."""
    conn = await get_connection()
    async with conn.execute(
        "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
    ) as cursor:
        row = await cursor.fetchone()
    return float(row["cash_balance"]) if row else 0.0


async def list_positions(*, user_id: str = "default") -> list[Position]:
    """All open positions, ticker ascending."""
    conn = await get_connection()
    async with conn.execute(
        "SELECT ticker, quantity, avg_cost, updated_at FROM positions"
        " WHERE user_id = ? ORDER BY ticker ASC",
        (user_id,),
    ) as cursor:
        rows = await cursor.fetchall()
    return [_to_position(row) for row in rows]


async def get_position(ticker: str, *, user_id: str = "default") -> Position | None:
    """One position, or None when the ticker is not held."""
    conn = await get_connection()
    async with conn.execute(
        "SELECT ticker, quantity, avg_cost, updated_at FROM positions"
        " WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ) as cursor:
        row = await cursor.fetchone()
    return _to_position(row) if row else None


async def execute_trade_tx(
    ticker: str,
    side: str,
    quantity: float,
    price: float,
    *,
    user_id: str = "default",
) -> Trade:
    """Fill a market order inside one transaction.

    Validates funds (buy) or held shares (sell) INSIDE the transaction, adjusts
    cash, upserts or deletes the position, and appends the trade row. Raises
    InsufficientFunds or InsufficientShares, leaving the database untouched.
    A sell never changes avg_cost (BUILD_CONTRACT B1).
    """
    side = side.lower()
    if side not in ("buy", "sell"):
        raise ValueError(f"Invalid side: {side}")

    quantity = round(float(quantity), QUANTITY_DP)
    price = float(price)
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero")
    if price <= 0:
        raise ValueError("Price must be greater than zero")

    async with transaction() as conn:
        cash = await _locked_cash(conn, user_id)
        position = await _locked_position(conn, user_id, ticker)
        now = utc_now()

        if side == "buy":
            cost = round(quantity * price, CASH_DP)
            if cost > cash + _TOLERANCE:
                raise InsufficientFunds(
                    f"Insufficient cash: {ticker} buy costs ${cost:,.2f}, "
                    f"available ${cash:,.2f}"
                )
            await _set_cash(conn, user_id, cash - cost)
            await _apply_buy(conn, user_id, ticker, quantity, price, position, now)
        else:
            held = position.quantity if position else 0.0
            if quantity > held + _TOLERANCE:
                raise InsufficientShares(
                    f"Insufficient shares: cannot sell {quantity:g} {ticker}, "
                    f"holding {held:g}"
                )
            proceeds = round(quantity * price, CASH_DP)
            await _set_cash(conn, user_id, cash + proceeds)
            await _apply_sell(conn, user_id, ticker, quantity, position, now)

        trade = Trade(
            id=str(uuid.uuid4()),
            ticker=ticker,
            side=side,
            quantity=quantity,
            price=price,
            executed_at=now,
        )
        await conn.execute(
            "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (trade.id, user_id, ticker, side, quantity, price, now),
        )
    return trade


async def list_trades(limit: int = 50, *, user_id: str = "default") -> list[Trade]:
    """The `limit` most recent trades, newest first."""
    conn = await get_connection()
    async with conn.execute(
        "SELECT id, ticker, side, quantity, price, executed_at FROM trades"
        " WHERE user_id = ? ORDER BY executed_at DESC, rowid DESC LIMIT ?",
        (user_id, limit),
    ) as cursor:
        rows = await cursor.fetchall()
    return [
        Trade(
            id=row["id"],
            ticker=row["ticker"],
            side=row["side"],
            quantity=float(row["quantity"]),
            price=float(row["price"]),
            executed_at=row["executed_at"],
        )
        for row in rows
    ]


async def record_snapshot(total_value: float, *, user_id: str = "default") -> None:
    """Insert a portfolio value snapshot and prune rows older than 24h."""
    async with transaction() as conn:
        await conn.execute(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at)"
            " VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), user_id, round(float(total_value), CASH_DP), utc_now()),
        )
        await conn.execute(
            "DELETE FROM portfolio_snapshots WHERE user_id = ? AND recorded_at < ?",
            (user_id, _retention_cutoff()),
        )


async def list_snapshots(*, user_id: str = "default") -> list[Snapshot]:
    """Snapshots from the last 24 hours, recorded_at ascending."""
    conn = await get_connection()
    async with conn.execute(
        "SELECT total_value, recorded_at FROM portfolio_snapshots"
        " WHERE user_id = ? AND recorded_at >= ? ORDER BY recorded_at ASC, rowid ASC",
        (user_id, _retention_cutoff()),
    ) as cursor:
        rows = await cursor.fetchall()
    return [
        Snapshot(total_value=float(row["total_value"]), recorded_at=row["recorded_at"])
        for row in rows
    ]


def _retention_cutoff() -> str:
    """ISO timestamp 24 hours ago; rows older than this are dropped."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=SNAPSHOT_RETENTION_HOURS)
    return cutoff.isoformat()


def _to_position(row: aiosqlite.Row) -> Position:
    return Position(
        ticker=row["ticker"],
        quantity=float(row["quantity"]),
        avg_cost=float(row["avg_cost"]),
        updated_at=row["updated_at"],
    )


async def _locked_cash(conn: aiosqlite.Connection, user_id: str) -> float:
    """Read the cash balance inside the open transaction."""
    async with conn.execute(
        "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
    ) as cursor:
        row = await cursor.fetchone()
    if row is None:
        raise ValueError(f"No profile for user {user_id!r}")
    return float(row["cash_balance"])


async def _locked_position(
    conn: aiosqlite.Connection, user_id: str, ticker: str
) -> Position | None:
    """Read the position inside the open transaction."""
    async with conn.execute(
        "SELECT ticker, quantity, avg_cost, updated_at FROM positions"
        " WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ) as cursor:
        row = await cursor.fetchone()
    return _to_position(row) if row else None


async def _set_cash(conn: aiosqlite.Connection, user_id: str, cash: float) -> None:
    await conn.execute(
        "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
        (round(cash, CASH_DP), user_id),
    )


async def _apply_buy(
    conn: aiosqlite.Connection,
    user_id: str,
    ticker: str,
    quantity: float,
    price: float,
    position: Position | None,
    now: str,
) -> None:
    """Insert the position or blend the new shares into its average cost."""
    if position is None:
        await conn.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), user_id, ticker, quantity, round(price, QUANTITY_DP), now),
        )
        return

    new_quantity = round(position.quantity + quantity, QUANTITY_DP)
    total_cost = position.quantity * position.avg_cost + quantity * price
    new_avg_cost = round(total_cost / new_quantity, QUANTITY_DP)
    await conn.execute(
        "UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ?"
        " WHERE user_id = ? AND ticker = ?",
        (new_quantity, new_avg_cost, now, user_id, ticker),
    )


async def _apply_sell(
    conn: aiosqlite.Connection,
    user_id: str,
    ticker: str,
    quantity: float,
    position: Position | None,
    now: str,
) -> None:
    """Reduce the position, deleting the row once it is effectively empty."""
    remaining = round((position.quantity if position else 0.0) - quantity, QUANTITY_DP)
    if remaining < MIN_QUANTITY:
        await conn.execute(
            "DELETE FROM positions WHERE user_id = ? AND ticker = ?", (user_id, ticker)
        )
        return
    await conn.execute(
        "UPDATE positions SET quantity = ?, updated_at = ? WHERE user_id = ? AND ticker = ?",
        (remaining, now, user_id, ticker),
    )
