"""The model call: LiteLLM -> OpenRouter -> Cerebras inference.

`LLM_MOCK=true` swaps out `litellm.acompletion` and nothing else (INTERFACES.md
section 3.1). Both paths hand the same raw JSON to the same parser, so
everything downstream is identical.

Always `acompletion`. The synchronous `completion` blocks the event loop, which
freezes the SSE price stream for every connected client for the whole turn
(BUILD_CONTRACT section 6).
"""

from __future__ import annotations

from app.llm import mock
from app.llm.schema import ChatResponse, parse_response

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}
REASONING_EFFORT = "low"


def _last_user_text(messages: list[dict]) -> str:
    """The most recent user turn - all the mock needs to pick a response."""
    for entry in reversed(messages):
        if entry.get("role") == "user":
            return entry.get("content") or ""
    return ""


async def _acompletion(messages: list[dict]) -> str | None:
    """The one network call. Isolated so tests can prove mock mode never runs it."""
    import litellm  # imported lazily: it is slow and mock mode never needs it

    response = await litellm.acompletion(
        model=MODEL,
        messages=messages,
        response_format=ChatResponse,
        reasoning_effort=REASONING_EFFORT,
        extra_body=EXTRA_BODY,
    )
    return response.choices[0].message.content


async def complete(messages: list[dict]) -> ChatResponse:
    """Get the model's structured reply and parse it.

    Raises `LLMResponseError` if the reply does not match the schema, and
    whatever LiteLLM raises on a transport or auth failure. `handle_chat` turns
    both into a user-facing message.
    """
    if mock.mock_enabled():
        raw = mock.mock_payload(_last_user_text(messages))
    else:
        raw = await _acompletion(messages)
    return parse_response(raw)
