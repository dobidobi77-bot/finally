# LLM chat integration

Two public functions, both in `chat.py` (INTERFACES.md section 3):

```python
await handle_chat(message)      # one full turn -> the stored assistant message
await get_history(limit=20)     # {"messages": [...]} oldest first
```

## Modules

| File | Role |
| --- | --- |
| `chat.py` | `handle_chat` / `get_history` - the only public surface |
| `schema.py` | `ChatResponse` pydantic model and `parse_response` |
| `context.py` | System prompt and prompt assembly |
| `client.py` | `litellm.acompletion` -> OpenRouter -> Cerebras, and the mock seam |
| `mock.py` | The `LLM_MOCK=true` stand-in for the model |
| `executor.py` | Auto-execution -> action receipts |
| `deps.py` | Lazy indirection over `app.services` and `app.db` |

## Mock mode

**INTERFACES.md section 3.1 is the source of truth for this table.** It is
reproduced here for convenience; if the two ever disagree, section 3.1 wins.

`LLM_MOCK=true` replaces the `litellm.acompletion` call and nothing else. The
seam is `client._acompletion`; everything downstream is byte-for-byte the live
path - the same JSON goes through the same `parse_response`, the same
`execute_actions`, the same `app.services` calls, the same persistence. So
`buy 99999 AAPL` really reaches `portfolio_service.execute_trade`, really fails
on cash, and really produces an `ok: false` receipt.

Patterns are matched against the user message, case-insensitive, first match
wins. Tickers are uppercased.

| Pattern | Payload | `message` |
| --- | --- | --- |
| `\bbuy\s+(\d+(?:\.\d+)?)\s+([A-Za-z]{1,5})\b` | `trades: [{ticker, side:"buy", quantity}]` | `Buying {qty} {TICKER}.` |
| `\bsell\s+(\d+(?:\.\d+)?)\s+([A-Za-z]{1,5})\b` | `trades: [{ticker, side:"sell", quantity}]` | `Selling {qty} {TICKER}.` |
| `\bwatch\s+([A-Za-z]{1,5})\b` | `watchlist_changes: [{ticker, action:"add"}]` | `Adding {TICKER} to the watchlist.` |
| `\bunwatch\s+([A-Za-z]{1,5})\b` | `watchlist_changes: [{ticker, action:"remove"}]` | `Removing {TICKER} from the watchlist.` |
| anything else | nothing | `Mock mode: no model was called. Ask me to buy, sell, watch or unwatch a ticker.` |

Notes for the E2E suite:

- The `message` text is fixed. It never contains a price or a portfolio figure,
  so it is safe to assert on. Fill prices and failures appear only in `actions`
  (BUILD_CONTRACT B6).
- A trade needs an explicit quantity. `buy AAPL` has none, so it falls through
  to the fallback reply.
- `buy 99999 AAPL` fails on cash from the $10,000 starting balance.
- `sell 5 AAPL` needs the shares to be held first; drive `buy 5 AAPL` before it.

## `actions` null vs empty

Per INTERFACES.md section 1: `None` is a user message, `[]` is an assistant turn
that executed nothing, `[{...}]` carries receipts. `handle_chat` always writes a
list for the assistant, including on the LLM-failure path.

## Action receipts

```json
{"type": "trade", "ok": true,  "ticker": "AAPL", "side": "buy", "quantity": 10, "price": 190.5}
{"type": "trade", "ok": false, "ticker": "AAPL", "side": "buy", "quantity": 10, "error": "Insufficient cash"}
{"type": "watchlist", "ok": true,  "ticker": "PYPL", "action": "add"}
{"type": "watchlist", "ok": false, "ticker": "ZZZZZZ", "action": "add", "error": "Invalid ticker format"}
```

## Real model

`openrouter/openai/gpt-oss-120b` with `extra_body={"provider": {"order": ["cerebras"]}}`,
called through `litellm.acompletion` with structured outputs. Never the
synchronous `completion` - it would block the event loop and freeze the SSE
price stream for every connected client (BUILD_CONTRACT section 6).
Needs `OPENROUTER_API_KEY`.
