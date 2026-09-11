# FinAlly — AI Trading Workstation

An AI-powered trading workstation that streams live market data, simulates portfolio trading, and integrates an LLM assistant that can analyse positions and execute trades through natural language.

Built by coding agents as the capstone project for an agentic AI coding course. The full specification is in [planning/PLAN.md](planning/PLAN.md), which agents use as their shared contract.

## Status

Early development. Only the market data subsystem is built.

| Component | State |
| --- | --- |
| Market data — simulator, Massive API client, price cache, SSE endpoint | Built, 73 tests passing |
| Database, portfolio, trading | Not started |
| LLM chat assistant | Not started |
| Frontend | Not started |
| Docker packaging | Not started |

There is no runnable application yet — no Dockerfile, no frontend, no API server. The sections below describe what exists today.

## Running what exists

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
cd backend
uv sync

# Live terminal dashboard: 10 tickers with sparklines and colour-coded moves.
# Runs 60 seconds, or until Ctrl+C. No API key needed.
uv run market_data_demo.py

# Test suite
uv run pytest
```

## Running with Docker

Requires Docker Desktop (or Docker Engine with the compose plugin). Copy `.env.example` to `.env` and add your `OPENROUTER_API_KEY`, then use the scripts in `scripts/`. Each has a `.sh` (macOS/Linux) and a `.ps1` (Windows PowerShell 5.1+) variant with the same flags.

| Script | What it does |
| --- | --- |
| `start` | Build if needed and start the app at http://localhost:8000. `--build` forces a rebuild, `--open` opens a browser once healthy. Safe to run repeatedly. |
| `stop` | Stop the app. Your portfolio, trades and chat history are kept. |
| `restart` | Stop and start again, keeping all data, and wait until the app is healthy. |
| `reset` | Start over: stop the app, delete the database volume, start fresh with $10,000 cash and the default watchlist. Asks for confirmation; `--yes` skips it. Unrecoverable. |

```bash
scripts/start.sh --build      # first run
scripts/reset.sh              # wipe the portfolio and start over
.\scripts\start.ps1 -Build    # Windows (PowerShell also accepts --build)
```

`restart` and `reset` accept `--test`, which starts the app with the built-in simulator and a mock LLM regardless of the keys in `.env`. The E2E suite uses this; you do not need it for normal use.

The database lives in the Docker volume `finally-data`, not in the `db/` directory. `stop` never removes it; only `reset` does.

## Market data

Two interchangeable sources sit behind one abstract interface (`MarketDataSource`):

- **Simulator** (default) — geometric Brownian motion with per-ticker drift and volatility, sector-correlated moves, and occasional random shocks. Runs in-process with no external dependencies.
- **Massive API** (optional) — REST polling against Polygon.io. Selected automatically when `MASSIVE_API_KEY` is set.

Both write to a thread-safe `PriceCache`. Everything downstream — the SSE endpoint, and later portfolio valuation and trade execution — reads from that cache and never touches the source directly, so the rest of the system does not care which one is running.

Module-level detail is in [planning/MARKET_DATA_SUMMARY.md](planning/MARKET_DATA_SUMMARY.md).

## Environment variables

Create a `.env` file in the project root:

| Variable | Required | Description |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | Later | OpenRouter key for the AI chat assistant. Not used yet. |
| `MASSIVE_API_KEY` | No | Polygon.io key for real market data. Omit to use the simulator. |
| `LLM_MOCK` | No | Set `true` for deterministic mock LLM responses in tests. |

## Planned architecture

A single Docker container serving everything on port 8000:

- **Frontend** — a static build served by FastAPI, so there is one origin and no CORS setup
- **Backend** — FastAPI managed with uv, pushing live prices over SSE
- **Database** — SQLite, a single volume-mounted file
- **AI** — LiteLLM to OpenRouter, using structured outputs to drive trade execution

## Project structure

```
finally/
├── backend/              FastAPI uv project
│   ├── app/market/       Market data subsystem (built)
│   └── tests/            Unit and integration tests
└── planning/             Specification and agent contracts
    ├── PLAN.md
    └── MARKET_DATA_SUMMARY.md
```

## License

See [LICENSE](LICENSE).
