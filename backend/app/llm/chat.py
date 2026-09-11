"""The two public entry points for the chat feature (INTERFACES.md section 3)."""

from __future__ import annotations

import logging

from app.llm import client, context, deps
from app.llm.executor import execute_actions
from app.llm.schema import ChatResponse

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 20
FAILURE_MESSAGE = (
    "I could not reach my language model just now, so I have not analysed anything "
    "or placed any trades. Please try again in a moment."
)


def _to_dict(stored) -> dict:
    """Render a stored `ChatMessage` as the HTTP body shape."""
    return {
        "id": stored.id,
        "role": stored.role,
        "content": stored.content,
        "actions": stored.actions,
        "created_at": stored.created_at,
    }


async def _respond(message: str) -> ChatResponse:
    """Build the prompt and get the model's reply.

    `LLM_MOCK=true` is handled inside `client.complete`, at the
    `litellm.acompletion` call and nowhere else (INTERFACES.md section 3.1), so
    this path is identical mocked or live.
    """
    history = await deps.list_chat_messages(limit=HISTORY_LIMIT)
    messages = await context.build_messages(history, message)
    return await client.complete(messages)


async def handle_chat(message: str) -> dict:
    """Run one full chat turn and return the stored assistant message.

    Persists the user message, asks the model, auto-executes whatever it asked
    for, then persists the assistant message with its action receipts. An LLM
    failure becomes an explanatory message with no actions - it never raises.

    An assistant message always stores a list, `[]` when nothing ran. `None`
    means a user message (INTERFACES.md section 1).
    """
    await deps.add_chat_message("user", message)
    try:
        response = await _respond(message)
    except Exception:
        logger.exception("Chat turn failed before any action was executed")
        return _to_dict(await deps.add_chat_message("assistant", FAILURE_MESSAGE, []))
    actions = await execute_actions(response)
    return _to_dict(await deps.add_chat_message("assistant", response.message, actions))


async def get_history(limit: int = HISTORY_LIMIT) -> dict:
    """Recent conversation, oldest first (BUILD_CONTRACT A6)."""
    messages = await deps.list_chat_messages(limit=limit)
    return {"messages": [_to_dict(m) for m in messages]}
