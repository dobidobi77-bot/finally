"""The frozen LLM_MOCK contract (INTERFACES.md section 3.1)."""

from __future__ import annotations

import json

import pytest

from app.llm.mock import FALLBACK_MESSAGE, mock_enabled, mock_payload
from app.llm.schema import parse_response


def payload(message: str) -> dict:
    """The mock output as a dict, so tests assert on the payload the model sends."""
    return json.loads(mock_payload(message))


def test_fallback_has_no_actions_and_fixed_text():
    result = payload("how is my portfolio doing?")
    assert result["message"] == FALLBACK_MESSAGE
    assert result["trades"] == []
    assert result["watchlist_changes"] == []


def test_buy_pattern():
    result = payload("buy 10 AAPL")
    assert result["message"] == "Buying 10 AAPL."
    assert result["trades"] == [{"ticker": "AAPL", "side": "buy", "quantity": 10.0}]
    assert result["watchlist_changes"] == []


def test_sell_pattern():
    result = payload("sell 3 TSLA")
    assert result["message"] == "Selling 3 TSLA."
    assert result["trades"] == [{"ticker": "TSLA", "side": "sell", "quantity": 3.0}]


def test_fractional_quantity():
    result = payload("buy 2.5 nvda")
    assert result["message"] == "Buying 2.5 NVDA."
    assert result["trades"][0]["quantity"] == 2.5


def test_watch_pattern():
    result = payload("watch pypl")
    assert result["message"] == "Adding PYPL to the watchlist."
    assert result["watchlist_changes"] == [{"ticker": "PYPL", "action": "add"}]
    assert result["trades"] == []


def test_unwatch_pattern():
    result = payload("unwatch TSLA")
    assert result["message"] == "Removing TSLA from the watchlist."
    assert result["watchlist_changes"] == [{"ticker": "TSLA", "action": "remove"}]


def test_unwatch_is_not_shadowed_by_watch():
    """`\bwatch` cannot match inside "unwatch" - there is no word boundary there."""
    assert payload("unwatch aapl")["watchlist_changes"][0]["action"] == "remove"


def test_first_match_wins_buy_before_sell():
    result = payload("buy 1 AAPL then sell 1 MSFT")
    assert result["trades"] == [{"ticker": "AAPL", "side": "buy", "quantity": 1.0}]


def test_first_match_wins_trade_before_watchlist():
    result = payload("buy 1 AAPL and watch MSFT")
    assert result["trades"][0]["ticker"] == "AAPL"
    assert result["watchlist_changes"] == []


def test_tickers_are_uppercased():
    assert payload("buy 1 aapl")["trades"][0]["ticker"] == "AAPL"
    assert payload("WATCH pypl")["watchlist_changes"][0]["ticker"] == "PYPL"


def test_patterns_are_case_insensitive():
    assert payload("BUY 10 AAPL")["message"] == "Buying 10 AAPL."


def test_quantity_is_required_for_a_trade():
    """"buy AAPL" has no quantity, so it is not a trade instruction."""
    assert payload("buy AAPL")["message"] == FALLBACK_MESSAGE


def test_over_large_buy_is_a_normal_trade_payload():
    """The failure must come from the real service layer, not from the mock."""
    result = payload("buy 99999 AAPL")
    assert result["trades"] == [{"ticker": "AAPL", "side": "buy", "quantity": 99999.0}]
    assert "insufficient" not in result["message"].lower()


def test_over_long_symbol_passes_straight_through():
    """`{1,10}`, not A3's `{1,5}`: the service layer must be the one to reject it."""
    result = payload("watch ZZZZZZ")
    assert result["watchlist_changes"] == [{"ticker": "ZZZZZZ", "action": "add"}]
    assert "invalid" not in result["message"].lower()


def test_over_long_symbol_in_a_trade_passes_through_too():
    result = payload("buy 1 ZZZZZZ")
    assert result["trades"] == [{"ticker": "ZZZZZZ", "side": "buy", "quantity": 1.0}]


@pytest.mark.parametrize(
    "message,ticker,quantity",
    [("buy 1 GOOGL", "GOOGL", 1.0), ("buy 99999 GOOGL", "GOOGL", 99999.0), ("buy 0.5 V", "V", 0.5)],
)
def test_triggers_are_parametric_over_ticker_and_quantity(message, ticker, quantity):
    """Any ticker, any quantity - the suite drives scenarios with no mock change."""
    trade = payload(message)["trades"][0]
    assert (trade["ticker"], trade["quantity"]) == (ticker, quantity)


def test_fallback_message_carries_no_live_figures():
    assert "$" not in FALLBACK_MESSAGE


@pytest.mark.parametrize("message", ["buy 10 AAPL", "watch PYPL", "hello"])
def test_mock_output_parses_as_a_real_model_reply(message):
    """The mock returns exactly what the parser expects from the real model."""
    assert parse_response(mock_payload(message)).message


@pytest.mark.parametrize("message", ["buy 10 AAPL", "watch PYPL", "hello"])
def test_mock_is_deterministic(message):
    assert mock_payload(message) == mock_payload(message)


def test_empty_message_falls_back():
    assert payload("")["message"] == FALLBACK_MESSAGE


def test_mock_enabled_reads_the_flag_at_call_time(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "TRUE")
    assert mock_enabled() is True
    monkeypatch.setenv("LLM_MOCK", "false")
    assert mock_enabled() is False
    monkeypatch.delenv("LLM_MOCK")
    assert mock_enabled() is False
