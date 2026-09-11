"""`handle_chat` and `get_history` - the whole turn, with the service layer faked."""

from __future__ import annotations

import pytest

from app.llm import chat, client, context
from app.llm.chat import FAILURE_MESSAGE, HISTORY_LIMIT, get_history, handle_chat
from app.llm.mock import FALLBACK_MESSAGE


@pytest.fixture
def no_network(monkeypatch):
    """Fail loudly if anything reaches litellm. Mock mode must never get here."""

    async def explode(messages):
        raise AssertionError("litellm.acompletion must not be called in mock mode")

    monkeypatch.setattr(client, "_acompletion", explode)


@pytest.fixture
def fake_model(monkeypatch):
    """Replace only the network call, exactly as LLM_MOCK does."""
    captured: dict = {}

    def respond_with(raw: str):
        async def fake(messages):
            captured["messages"] = messages
            return raw

        monkeypatch.setattr(client, "_acompletion", fake)
        return captured

    return respond_with


async def test_mock_mode_returns_without_calling_the_model(store, mock_mode, no_network):
    result = await handle_chat("how am I doing?")
    assert result["role"] == "assistant"
    assert result["content"] == FALLBACK_MESSAGE
    assert result["actions"] == []
    assert result["id"] and result["created_at"]


async def test_mock_mode_persists_user_then_assistant(store, mock_mode, no_network):
    await handle_chat("hello there")
    assert (store.messages[0].role, store.messages[0].content) == ("user", "hello there")
    assert store.messages[1].role == "assistant"
    assert len(store.messages) == 2


async def test_mock_buy_executes_through_the_service_layer(store, mock_mode, no_network):
    result = await handle_chat("buy 5 AAPL")
    assert store.trades == [("AAPL", "buy", 5.0)]
    assert result["content"] == "Buying 5 AAPL."
    assert result["actions"] == [
        {"type": "trade", "ticker": "AAPL", "side": "buy", "quantity": 5.0, "ok": True, "price": 190.5}
    ]


async def test_mock_failed_trade_reaches_the_service_layer_and_fails_there(store, mock_mode, no_network):
    """The over-large buy must really be attempted, not faked into a receipt."""
    from app.db.errors import InsufficientFunds

    store.trade_error = InsufficientFunds("Insufficient cash")
    result = await handle_chat("buy 99999 AAPL")

    assert store.trades == [("AAPL", "buy", 99999.0)]
    assert result["content"] == "Buying 99999 AAPL."
    assert result["actions"][0]["ok"] is False
    assert result["actions"][0]["error"] == "Insufficient cash"
    assert "insufficient" not in result["content"].lower()


async def test_mock_watch_executes(store, mock_mode, no_network):
    result = await handle_chat("watch PYPL")
    assert store.watchlist_calls == [("PYPL", "add")]
    assert result["actions"][0] == {"type": "watchlist", "ticker": "PYPL", "action": "add", "ok": True}


async def test_mock_mode_still_builds_the_real_prompt(store, mock_mode, no_network):
    """Mock mode swaps the model, not the pipeline: context is still assembled."""
    await handle_chat("hello")
    assert store.history_calls == [HISTORY_LIMIT]
    assert store.portfolio_calls == 1
    assert store.watchlist_reads == 1


async def test_stored_actions_match_the_returned_actions(store, mock_mode, no_network):
    result = await handle_chat("buy 5 AAPL")
    assert store.messages[-1].actions == result["actions"]


async def test_real_path_sends_context_and_history(store, fake_model):
    captured = fake_model(
        '{"message": "Analysed.", "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 2}]}'
    )
    result = await handle_chat("what should I do?")

    assert [m["role"] for m in captured["messages"]][:2] == ["system", "system"]
    assert "FinAlly" in captured["messages"][0]["content"]
    assert "Cash: $5,000.00" in captured["messages"][1]["content"]
    assert captured["messages"][-1] == {"role": "user", "content": "what should I do?"}
    assert result["content"] == "Analysed."
    assert store.trades == [("AAPL", "buy", 2.0)]


async def test_history_window_is_bounded_to_twenty(store, fake_model):
    fake_model('{"message": "ok"}')
    for i in range(30):
        await store.add_chat_message("user", f"message {i}")
    await handle_chat("the newest one")

    assert HISTORY_LIMIT == 20
    assert store.history_calls == [20]


async def test_malformed_model_reply_degrades_gracefully(store, fake_model):
    fake_model("{not json at all")
    result = await handle_chat("buy 5 AAPL")
    assert result["content"] == FAILURE_MESSAGE
    assert result["actions"] == []
    assert store.trades == []


async def test_network_failure_returns_a_message_with_no_actions(store, monkeypatch):
    async def boom(messages):
        raise RuntimeError("openrouter is down")

    monkeypatch.setattr(client, "_acompletion", boom)
    result = await handle_chat("buy 5 AAPL")

    assert result["content"] == FAILURE_MESSAGE
    assert result["actions"] == []
    assert store.messages[-1].role == "assistant"


async def test_failure_path_persists_an_empty_list_not_none(store, monkeypatch):
    """`[]` means the assistant did nothing; `None` would mean a user message."""

    async def boom(messages):
        raise RuntimeError("openrouter is down")

    monkeypatch.setattr(client, "_acompletion", boom)
    await handle_chat("hello")

    assert store.messages[-1].actions == []
    assert store.messages[-1].actions is not None
    assert store.messages[0].actions is None


async def test_context_failure_also_degrades_gracefully(store, monkeypatch, mock_mode):
    async def boom():
        raise RuntimeError("price cache not ready")

    monkeypatch.setattr(chat.deps, "get_portfolio", boom)
    result = await handle_chat("hello")
    assert result["content"] == FAILURE_MESSAGE


async def test_get_history_returns_messages_oldest_first(store):
    await store.add_chat_message("user", "first")
    await store.add_chat_message("assistant", "second", [])
    result = await get_history()

    assert [m["content"] for m in result["messages"]] == ["first", "second"]
    assert set(result["messages"][0]) == {"id", "role", "content", "actions", "created_at"}


async def test_get_history_passes_its_limit_through(store):
    await get_history(limit=5)
    assert store.history_calls == [5]


async def test_empty_history_still_sends_the_user_message(store, monkeypatch, fake_model):
    captured = fake_model('{"message": "ok"}')

    async def empty_history(limit: int = 20):
        return []

    monkeypatch.setattr(chat.deps, "list_chat_messages", empty_history)
    await handle_chat("standalone question")
    assert captured["messages"][-1] == {"role": "user", "content": "standalone question"}


def test_context_renders_an_empty_portfolio():
    text = context.format_context({"cash": 10000.0, "total_value": 10000.0, "unrealized_pnl": 0.0}, {})
    assert "Positions: none" in text
    assert "Watchlist: empty" in text
