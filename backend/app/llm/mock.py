"""The `LLM_MOCK=true` stand-in for the model itself.

The contract is frozen in INTERFACES.md section 3.1 - the patterns, the
first-match-wins order and the exact `message` strings all come from there, not
from a choice made here.

This replaces the `litellm.acompletion` call and nothing else: it returns the
same JSON payload a real model would return, so parsing, auto-execution through
`app.services`, receipt building and persistence all run unchanged.

Triggers are parametric so the E2E suite can drive any ticker and any quantity
without a new branch here. **The mock never validates anything** - it only
decides what the model would have said. Every verdict comes from the service
layer, which is why the ticker capture is `{1,10}` rather than A3's `{1,5}`: an
over-long symbol must reach `watchlist_service.add_ticker` and be rejected there
with the real error, exactly as an over-large buy must reach `execute_trade` and
really fail on cash.
"""

from __future__ import annotations

import json
import os
import re

FALLBACK_MESSAGE = (
    "Mock mode: no model was called. Ask me to buy, sell, watch or unwatch a ticker."
)

_BUY = re.compile(r"\bbuy\s+(\d+(?:\.\d+)?)\s+([A-Za-z]{1,10})\b", re.IGNORECASE)
_SELL = re.compile(r"\bsell\s+(\d+(?:\.\d+)?)\s+([A-Za-z]{1,10})\b", re.IGNORECASE)
_WATCH = re.compile(r"\bwatch\s+([A-Za-z]{1,10})\b", re.IGNORECASE)
_UNWATCH = re.compile(r"\bunwatch\s+([A-Za-z]{1,10})\b", re.IGNORECASE)


def mock_enabled() -> bool:
    """Read the flag at call time so tests and the E2E run can set it."""
    return os.getenv("LLM_MOCK", "").strip().lower() == "true"


def mock_payload(message: str) -> str:
    """Return the JSON a real model would have returned for `message`.

    Patterns are tried in the order fixed by INTERFACES.md section 3.1; the
    first match wins. Tickers are uppercased. The `message` text is fixed and
    carries no live prices or portfolio figures, so E2E can assert on it - fill
    prices and failures live in `actions` only (BUILD_CONTRACT B6).
    """
    text = message or ""

    match = _BUY.search(text)
    if match:
        return _trade(match, "buy", "Buying")

    match = _SELL.search(text)
    if match:
        return _trade(match, "sell", "Selling")

    match = _WATCH.search(text)
    if match:
        return _watchlist(match, "add", "Adding {ticker} to the watchlist.")

    match = _UNWATCH.search(text)
    if match:
        return _watchlist(match, "remove", "Removing {ticker} from the watchlist.")

    return json.dumps({"message": FALLBACK_MESSAGE, "trades": [], "watchlist_changes": []})


def _trade(match: re.Match, side: str, verb: str) -> str:
    """Build the payload for a buy or sell match."""
    quantity, ticker = match.group(1), match.group(2).upper()
    return json.dumps(
        {
            "message": f"{verb} {quantity} {ticker}.",
            "trades": [{"ticker": ticker, "side": side, "quantity": float(quantity)}],
            "watchlist_changes": [],
        }
    )


def _watchlist(match: re.Match, action: str, template: str) -> str:
    """Build the payload for a watch or unwatch match."""
    ticker = match.group(1).upper()
    return json.dumps(
        {
            "message": template.format(ticker=ticker),
            "trades": [],
            "watchlist_changes": [{"ticker": ticker, "action": action}],
        }
    )
