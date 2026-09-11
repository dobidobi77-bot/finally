"""Chat history. `actions` is stored as a JSON string, decoded on read."""

from __future__ import annotations

import json
import uuid

from .connection import get_connection, transaction
from .init import utc_now
from .models import ChatMessage


async def list_chat_messages(limit: int = 20, *, user_id: str = "default") -> list[ChatMessage]:
    """The `limit` most recent messages, returned oldest first."""
    conn = await get_connection()
    async with conn.execute(
        "SELECT id, role, content, actions, created_at FROM chat_messages"
        " WHERE user_id = ? ORDER BY created_at DESC, rowid DESC LIMIT ?",
        (user_id, limit),
    ) as cursor:
        rows = await cursor.fetchall()
    return [_to_message(row) for row in reversed(rows)]


async def add_chat_message(
    role: str,
    content: str,
    actions: list | None = None,
    *,
    user_id: str = "default",
) -> ChatMessage:
    """Append one message and return it as stored."""
    if role not in ("user", "assistant"):
        raise ValueError(f"Invalid role: {role}")

    message = ChatMessage(
        id=str(uuid.uuid4()),
        role=role,
        content=content,
        actions=actions,
        created_at=utc_now(),
    )
    async with transaction() as conn:
        await conn.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                message.id,
                user_id,
                message.role,
                message.content,
                json.dumps(actions) if actions is not None else None,
                message.created_at,
            ),
        )
    return message


def _to_message(row) -> ChatMessage:
    return ChatMessage(
        id=row["id"],
        role=row["role"],
        content=row["content"],
        actions=json.loads(row["actions"]) if row["actions"] else None,
        created_at=row["created_at"],
    )
