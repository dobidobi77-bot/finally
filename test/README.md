# FinAlly E2E tests

Playwright, run on the host against a running app (BUILD_CONTRACT C2 — no
Playwright container).

## Run

```bash
cd test
npm install
npm test          # npm run test:headed to watch it
npm run report    # open the HTML report of the last run
```

`globalSetup` calls `scripts/reset --yes --test` itself, so there is nothing to
start by hand. That deletes `db/finally.db` and its `-wal` / `-shm` sidecars,
restarts the app with the test-mode override, and polls `GET /api/health` until
`cache_ready` is true (INTERFACES.md 7.1). Every assertion is therefore
unconditional — the `$10,000` fresh-start check is a hard assertion.

## Test mode

`--test` layers `docker-compose.test.yml` on top of `docker-compose.yml`
(INTERFACES.md 6.2), forcing `MASSIVE_API_KEY=""` and `LLM_MOCK=true` without
touching the user's `.env`. The suite needs both:

- the **simulator**, because the real Massive API polls every 15 seconds and
  goes flat outside US market hours, which the streaming assertions cannot
  tolerate;
- the **mock LLM**, because the chat specs assert the frozen behaviour in
  INTERFACES.md 3.1 — and a real model would cost money on every run.

Setup fails loudly if `GET /api/health` does not report
`market_source: "simulator"`, rather than letting the suite go flaky and
expensive. Never run `docker compose config` here: it prints resolved `env_file`
values, real API keys included, in plaintext.

| Variable | Default | Purpose |
| --- | --- | --- |
| `E2E_BASE_URL` | `http://localhost:8000` | where the app is served |
| `E2E_READY_TIMEOUT_MS` | `90000` | how long setup waits for readiness |
| `E2E_SCRIPT_FLAVOR` | `ps1` on Windows, else `sh` | which devops script variant to invoke |
| `E2E_SKIP_RESET` | unset | reuse the running app instead of resetting — for iterating on one spec, never for a full run |

## Layout

```
playwright.config.ts   single worker, no retries, no webServer
helpers/health.ts      the readiness gate - polls /api/health for cache_ready
helpers/appctl.ts      drives scripts/reset and scripts/restart; asserts test mode
helpers/fixtures.ts    app + api fixtures; applies the gate to every test
helpers/app.ts         page object over the data-testid contract
helpers/api.ts         typed HTTP client used for setup and for evidence
helpers/charts.ts      counts drawn marks in SVG or canvas charts
specs/                 numbered; the shared portfolio is exercised in order
```

## Why one worker and no retries

The app is single-user: every spec touches the same cash, positions, watchlist
and chat log. Parallel workers would interleave trades, and a retry would replay
a trade against a portfolio the first attempt already changed. Specs set up
their own preconditions and assert on deltas rather than depending on cleanup.

`09-restart-persistence.spec.ts` runs last and bounces the app **without**
deleting the database, to prove a restart never undoes a user's changes.

## When a spec fails

Failures carry a trace, a screenshot and a video (`test-results/`). The failure
messages quote the request/response body — report that to the owning role. The
specs never work around application bugs.
