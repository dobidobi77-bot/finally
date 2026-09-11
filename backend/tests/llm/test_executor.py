"""Auto-execution receipts: successes, validation failures, and surprises."""

from __future__ import annotations

from app.db.errors import InsufficientFunds
from app.llm import deps
from app.llm.executor import execute_actions
from app.llm.schema import ChatResponse, TradeInstruction, WatchlistChange


async def test_successful_trade_receipt_carries_the_fill_price(store):
    response = ChatResponse(message="ok", trades=[TradeInstruction(ticker="AAPL", side="buy", quantity=10)])
    receipts = await execute_actions(response)
    assert receipts == [
        {"type": "trade", "ticker": "AAPL", "side": "buy", "quantity": 10.0, "ok": True, "price": 190.5}
    ]
    assert store.trades == [("AAPL", "buy", 10.0)]


async def test_trade_validation_failure_becomes_an_ok_false_receipt(store):
    store.trade_error = InsufficientFunds("Insufficient cash")
    response = ChatResponse(message="ok", trades=[TradeInstruction(ticker="AAPL", side="buy", quantity=100000)])
    receipts = await execute_actions(response)
    assert receipts[0]["ok"] is False
    assert receipts[0]["error"] == "Insufficient cash"
    assert receipts[0]["ticker"] == "AAPL"


async def test_unexpected_trade_error_becomes_a_generic_receipt(store):
    store.trade_error = RuntimeError("database on fire")
    response = ChatResponse(message="ok", trades=[TradeInstruction(ticker="AAPL", side="buy", quantity=1)])
    receipts = await execute_actions(response)
    assert receipts[0]["ok"] is False
    assert "database on fire" not in receipts[0]["error"]


async def test_watchlist_add_and_remove_receipts(store):
    response = ChatResponse(
        message="ok",
        watchlist_changes=[
            WatchlistChange(ticker="PYPL", action="add"),
            WatchlistChange(ticker="TSLA", action="remove"),
        ],
    )
    receipts = await execute_actions(response)
    assert receipts == [
        {"type": "watchlist", "ticker": "PYPL", "action": "add", "ok": True},
        {"type": "watchlist", "ticker": "TSLA", "action": "remove", "ok": True},
    ]
    assert store.watchlist_calls == [("PYPL", "add"), ("TSLA", "remove")]


async def test_watchlist_failure_receipt(store):
    store.watchlist_error = InsufficientFunds("Invalid ticker format")
    response = ChatResponse(message="ok", watchlist_changes=[WatchlistChange(ticker="ZZZZZ", action="add")])
    receipts = await execute_actions(response)
    assert receipts[0] == {
        "type": "watchlist",
        "ticker": "ZZZZZ",
        "action": "add",
        "ok": False,
        "error": "Invalid ticker format",
    }


async def test_trades_run_before_watchlist_changes(store):
    response = ChatResponse(
        message="ok",
        trades=[TradeInstruction(ticker="AAPL", side="buy", quantity=1)],
        watchlist_changes=[WatchlistChange(ticker="PYPL", action="add")],
    )
    receipts = await execute_actions(response)
    assert [r["type"] for r in receipts] == ["trade", "watchlist"]


async def test_no_actions_means_no_receipts(store):
    assert await execute_actions(ChatResponse(message="just chatting")) == []


async def test_user_facing_errors_tolerates_missing_service_layer():
    """`app.services.errors` may not exist yet; the db errors must still be caught."""
    errors = deps.user_facing_errors()
    assert InsufficientFunds in errors
