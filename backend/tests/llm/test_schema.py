"""Structured output parsing: every valid shape, and every way it can be wrong."""

from __future__ import annotations

import json

import pytest

from app.llm.schema import ChatResponse, LLMResponseError, parse_response


def test_parses_message_only():
    result = parse_response(json.dumps({"message": "Hello"}))
    assert result.message == "Hello"
    assert result.trades == []
    assert result.watchlist_changes == []


def test_parses_full_schema():
    raw = json.dumps(
        {
            "message": "Buying and watching.",
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
            "watchlist_changes": [{"ticker": "PYPL", "action": "add"}],
        }
    )
    result = parse_response(raw)
    assert result.trades[0].ticker == "AAPL"
    assert result.trades[0].side == "buy"
    assert result.trades[0].quantity == 10
    assert result.watchlist_changes[0].action == "add"


def test_parses_sell_and_remove():
    raw = json.dumps(
        {
            "message": "Trimming.",
            "trades": [{"ticker": "TSLA", "side": "sell", "quantity": 2.5}],
            "watchlist_changes": [{"ticker": "TSLA", "action": "remove"}],
        }
    )
    result = parse_response(raw)
    assert result.trades[0].side == "sell"
    assert result.trades[0].quantity == 2.5
    assert result.watchlist_changes[0].action == "remove"


def test_explicit_null_lists_become_empty():
    raw = json.dumps({"message": "Nothing to do.", "trades": None, "watchlist_changes": None})
    result = parse_response(raw)
    assert result.trades == []
    assert result.watchlist_changes == []


def test_unknown_fields_are_ignored():
    raw = json.dumps({"message": "Hi", "confidence": 0.9, "trades": [], "notes": ["x"]})
    assert parse_response(raw).message == "Hi"


def test_ticker_and_side_are_normalised():
    raw = json.dumps({"message": "ok", "trades": [{"ticker": " aapl ", "side": "BUY", "quantity": 1}]})
    trade = parse_response(raw).trades[0]
    assert trade.ticker == "AAPL"
    assert trade.side == "buy"


def test_missing_message_is_rejected():
    with pytest.raises(LLMResponseError):
        parse_response(json.dumps({"trades": []}))


def test_malformed_json_is_rejected():
    with pytest.raises(LLMResponseError):
        parse_response("{not json at all")


def test_empty_response_is_rejected():
    with pytest.raises(LLMResponseError):
        parse_response("   ")


def test_none_response_is_rejected():
    with pytest.raises(LLMResponseError):
        parse_response(None)


def test_invalid_side_is_rejected():
    with pytest.raises(LLMResponseError):
        parse_response(json.dumps({"message": "x", "trades": [{"ticker": "AAPL", "side": "short", "quantity": 1}]}))


def test_invalid_watchlist_action_is_rejected():
    with pytest.raises(LLMResponseError):
        parse_response(json.dumps({"message": "x", "watchlist_changes": [{"ticker": "AAPL", "action": "star"}]}))


def test_response_model_is_json_schema_serialisable():
    """LiteLLM structured outputs needs a JSON schema for the model."""
    schema = ChatResponse.model_json_schema()
    assert "message" in schema["properties"]
    assert schema["required"] == ["message"]
