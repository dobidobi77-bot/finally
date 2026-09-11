"""Chat message persistence, ordering and the history window."""

import pytest

from app.db import repo_chat


async def test_user_message_round_trips_with_no_actions():
    await repo_chat.add_chat_message("user", "How is my portfolio?")

    messages = await repo_chat.list_chat_messages()
    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].content == "How is my portfolio?"
    assert messages[0].actions is None


async def test_assistant_actions_are_json_decoded_on_read():
    actions = [{"type": "trade", "ok": True, "ticker": "AAPL", "side": "buy", "quantity": 10}]
    await repo_chat.add_chat_message("assistant", "Bought 10 AAPL.", actions)

    stored = (await repo_chat.list_chat_messages())[0]
    assert stored.actions == actions


async def test_history_is_oldest_first():
    for i in range(3):
        await repo_chat.add_chat_message("user", f"message {i}")

    contents = [m.content for m in await repo_chat.list_chat_messages()]
    assert contents == ["message 0", "message 1", "message 2"]


async def test_limit_keeps_the_most_recent_messages_still_oldest_first():
    for i in range(5):
        await repo_chat.add_chat_message("user", f"message {i}")

    contents = [m.content for m in await repo_chat.list_chat_messages(limit=2)]
    assert contents == ["message 3", "message 4"]


async def test_default_limit_is_twenty():
    for i in range(25):
        await repo_chat.add_chat_message("user", f"message {i}")

    messages = await repo_chat.list_chat_messages()
    assert len(messages) == 20
    assert messages[0].content == "message 5"


async def test_invalid_role_is_rejected():
    with pytest.raises(ValueError):
        await repo_chat.add_chat_message("system", "nope")


async def test_history_is_isolated_per_user():
    await repo_chat.add_chat_message("user", "mine")
    await repo_chat.add_chat_message("user", "theirs", user_id="other")

    assert [m.content for m in await repo_chat.list_chat_messages()] == ["mine"]
    assert [m.content for m in await repo_chat.list_chat_messages(user_id="other")] == ["theirs"]
