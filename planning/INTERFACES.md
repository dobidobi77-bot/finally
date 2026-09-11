# Internal Interfaces — frozen signatures

Companion to `BUILD_CONTRACT.md`. That file defines the **HTTP** contract; this
one defines the **Python module** boundaries so roles can build in parallel
without negotiating.

**These signatures are frozen.** If one is genuinely wrong, message the team
lead. Do not change it unilaterally — another role is coding against it.

Team lead has already added every dependency to `backend/pyproject.toml`:
`litellm`, `httpx`, `python-dotenv`, `aiosqlite` (runtime) and `pytest`,
`pytest-asyncio`, `pytest-cov`, `pytest-httpx`, `ruff`, `rich` (dev).
Do not run `uv add` without asking the team lead first — it rewrites `uv.lock`
and races with other agents.

---

## 0. Shared app state — `backend/app/state.py`

Owned by **backend-engineer**. One module-level holder, created at import,
populated in the FastAPI `lifespan` handler.

```python
from app.market.cache import PriceCache
from app.market.interface import MarketDataSource

price_cache: PriceCache                    # always present, populated by the data source
market_source: MarketDataSource | None     # set in lifespan, None before startup

def get_market_source() -> MarketDataSource: ...   # raises RuntimeError if not started
def sse_client_count() -> int: ...                 # for B4 snapshot gating
```

Everything reads prices from `state.price_cache`. Nothing calls a data source
for a price.

---

## 1. Database layer — `backend/app/db/`

Owned by **db-engineer**. Suggested files: `schema.sql`, `connection.py`,
`init.py`, `repo_portfolio.py`, `repo_watchlist.py`, `repo_chat.py`,
`repo_seeds.py`, `models.py`, `errors.py`.

All functions are `async`. All take `user_id: str = "default"` as a keyword-only
argument. Callers never pass a connection — the layer manages it.

### Models — `app/db/models.py` (frozen dataclasses)

```python
@dataclass(frozen=True, slots=True)
class Position:
    ticker: str
    quantity: float
    avg_cost: float
    updated_at: str

@dataclass(frozen=True, slots=True)
class Trade:
    id: str
    ticker: str
    side: str          # "buy" | "sell"
    quantity: float
    price: float
    executed_at: str

@dataclass(frozen=True, slots=True)
class Snapshot:
    total_value: float
    recorded_at: str

@dataclass(frozen=True, slots=True)
class ChatMessage:
    id: str
    role: str          # "user" | "assistant"
    content: str
    actions: list | None    # already JSON-decoded; see the convention below
    created_at: str

@dataclass(frozen=True, slots=True)
class TickerSeed:
    ticker: str
    seed_price: float
    drift: float
    volatility: float
```

### `actions` null-vs-empty convention — frozen

`actions` distinguishes three states and all three are meaningful:

| Value | Meaning |
| --- | --- |
| `None` | a **user** message. Users never have actions. |
| `[]` | an **assistant** message that executed nothing. |
| `[{...}]` | an assistant message with receipts, successes and failures alike. |

An assistant turn that executed nothing must persist `[]`, never `None`, so the
frontend can tell "the assistant did nothing" from "this is a user message"
without inspecting `role`. This is a caller-side convention — the storage layer
stores whatever it is given. **llm-engineer** enforces it when writing the
assistant message; **frontend-engineer** may rely on it when rendering chips.

### Errors — `app/db/errors.py`

```python
class InsufficientFunds(Exception): ...    # str(e) is user-facing
class InsufficientShares(Exception): ...   # str(e) is user-facing
```

### Lifecycle — `app/db/init.py`

```python
async def init_db(db_path: str | None = None) -> None
    """Create schema if missing and seed defaults. Idempotent.

    db_path defaults to env DB_PATH, else "db/finally.db" relative to the
    project root. Applies PRAGMA journal_mode=WAL and busy_timeout=5000 on
    every connection. Seeds users_profile(default, 10000.0) and the 10 default
    watchlist tickers, only when those tables are empty.
    """

async def close_db() -> None
    """Close pooled connections. Called from lifespan shutdown."""
```

### Repositories

```python
# repo_portfolio.py
async def get_cash(*, user_id: str = "default") -> float
async def list_positions(*, user_id: str = "default") -> list[Position]
async def get_position(ticker: str, *, user_id: str = "default") -> Position | None

async def execute_trade_tx(
    ticker: str, side: str, quantity: float, price: float,
    *, user_id: str = "default",
) -> Trade
    """One transaction: validate, adjust cash, upsert/delete the position,
    insert the trade row. Raises InsufficientFunds or InsufficientShares
    (checked INSIDE the transaction). Rounds cash to 2dp, quantity to 6dp,
    deletes the position row when the resulting quantity < 1e-6. A sell never
    changes avg_cost."""

async def list_trades(limit: int = 50, *, user_id: str = "default") -> list[Trade]

async def record_snapshot(total_value: float, *, user_id: str = "default") -> None
    """Insert a snapshot and delete rows older than 24h."""

async def list_snapshots(*, user_id: str = "default") -> list[Snapshot]
    """Last 24 hours, recorded_at ascending."""

# repo_watchlist.py
async def list_watchlist(*, user_id: str = "default") -> list[str]
    """Tickers, added_at ascending (BUILD_CONTRACT B11)."""
async def add_to_watchlist(ticker: str, *, user_id: str = "default") -> bool
    """False if already present (no error)."""
async def remove_from_watchlist(ticker: str, *, user_id: str = "default") -> bool
    """False if not present."""

# repo_chat.py
async def list_chat_messages(limit: int = 20, *, user_id: str = "default") -> list[ChatMessage]
    """The `limit` most recent messages, returned OLDEST FIRST."""
async def add_chat_message(
    role: str, content: str, actions: list | None = None,
    *, user_id: str = "default",
) -> ChatMessage

# repo_seeds.py  (BUILD_CONTRACT A3 — persisted seeds)
async def get_ticker_seed(ticker: str) -> TickerSeed | None
async def upsert_ticker_seed(
    ticker: str, seed_price: float, drift: float, volatility: float
) -> TickerSeed
```

### Extra table — `ticker_seeds`

Beyond the six tables in PLAN.md section 7:

```
ticker_seeds
  ticker      TEXT PRIMARY KEY
  seed_price  REAL
  drift       REAL
  volatility  REAL
  created_at  TEXT
```

---

## 2. Service layer — `backend/app/services/`

Owned by **backend-engineer**. This is the ONLY place trade and watchlist
mutation logic lives. The HTTP routes and the LLM both call these same
functions (BUILD_CONTRACT B3).

```python
# app/services/errors.py
class ServiceError(Exception):
    """str(e) is the human-readable message put into {"error": ...} with 400."""

# app/services/portfolio_service.py
async def get_portfolio() -> dict
    """{"cash": float, "positions": [...], "total_value": float,
        "unrealized_pnl": float}
    Each position: {ticker, quantity, avg_cost, current_price,
                    unrealized_pnl, pnl_percent}.
    current_price comes from state.price_cache; falls back to avg_cost when the
    cache has no entry yet."""

async def execute_trade(ticker: str, side: str, quantity: float) -> dict
    """Validates ticker format, side, and quantity > 0. Ensures the ticker is
    tracked, waiting up to 2s for a first price (BUILD_CONTRACT A4). Calls
    execute_trade_tx, then records a portfolio snapshot.
    Returns {"ok": True, "trade": {...}, "portfolio": {...}}.
    Raises ServiceError on any validation or funds/shares failure."""

async def get_history() -> dict
    """{"snapshots": [{"total_value": float, "recorded_at": str}, ...]}"""

async def snapshot_now() -> None
    """Compute total value and record a snapshot. Used by the 30s background task."""

# app/services/watchlist_service.py
async def get_watchlist() -> dict
    """{"tickers": [ {ticker, price, previous_price, open_price, change,
                      change_percent, direction, timestamp}, ... ]}
    added_at ascending. Fields come from PriceCache; price is null if not yet ticked."""

async def add_ticker(ticker: str) -> dict
    """Validate ^[A-Z]{1,5}$ (uppercase the input first). Persist a seed via
    upsert_ticker_seed if unknown, add to the watchlist, add to the market
    source. Returns {"ok": True, "ticker": "AAPL"}.
    Raises ServiceError("Invalid ticker format") on a bad symbol."""

async def remove_ticker(ticker: str) -> dict
    """Remove from the watchlist. Stops tracking ONLY if no open position
    (BUILD_CONTRACT A2). Returns {"ok": True}."""

async def tracked_tickers() -> list[str]
    """watchlist union tickers with a non-zero position. Used at startup."""
```

---

## 3. LLM layer — `backend/app/llm/`

Owned by **llm-engineer**. Exactly two public functions. The HTTP route lives in
`app/api/chat.py` (backend-engineer) and is a thin wrapper over these.

```python
# app/llm/chat.py
async def handle_chat(message: str) -> dict
    """Full turn: persist the user message, build context, call the LLM,
    auto-execute trades and watchlist changes via the SERVICE functions in
    section 2, persist the assistant message with its actions, return it.

    Returns the POST /api/chat body:
        {"id", "role": "assistant", "content", "actions", "created_at"}

    `actions` is a list of receipts (BUILD_CONTRACT B6):
        {"type": "trade", "ok": true,  "ticker": "AAPL", "side": "buy",
         "quantity": 10, "price": 190.5}
        {"type": "trade", "ok": false, "ticker": "AAPL", "side": "buy",
         "quantity": 10, "error": "Insufficient cash"}
        {"type": "watchlist", "ok": true,  "ticker": "PYPL", "action": "add"}
        {"type": "watchlist", "ok": false, "ticker": "ZZZZZZ", "action": "add",
         "error": "Invalid ticker format"}

    Never raises for an LLM failure — returns a message explaining the problem
    with actions: []."""

async def get_history(limit: int = 20) -> dict
    """{"messages": [ {id, role, content, actions, created_at}, ... ]} oldest
    first. Thin wrapper over repo_chat.list_chat_messages."""
```

Model: `openrouter/openai/gpt-oss-120b` with Cerebras as the inference provider,
via `litellm.acompletion` (never the sync `completion` — BUILD_CONTRACT section
6). Use the `cerebras` skill for the call shape.

### 3.1 LLM_MOCK contract — frozen

`LLM_MOCK=true` replaces **only the `litellm.acompletion` call**. The mock
returns the same structured payload a real model would return; everything
downstream — trade execution through `app.services.*`, receipt building,
persistence — runs unchanged. This is what makes a failed trade testable: an
over-large buy really reaches `execute_trade`, really fails, and really produces
an `ok: false` receipt. **Never short-circuit past the service layer.**

Triggers are matched against the user message, case-insensitive, **first match
wins**. Tickers are uppercased before use.

| Pattern | Structured payload | `message` |
| --- | --- | --- |
| `\bbuy\s+(\d+(?:\.\d+)?)\s+([A-Za-z]{1,10})\b` | `trades: [{ticker, side:"buy", quantity}]` | `Buying {qty} {TICKER}.` |
| `\bsell\s+(\d+(?:\.\d+)?)\s+([A-Za-z]{1,10})\b` | `trades: [{ticker, side:"sell", quantity}]` | `Selling {qty} {TICKER}.` |
| `\bwatch\s+([A-Za-z]{1,10})\b` | `watchlist_changes: [{ticker, action:"add"}]` | `Adding {TICKER} to the watchlist.` |
| `\bunwatch\s+([A-Za-z]{1,10})\b` | `watchlist_changes: [{ticker, action:"remove"}]` | `Removing {TICKER} from the watchlist.` |
| anything else | no trades, no watchlist changes | `Mock mode: no model was called. Ask me to buy, sell, watch or unwatch a ticker.` |

Triggers are **parametric, not canned**. Any ticker and any quantity, so the
E2E suite can drive an arbitrary scenario without a new mock branch. A canned
set like "buy aapl -> buy 5 AAPL" is not acceptable: it forces the test to know
the mock's private choices, and every new scenario needs a code change in
`app/llm/`.

The capture is `{1,10}` rather than `{1,5}` **on purpose**. A symbol longer than
five characters is invalid per A3, and the mock must pass it straight through to
`watchlist_service.add_ticker` so the real validator rejects it with the real
`"Invalid ticker format"` error and a genuine `ok: false` receipt. **The mock
never validates anything.** It only decides what the model would have said; every
verdict comes from the service layer.

`message` text is fixed and contains no live prices or portfolio figures, so
E2E assertions on it are stable. Fill prices and failures appear only in
`actions`, never in the mock prose — same as the real path (BUILD_CONTRACT B6).

---

## 4. HTTP routes — `backend/app/api/`

Owned by **backend-engineer**. Thin. No business logic. Catch `ServiceError`
and return `400 {"error": str(e)}`.

```
app/api/health.py     -> router  GET  /api/health
app/api/portfolio.py  -> router  GET  /api/portfolio
                                 POST /api/portfolio/trade
                                 GET  /api/portfolio/history
app/api/watchlist.py  -> router  GET  /api/watchlist
                                 POST /api/watchlist
                                 DELETE /api/watchlist/{ticker}
app/api/chat.py       -> router  GET  /api/chat?limit=20
                                 POST /api/chat
```

`app/main.py` creates the app, mounts every router, mounts the SSE router from
`create_stream_router(state.price_cache)`, serves the static frontend export
from `static/` as a catch-all, and runs the `lifespan` handler:

```
startup:  load .env -> init_db() -> tracked = tracked_tickers()
          -> market_source.start(tracked) -> start the 30s snapshot task
shutdown: cancel the snapshot task -> market_source.stop() -> close_db()
```

Static serving must not shadow `/api/*`. Mount API routers first. The static
directory may be absent in local dev — tolerate that, do not crash.

---

## 5. Frontend — `frontend/`

Owned by **frontend-engineer**. Next.js + TypeScript, `output: 'export'`,
Tailwind. Talks only to the HTTP contract in `BUILD_CONTRACT.md` section 4 and
the SSE shape in A5. Build output goes to `frontend/out/`.

`npm run build` must produce a fully static `out/` directory — devops copies it
to `static/` in the image.

**Stable test hooks.** integration-tester selects on these `data-testid`
values; frontend-engineer must provide them and not rename them:

```
connection-status      header dot; data-state="connected|reconnecting|disconnected"
cash-balance           header cash figure
total-value            header portfolio total
watchlist              watchlist container
watchlist-row-<T>      one row, e.g. watchlist-row-AAPL
watchlist-price-<T>    the price cell inside that row
watchlist-add-input    add-ticker text input
watchlist-add-submit   add-ticker button
watchlist-remove-<T>   remove button for a ticker
watchlist-error        error region for a rejected add, e.g. "Invalid ticker format"
main-chart             selected-ticker chart container;
                       data-points="<n>" = number of points currently plotted
positions-table        positions table container
position-row-<T>       one position row
portfolio-heatmap      treemap container
heatmap-tile-<T>       one position tile inside the treemap
pnl-chart              portfolio value line chart container;
                       data-points="<n>" = number of points currently plotted
trade-ticker           trade bar ticker input
trade-quantity         trade bar quantity input
trade-buy              buy button
trade-sell             sell button
trade-error            error message region of the trade bar
chat-panel             chat sidebar container
chat-input             chat text input
chat-send              chat send button
chat-message-<n>       nth message bubble, 0-indexed, oldest first
chat-loading           loading indicator shown while a chat request is in flight
chat-action-chip       one action receipt chip (multiple allowed);
                       data-ok="true|false" marks success vs failure
```

Every error region (`trade-error`, `watchlist-error`) must be present in the DOM
only when there is an error, and must render the backend's `{"error": ...}`
string verbatim rather than a rewritten message. Tests select on the testid, not
on the wording.

**Charts expose their data, not their rendering.** Tests must never assert on
SVG `rect`/`path`/`circle` counts or canvas pixels — the rendering primitive is
the frontend's free choice (the heatmap is div-based, the P&L chart is SVG), and
a test that counts primitives breaks on a purely visual refactor while proving
nothing about the data. Instead:

- `portfolio-heatmap` contains one `heatmap-tile-<TICKER>` per position.
- `main-chart` and `pnl-chart` each carry `data-points="<n>"`, the number of
  points actually plotted. `0` is a truthful value for an empty chart and must
  be rendered, not omitted.

This is the whole chart contract. Nothing else about chart internals is frozen,
and nothing else may be asserted on.

---

## 6. Docker / scripts — root

Owned by **devops-engineer**. `Dockerfile`, `.dockerignore`,
`docker-compose.yml`, `.env.example`, `scripts/{start,stop}.{sh,ps1}`.

- Stage 1 `node:20-slim`: build `frontend/` into `out/`
- Stage 2 `python:3.12-slim` + uv: `uv sync --frozen`, copy `frontend/out` to
  `/app/static`, expose 8000, run uvicorn.
- **Named volume `finally-data:/app/db`, not a bind mount.** `DB_PATH=/app/db/finally.db`.
  This overrides BUILD_CONTRACT B10, which preferred a bind mount for
  inspectability. Reason: SQLite runs in WAL mode (mandatory, BUILD_CONTRACT
  section 6), and WAL mmaps a `-shm` sidecar. Docker Desktop's Windows
  bind-mount bridge cannot support that mapping — the second start fails with
  `sqlite3.OperationalError: disk I/O error` and leaves `-wal`/`-shm` locked on
  the host. A named volume is ext4 inside the Docker VM, where WAL works.
  Inspect with `docker compose exec finally sqlite3 /app/db/finally.db`; copy
  out with `docker compose cp finally:/app/db/finally.db ./db/finally.db`.
  The host `db/` directory is for local (non-Docker) runs only.
- `--env-file .env` is the only env mechanism in Docker; `python-dotenv` is a
  local-dev convenience only.

### 6.1 Image layout — frozen

```
WORKDIR /app
  /app/app/      backend/app copied here, PYTHONPATH=/app
  /app/static/   frontend out/ copied here
  /app/db/       named volume finally-data, DB_PATH=/app/db/finally.db
  /app/.venv/    on PATH
CMD uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Static directory resolution is `__file__`-relative, not CWD-relative.**
`app/main.py` uses `Path(__file__).resolve().parent.parent / "static"` with an
optional `STATIC_DIR` env override. In the image that resolves to `/app/static`,
matching the layout above, and it keeps working if uvicorn is ever launched from
a different working directory. Neither side needs to change.

### 6.2 Test-mode env override — frozen

`.env` is the user's own file holding their real API keys. Nothing in this
project rewrites it and no agent edits it.

The E2E suite needs the simulator and the mock LLM, but this machine's `.env`
has a non-empty `MASSIVE_API_KEY`, which selects the real Massive API. So
devops-engineer adds `docker-compose.test.yml` containing **only** an
environment override:

```yaml
services:
  finally:
    environment:
      MASSIVE_API_KEY: ""
      LLM_MOCK: "true"
```

Used as `docker compose -f docker-compose.yml -f docker-compose.test.yml up -d`.
Compose `environment:` beats `env_file:`, so this wins over `.env` without
touching it.

This does not reopen BUILD_CONTRACT C2. C2 dropped a `docker-compose.test.yml`
that ran a **Playwright container**; there is still no Playwright container and
Playwright still runs on the host. This file is a five-line env override, nothing
more.

`scripts/reset.{sh,ps1}` takes a `--test` flag that layers the override in when
restarting. Playwright `globalSetup` calls `reset --yes --test`. The plain
user-facing `reset` never uses test mode.

Never run `docker compose config` in a logged or CI step — it prints resolved
`env_file` values, including real API keys, in plaintext.

---

## 7. E2E tests — `test/`

Owned by **integration-tester**. Playwright on the host against
`http://localhost:8000`, `LLM_MOCK=true`. Gate readiness on
`GET /api/health` returning `cache_ready: true` — never on a UI guess.
No SSE-reconnection test (BUILD_CONTRACT C7).

### 7.1 Fresh state — frozen

There is no state-reset API endpoint and there will not be one; test-only routes
do not belong in the production app.

**devops-engineer** provides `scripts/reset.sh` and `scripts/reset.ps1`: stop
the app **and remove the data volume** (`docker compose down -v` — note compose
prefixes the project name, so the real volume is `finally_finally-data`, and a
hand-typed `docker volume rm finally-data` would not find it), start the app,
poll `GET /api/health`
until `cache_ready` is true, exit non-zero on timeout. The database lives in
the named volume (section 6), so deleting host files under `db/` is a silent
no-op — the reset must remove the volume. Removing the whole volume is also the
only thing that yields a genuinely fresh database: a table-truncating reset
leaves the profile row in place, which is exactly the half-populated state that
`init_db` treats as "not new".

**devops-engineer** also provides `scripts/restart.sh` and `scripts/restart.ps1`:
identical to `reset` **minus the volume removal** — stop, start (with the
`--test` override when asked), poll health. Data survives the bounce. The
restart-persistence spec uses it to prove that a removed ticker stays removed
and a bought position survives a restart, which is the class of bug `init_db`'s
seeding gate had before db-engineer fixed it. `restart` is not destructive, so
`--yes` is accepted for interface symmetry but nothing is confirmed.

Flags: `--yes` skips the confirmation prompt (the reset is destructive and
unrecoverable, so without it the script prints what it will delete and asks);
`--test` layers `docker-compose.test.yml` (section 6.2) on the restart. Playwright
`globalSetup` calls `reset --yes --test` and then **verifies** the state is
fresh via `/api/portfolio` and `/api/chat` — a reset that reports success while
changing nothing fails the run there, not three specs later.
This is also a genuine user-facing feature — "reset my portfolio" is a normal
thing to want from a trading simulator — so it is documented in the README, not
hidden as test scaffolding.

**integration-tester** invokes it from Playwright `globalSetup`. Every
assertion is then unconditional: the `$10,000` fresh-start check is a hard
assertion, never a conditional skip. A spec that skips itself when the
environment is not what it expected hides regressions rather than reporting
them. Run with `workers: 1` — one shared portfolio, no parallelism.
