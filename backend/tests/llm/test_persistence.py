"""Chat persistence against the real database.

These use the real `repo_chat`, not the fake, because the point is the
null-vs-empty convention in INTERFACES.md section 1 surviving a round trip
through SQLite: `None` is a user message, `[]` is an assistant turn that
executed nothing.
"""

from __future__ import annotations

import pytest

from app.db.init import close_db, init_db
from app.llm import client
from app.llm.chat import get_history, handle_chat


@pytest.fixture(autouse=True)
async def real_db(tmp_path, monkeypatch):
    """A fresh temp database, with the service layer stubbed out."""
    await init_db(str(tmp_path / "finally.db"))

    async def no_positions():
        return {"cash": 10000.0, "total_value": 10000.0, "unrealized_pnl": 0.0, "positions": []}

    async def empty_watchlist():
        return {"tickers": []}

    from app.llm import deps

    monkeypatch.setattr(deps, "get_portfolio", no_positions)
    monkeypatch.setattr(deps, "get_watchlist", empty_watchlist)
    yield
    await close_db()


async def test_assistant_turn_with_no_actions_round_trips_as_empty_list(mock_mode):
    """`[]` must survive to SQLite and back, distinguishable from the user's None."""
    await handle_chat("hello there")
    messages = (await get_history())["messages"]

    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["actions"] is None
    assert messages[1]["actions"] == []
    assert messages[1]["actions"] is not None


async def test_failed_turn_round_trips_as_empty_list(monkeypatch):
    async def boom(messages):
        raise RuntimeError("openrouter is down")

    monkeypatch.setattr(client, "_acompletion", boom)
    await handle_chat("hello there")
    messages = (await get_history())["messages"]

    assert messages[1]["actions"] == []


async def test_receipts_round_trip_through_sqlite(mock_mode, monkeypatch):
    from app.llm import deps

    async def add_ticker(ticker):
        return {"ok": True, "ticker": ticker}

    monkeypatch.setattr(deps, "add_ticker", add_ticker)
    await handle_chat("watch PYPL")
    messages = (await get_history())["messages"]

    assert messages[1]["actions"] == [
        {"type": "watchlist", "ticker": "PYPL", "action": "add", "ok": True}
    ]


async def test_history_survives_across_turns(mock_mode):
    await handle_chat("first question")
    await handle_chat("second question")
    contents = [m["content"] for m in (await get_history())["messages"]]

    assert contents[0] == "first question"
    assert contents[2] == "second question"
    assert len(contents) == 4
