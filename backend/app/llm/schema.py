"""Structured output schema for the chat response (PLAN.md section 9).

The model is asked to return JSON matching `ChatResponse`. Parsing is
deliberately forgiving about shape noise - unknown fields are ignored, an
explicit `null` for a list means "none", tickers are upper-cased - but strict
about the one field that must exist: `message`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator


class LLMResponseError(Exception):
    """Raised when the model reply is not valid `ChatResponse` JSON."""


class TradeInstruction(BaseModel):
    """One trade the assistant wants executed."""

    ticker: str
    side: Literal["buy", "sell"]
    quantity: float

    @field_validator("ticker", mode="before")
    @classmethod
    def _normalise_ticker(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("side", mode="before")
    @classmethod
    def _normalise_side(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class WatchlistChange(BaseModel):
    """One add/remove the assistant wants applied to the watchlist."""

    ticker: str
    action: Literal["add", "remove"]

    @field_validator("ticker", mode="before")
    @classmethod
    def _normalise_ticker(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("action", mode="before")
    @classmethod
    def _normalise_action(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class ChatResponse(BaseModel):
    """The whole model reply: prose plus the actions to auto-execute."""

    message: str
    trades: list[TradeInstruction] = Field(default_factory=list)
    watchlist_changes: list[WatchlistChange] = Field(default_factory=list)

    @field_validator("trades", "watchlist_changes", mode="before")
    @classmethod
    def _null_is_empty(cls, value: object) -> object:
        """An explicit `null` from the model means an empty list, not an error."""
        return [] if value is None else value


def parse_response(raw: str | None) -> ChatResponse:
    """Parse a raw model reply into a `ChatResponse`.

    Raises `LLMResponseError` for empty, non-JSON, or schema-violating replies.
    """
    if raw is None or not raw.strip():
        raise LLMResponseError("The model returned an empty response")
    try:
        return ChatResponse.model_validate_json(raw)
    except ValidationError as exc:
        raise LLMResponseError(f"The model returned malformed JSON: {exc.error_count()} problem(s)") from exc
