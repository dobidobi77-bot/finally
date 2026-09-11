# Backend — Developer Guide

## Project Setup

```bash
cd backend
uv sync               # Install all dependencies including the dev group (test/lint tools)
```

## Market Data API

The market data subsystem lives in `app/market/`. Use these imports:

```python
from app.market import PriceCache, PriceUpdate, MarketDataSource, create_market_data_source
```

### Core Types

- **`PriceUpdate`** — Immutable dataclass: `ticker`, `price`, `previous_price`, `open_price`, `timestamp`, plus properties `change`, `change_percent`, `direction` ("up"/"down"/"flat"), and `to_dict()` for JSON serialization. `previous_price` is one tick ago (drives the flash); `open_price` is the session baseline (drives daily change %, BUILD_CONTRACT A1).

- **`PriceCache`** — Thread-safe in-memory store. Key methods:
  - `update(ticker, price, timestamp=None) -> PriceUpdate`
  - `get(ticker) -> PriceUpdate | None`
  - `get_price(ticker) -> float | None`
  - `get_all() -> dict[str, PriceUpdate]`
  - `set_open_price(ticker, open_price)` / `get_open_price(ticker) -> float | None`
  - `remove(ticker)`
  - `version` property — monotonic counter, bumped on every update **and every removal** (for SSE change detection)

- **`MarketDataSource`** — Abstract interface implemented by `SimulatorDataSource` and `MassiveDataSource`. Lifecycle: `start(tickers)` -> `add_ticker()` / `remove_ticker()` -> `stop()`.

- **`create_market_data_source(cache)`** — Factory. Returns `MassiveDataSource` if `MASSIVE_API_KEY` is set, otherwise `SimulatorDataSource`.

### SSE Streaming

```python
from app.market import create_stream_router

router = create_stream_router(price_cache)  # Returns a fresh FastAPI APIRouter
# Endpoint: GET /api/stream/prices (text/event-stream)
```

Wire format (BUILD_CONTRACT A5): `retry: 1000` on connect, then one unnamed
event whose `data` is a JSON object keyed by ticker, emitted only when the cache
version changes, plus a `: keepalive` comment every 15s while quiet.

### Seed Data

Default tickers: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX. Seed prices and per-ticker volatility/drift params are in `app/market/seed_prices.py`.

A ticker not in that table seeds at `DEFAULT_SEED_PRICE` (100.00) and is
persisted to the `ticker_seeds` table by `app/market/seed_resolver.py`, so it
starts at the same price after a restart (BUILD_CONTRACT A3).

## Application Layout

- `app/state.py` — shared `price_cache`, `market_source`, SSE client count
- `app/services/` — the only place trade and watchlist logic lives; the HTTP
  routes and the LLM both call these
- `app/api/` — thin routers; `ServiceError` becomes `400 {"error": ...}` via the
  app-level exception handler in `app/main.py`
- `app/main.py` — `create_app()` plus the `lifespan` handler (init DB, start the
  feed, run the 30s snapshot task)

## Running Tests

```bash
uv run pytest -v              # All tests
uv run pytest --cov=app       # With coverage
uv run ruff check app/ tests/ # Lint
```

## Demo

```bash
uv run market_data_demo.py   # Live terminal dashboard with simulated prices
```
