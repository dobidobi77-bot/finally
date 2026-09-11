"""Trade execution, positions, cash and snapshots."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db import repo_portfolio
from app.db.connection import get_connection
from app.db.errors import InsufficientFunds, InsufficientShares


async def test_buy_debits_cash_and_opens_a_position():
    trade = await repo_portfolio.execute_trade_tx("AAPL", "buy", 10, 190.0)

    assert trade.side == "buy"
    assert trade.quantity == 10
    assert await repo_portfolio.get_cash() == 8100.0

    position = await repo_portfolio.get_position("AAPL")
    assert position.quantity == 10
    assert position.avg_cost == 190.0


async def test_sell_credits_cash_and_reduces_the_position():
    await repo_portfolio.execute_trade_tx("AAPL", "buy", 10, 190.0)
    await repo_portfolio.execute_trade_tx("AAPL", "sell", 4, 200.0)

    assert await repo_portfolio.get_cash() == 8900.0
    position = await repo_portfolio.get_position("AAPL")
    assert position.quantity == 6


async def test_sell_does_not_change_avg_cost():
    await repo_portfolio.execute_trade_tx("AAPL", "buy", 10, 190.0)
    await repo_portfolio.execute_trade_tx("AAPL", "sell", 4, 500.0)

    position = await repo_portfolio.get_position("AAPL")
    assert position.avg_cost == 190.0


async def test_second_buy_recalculates_avg_cost():
    await repo_portfolio.execute_trade_tx("AAPL", "buy", 10, 190.0)
    await repo_portfolio.execute_trade_tx("AAPL", "buy", 5, 200.0)

    position = await repo_portfolio.get_position("AAPL")
    assert position.quantity == 15
    assert position.avg_cost == pytest.approx(193.333333, abs=1e-6)


async def test_selling_the_whole_position_deletes_the_row():
    await repo_portfolio.execute_trade_tx("AAPL", "buy", 10, 190.0)
    await repo_portfolio.execute_trade_tx("AAPL", "sell", 10, 195.0)

    assert await repo_portfolio.get_position("AAPL") is None
    assert await repo_portfolio.list_positions() == []


async def test_fractional_sells_to_zero_leave_no_dust_position():
    """Repeated fractional sells must not leave a 1e-15 residual (BUILD_CONTRACT B2)."""
    await repo_portfolio.execute_trade_tx("AAPL", "buy", 0.3, 100.0)
    for _ in range(3):
        await repo_portfolio.execute_trade_tx("AAPL", "sell", 0.1, 100.0)

    assert await repo_portfolio.get_position("AAPL") is None


async def test_fractional_quantities_are_supported():
    await repo_portfolio.execute_trade_tx("AAPL", "buy", 2.5, 100.0)

    position = await repo_portfolio.get_position("AAPL")
    assert position.quantity == 2.5
    assert await repo_portfolio.get_cash() == 9750.0


async def test_insufficient_cash_is_rejected_and_changes_nothing():
    with pytest.raises(InsufficientFunds):
        await repo_portfolio.execute_trade_tx("NVDA", "buy", 100, 800.0)

    assert await repo_portfolio.get_cash() == 10000.0
    assert await repo_portfolio.get_position("NVDA") is None
    assert await repo_portfolio.list_trades() == []


async def test_insufficient_shares_is_rejected_and_changes_nothing():
    await repo_portfolio.execute_trade_tx("AAPL", "buy", 5, 100.0)

    with pytest.raises(InsufficientShares):
        await repo_portfolio.execute_trade_tx("AAPL", "sell", 6, 100.0)

    assert await repo_portfolio.get_cash() == 9500.0
    assert (await repo_portfolio.get_position("AAPL")).quantity == 5
    assert len(await repo_portfolio.list_trades()) == 1


async def test_selling_a_ticker_never_held_is_rejected():
    with pytest.raises(InsufficientShares):
        await repo_portfolio.execute_trade_tx("TSLA", "sell", 1, 250.0)


async def test_buying_the_exact_cash_balance_is_allowed():
    await repo_portfolio.execute_trade_tx("AAPL", "buy", 100, 100.0)

    assert await repo_portfolio.get_cash() == 0.0


@pytest.mark.parametrize("quantity", [0, -1, -0.5])
async def test_non_positive_quantity_is_rejected(quantity):
    with pytest.raises(ValueError):
        await repo_portfolio.execute_trade_tx("AAPL", "buy", quantity, 100.0)


async def test_invalid_side_is_rejected():
    with pytest.raises(ValueError):
        await repo_portfolio.execute_trade_tx("AAPL", "hold", 1, 100.0)


async def test_side_is_case_insensitive():
    trade = await repo_portfolio.execute_trade_tx("AAPL", "BUY", 1, 100.0)
    assert trade.side == "buy"


async def test_list_positions_is_ticker_ordered():
    await repo_portfolio.execute_trade_tx("TSLA", "buy", 1, 100.0)
    await repo_portfolio.execute_trade_tx("AAPL", "buy", 1, 100.0)

    assert [p.ticker for p in await repo_portfolio.list_positions()] == ["AAPL", "TSLA"]


async def test_list_trades_is_newest_first_and_honours_the_limit():
    for i in range(3):
        await repo_portfolio.execute_trade_tx("AAPL", "buy", 1, 100.0 + i)

    trades = await repo_portfolio.list_trades(limit=2)
    assert len(trades) == 2
    assert trades[0].price == 102.0
    assert trades[1].price == 101.0


async def test_positions_are_isolated_per_user():
    await repo_portfolio.execute_trade_tx("AAPL", "buy", 1, 100.0)

    assert await repo_portfolio.list_positions(user_id="default") != []
    assert await repo_portfolio.get_cash(user_id="someone-else") == 0.0


async def test_snapshots_round_trip_in_time_order():
    await repo_portfolio.record_snapshot(10000.0)
    await repo_portfolio.record_snapshot(10500.5)

    snapshots = await repo_portfolio.list_snapshots()
    assert [s.total_value for s in snapshots] == [10000.0, 10500.5]


async def test_snapshots_older_than_24h_are_pruned_on_write():
    old = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    conn = await get_connection()
    await conn.execute(
        "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at)"
        " VALUES (?, ?, ?, ?)",
        (str(uuid.uuid4()), "default", 1.0, old),
    )
    assert len(await _all_snapshot_rows()) == 1

    await repo_portfolio.record_snapshot(10000.0)

    rows = await _all_snapshot_rows()
    assert len(rows) == 1
    assert rows[0]["total_value"] == 10000.0


async def _all_snapshot_rows():
    conn = await get_connection()
    async with conn.execute("SELECT total_value, recorded_at FROM portfolio_snapshots") as cursor:
        return await cursor.fetchall()


async def test_concurrent_buys_do_not_overdraw_cash():
    """The transaction lock must serialise reads and writes of the cash balance."""
    results = await asyncio.gather(
        *(repo_portfolio.execute_trade_tx("AAPL", "buy", 10, 300.0) for _ in range(4)),
        return_exceptions=True,
    )

    assert sum(isinstance(r, InsufficientFunds) for r in results) == 1
    assert await repo_portfolio.get_cash() == 1000.0
    assert (await repo_portfolio.get_position("AAPL")).quantity == 30
