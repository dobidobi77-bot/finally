# Build Contract — Agent Team

Authoritative decisions for the build. This file closes the open questions in
`PLAN.md` section 13. **Where this file and PLAN.md disagree, this file wins.**
Do not re-litigate a decision here; if one is genuinely wrong, message the team
lead rather than deviating silently.

---

## 1. File ownership

Two agents editing one file overwrite each other. Each role owns its paths
exclusively. To change a file you do not own, message its owner.

| Role | Owns |
| --- | --- |
| **db-engineer** | `backend/app/db/**`, `backend/tests/db/**` |
| **backend-engineer** | `backend/app/api/**`, `backend/app/services/**`, `backend/app/market/**`, `backend/app/main.py`, `backend/tests/api/**`, `backend/tests/market/**` |
| **llm-engineer** | `backend/app/llm/**`, `backend/tests/llm/**` |
| **frontend-engineer** | `frontend/**` |
| **devops-engineer** | `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `scripts/**`, `.env.example` |
| **integration-tester** | `test/**` |

**Contended files.** `backend/pyproject.toml` is owned by **backend-engineer
only**. Need a dependency? Message backend-engineer with the package and why.
`planning/**` is owned by the **team lead** only.

---

## 2. Build order

Work that can start immediately is marked **now**. Everything else names what it
waits on.

1. **db-engineer — now.** Schema, migrations, connection helper, repositories.
2. **backend-engineer — now.** Fix the two known bugs (section 5), then services
   and routes once the DB layer lands.
3. **frontend-engineer — now.** Layout, components, styling against mocked data.
   Wire to real endpoints once backend publishes them.
4. **llm-engineer — after** backend services expose trade and watchlist
   functions. Build the mock path (`LLM_MOCK=true`) first so it is testable
   without an API key.
5. **devops-engineer — now** for `.env.example` and `.dockerignore`; Dockerfile
   after the frontend build command is known.
6. **integration-tester — now** for harness setup; write specs against the API
   contract in section 4, run them once the app boots.

---

## 3. Settled decisions

These close PLAN.md section 13.

### A1. Daily change % — backend supplies the baseline

`PriceCache` gains an `open_price` per ticker, set when the ticker is first
tracked (simulator: its seed price; Massive: the daily-bar open). It is included
in every SSE payload. The frontend renders
`(price - open_price) / open_price * 100`.

Chosen over a frontend page-load baseline so the number survives a refresh and
is identical across tabs.

### A2. Tracked ticker set

`tracked = watchlist ∪ {tickers with a non-zero position}`. Removing a ticker
from the watchlist never stops tracking it while a position is open.

### A3. Unknown tickers

Accept any symbol matching `^[A-Z]{1,5}$`. Anything else is rejected with
`400 {"error": "Invalid ticker format"}`.

An accepted symbol with no entry in `seed_prices.py` gets a seed price of
`100.00` and default GBM parameters, **persisted to the `ticker_seeds` table**.
The current code assigns `random.uniform(50, 300)` per process, so the same
ticker is repriced on every restart and open positions are revalued at a random
number. Persisting the seed fixes that.

### A4. Trading a ticker with no cached price

Valid format and not tracked: add it to tracking, wait up to 2 seconds for the
first tick, then fill. Still no price after 2 seconds: `400 {"error": "No price
available for TICKER"}`. Never fill at 0.

### A5. SSE contract

One unnamed event whose `data` is a JSON object keyed by ticker. Emitted only
when the cache version changes. `retry: 1000` on connect. A `: keepalive`
comment every 15 seconds so proxies do not close an idle stream.

```
retry: 1000

data: {"AAPL":{"ticker":"AAPL","price":190.5,"previous_price":190.4,"open_price":189.0,"timestamp":1757000000.0,"change":0.1,"change_percent":0.05,"direction":"up"},...}

: keepalive
```

### A6. Bootstrap and history

`GET /api/chat?limit=20` returns recent messages, oldest first. The frontend
calls it on page load so a refresh does not lose the conversation.

The main chart accumulates points from SSE since page load. **No price-history
endpoint** — the backend stores no price history. The chart is empty on first
render and fills in; that is expected.

### B1. Realized P&L

A sell does not change `avg_cost`. Realized P&L is derivable from the `trades`
log but is **not surfaced in the UI**. Only unrealized P&L is shown.

### B2. Money precision

Columns are SQLite `REAL`. Round cash to 2 decimal places on write, quantity to
6. Delete the position row when quantity `< 1e-6` so a fully sold position does
not linger as `1e-15`.

### B3. Trade validation

Quantity must be `> 0` — reject zero, negative, and non-numeric with `400`.
Buys validate against cash, sells against held quantity. **Manual and LLM trades
go through the identical service function.** No second code path.

### B4. Portfolio snapshots

Record a snapshot after every trade, and every 30 seconds **only while at least
one SSE client is connected**. Delete snapshots older than 24 hours on write.
`GET /api/portfolio/history` returns the last 24 hours.

### B5. Chat history window

Last 20 messages, for both the LLM prompt and `GET /api/chat`.

### B6. Trade results in chat

The LLM writes `message` before its trades execute, so its prose cannot report
fill prices or failures. The `actions` array is the authoritative receipt: the
frontend renders it as confirmation chips beneath the message, and failures
appear there. Do not add a second LLM call to narrate results.

### B7. Duplicate chat submissions

The frontend disables the input while a request is in flight. Trades
auto-execute with no confirmation, so a double submit would trade twice.

### B12. Colour tokens

```
--price-up:    #26a69a
--price-down:  #ef5350
--flash-up:    rgba(38, 166, 154, 0.25)
--flash-down:  rgba(239, 83, 80, 0.25)
```

Brand colours stay as PLAN.md section 2 defines them.

### B14. Health check

`GET /api/health` returns `{"status":"ok","market_source":"simulator"|"massive","cache_ready":true|false}`.
`cache_ready` is true once at least one price is cached. The integration tester
polls this for readiness instead of guessing at the UI.

### Simplifications adopted

- **C1** — `docker-compose.yml` is the supported path; scripts are thin wrappers.
  Name them `start.sh` / `stop.sh` / `start.ps1` / `stop.ps1`.
- **C2** — Playwright runs on the host against `http://localhost:8000`. No
  Playwright container, no `docker-compose.test.yml`.
- **C7** — No SSE reconnection E2E test. A unit test that the stream generator
  exits cleanly on client disconnect covers what this project owns.

---

## 4. API contract

Frontend and integration-tester build against this. Backend must match it.

| Method | Path | Body / Query | Returns |
| --- | --- | --- | --- |
| GET | `/api/health` | | `{status, market_source, cache_ready}` |
| GET | `/api/stream/prices` | | SSE, see A5 |
| GET | `/api/portfolio` | | `{cash, positions[], total_value, unrealized_pnl}` |
| POST | `/api/portfolio/trade` | `{ticker, quantity, side}` | `{ok, trade, portfolio}` or `400 {error}` |
| GET | `/api/portfolio/history` | | `{snapshots: [{total_value, recorded_at}]}` |
| GET | `/api/watchlist` | | `{tickers: [{ticker, price, open_price, ...}]}` |
| POST | `/api/watchlist` | `{ticker}` | `{ok, ticker}` or `400 {error}` |
| DELETE | `/api/watchlist/{ticker}` | | `{ok}` |
| GET | `/api/chat` | `?limit=20` | `{messages: [{id, role, content, actions, created_at}]}` |
| POST | `/api/chat` | `{message}` | `{id, role, content, actions, created_at}` |

Each position: `{ticker, quantity, avg_cost, current_price, unrealized_pnl, pnl_percent}`.

Errors are always `{"error": "<human readable>"}` with a 4xx status.

---

## 5. Known defects to fix

Found by review of the existing market subsystem. **backend-engineer owns both.**

**`backend/app/market/cache.py` — `remove()` does not bump `_version`.**
`update()` increments `_version` on every write but `remove()` only pops the
key. The SSE generator detects changes by version, so removing a ticker is never
pushed to clients and stale rows persist in other tabs. Add the increment and a
regression test.

**`backend/app/market/stream.py` — module-level router.** `router` is created at
module scope and `create_stream_router()` registers routes onto it, so a second
call double-registers `/api/stream/prices` and silently ignores the new
`price_cache`. Create the `APIRouter` inside the factory. The docstring claims
this pattern avoids globals; make that true.

---

## 6. Non-negotiable technical constraints

**Never block the event loop.** `litellm.completion` and the `sqlite3` driver
are synchronous. Called directly from an async route they freeze the SSE
generator for every connected client — prices stop moving for everyone for the
whole duration of a chat turn. Use `litellm.acompletion`, or wrap in
`asyncio.to_thread`. `backend/app/market/massive_client.py` already sets this
precedent; follow it.

**SQLite settings.** `PRAGMA journal_mode = WAL` and `PRAGMA busy_timeout = 5000`
on every connection. Wrap each trade (cash update, position upsert, trade row,
snapshot) in one transaction so a failure cannot leave cash debited with no
position.

**Startup, not lazy init.** Initialise the DB and start the market data source
in a FastAPI `lifespan` handler. `await source.start(tickers)` needs the
watchlist at startup, which the lazy-init-on-first-request approach in PLAN.md
section 7 cannot provide.

**Missing dependencies.** `backend/pyproject.toml` currently lacks `litellm`,
`httpx`, `python-dotenv`, and an async SQLite driver. backend-engineer adds
them; `rich` belongs in dev dependencies.

**Every role writes unit tests for its own code.** The existing suite is 73
tests passing — keep it green. Run `cd backend && uv run pytest` before
reporting a task complete. Python is managed with `uv`: `uv run`, never
`python`; `uv add`, never `pip install`.

---

## 7. Reporting

Mark a task complete only when its tests pass. If you are blocked by another
role, message that role directly and say what you need. If you find a defect in
someone else's area, message them — do not fix it yourself.
