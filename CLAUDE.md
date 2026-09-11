# FinAlly Project - the Finance Ally

All project documentation is in the `planning` directory.

The key document is PLAN.md included in full below. The market data component is summarized in `planning/MARKET_DATA_SUMMARY.md` with more details in the `planning/archive` folder. Consult these docs only when required.

**Agent team members: read `planning/BUILD_CONTRACT.md` before writing any code.** It records the settled decisions, file ownership per role, and the API contract. Where it and PLAN.md disagree, BUILD_CONTRACT.md wins. `planning/INTERFACES.md` freezes the Python module signatures, the `data-testid` hooks, the LLM mock triggers, and the Docker layout.

## Common commands

Run from the project root unless noted.

```bash
# Backend (uv-managed; never `python`, never `pip`)
cd backend && uv run pytest -q              # unit tests
cd backend && uv run ruff check app/ tests/ # lint
cd backend && uv run uvicorn app.main:app --reload   # local dev server, API only

# Frontend
cd frontend && npm test                     # vitest, single run
cd frontend && npm run build                # static export to frontend/out/
cd frontend && npm run dev                  # dev server (proxy to backend not configured; use Docker for full app)

# Docker (the supported way to run the full app)
scripts/start.sh --build   # or scripts\start.ps1 -Build   -> http://localhost:8000
scripts/stop.sh            # stops; keeps the data volume
scripts/restart.sh         # bounce; keeps data
scripts/reset.sh --yes     # WIPES the database volume and restarts
scripts/reset.sh --yes --test   # same, with simulator + LLM_MOCK (what E2E uses)

# E2E (Playwright on the host; globalSetup runs reset --yes --test itself)
cd test && npm test
cd test && npm run report                   # open the last HTML report

# Health / mode check
curl http://localhost:8000/api/health       # {"status","market_source","cache_ready"}
```

Never run `docker compose config` in anything logged: it prints `.env` secrets in plaintext.

@planning/PLAN.md