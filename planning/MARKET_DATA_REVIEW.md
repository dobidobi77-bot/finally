# Market Data Backend — Code Review (Round 2)

**Date:** 2026-09-10
**Scope:** `backend/app/market/` (8 modules), `backend/tests/market/` (6 test modules), `backend/market_data_demo.py`, `backend/pyproject.toml`
**Reviewer environment:** Python 3.13.7, `uv` 0.12.12, all dependencies installed from `uv.lock`
**Supersedes:** `planning/archive/MARKET_DATA_REVIEW.md` (round 1)

---

## 0. Executive Summary

The round-1 review's action items have all been applied and the suite is now green: **73 tests pass, 91% coverage, `ruff check` clean**. On structure, this code is genuinely good — the strategy pattern, the shared cache, the immutable `PriceUpdate`, and the lifecycle discipline are all sound and will integrate cleanly.

However, this round found **two defects that the passing test suite does not catch**, both of which mean a shipped subsystem does not do what its documentation says it does:

1. **The Massive (real market data) path never populates the price cache at all.** It is 100% non-functional against the real SDK. Verified empirically.
2. **The random shock events overwhelm the GBM engine by ~317x in variance**, rendering the per-ticker volatility tuning and the entire Cholesky correlation design inert. Verified empirically.

Both slipped past 73 tests for the same underlying reason, discussed in §4: the suite tests the implementation against mocks built from the implementation's own assumptions, and never asserts the simulator's *statistical* behaviour — which is the simulator's entire product.

**Verdict: not ready to be treated as "complete".** Item C1 must be fixed before `MASSIVE_API_KEY` is documented as supported; C2 should be fixed before the simulator is considered representative. Everything else is small.

---

## 1. Test & Lint Results (this run)

```
$ uv run --extra dev pytest -v --cov=app --cov-report=term-missing
73 passed in 3.50s
```

| Module | Stmts | Miss | Cover | Uncovered |
|---|---:|---:|---:|---|
| `app/market/cache.py` | 39 | 0 | 100% | |
| `app/market/factory.py` | 15 | 0 | 100% | |
| `app/market/interface.py` | 13 | 0 | 100% | |
| `app/market/models.py` | 26 | 0 | 100% | |
| `app/market/seed_prices.py` | 8 | 0 | 100% | |
| `app/market/simulator.py` | 139 | 3 | 98% | 149, 268-269 |
| `app/market/massive_client.py` | 67 | 4 | 94% | 85-87, 125 |
| `app/market/stream.py` | 36 | 24 | **33%** | 26-48, 62-87 |
| **TOTAL** | **349** | **31** | **91%** | |

- `ruff check app/ tests/ market_data_demo.py` — **All checks passed.**
- `ruff format --check` — 3 test files would be reformatted (`test_models.py`, `test_simulator.py`, `test_simulator_source.py`). Not currently part of the documented workflow in `backend/CLAUDE.md`, which only lists `ruff check`.

**Note on `MARKET_DATA_SUMMARY.md`:** it reports 84% overall and 56% for `massive_client.py`. Actual figures are 91% and 94%. The summary's numbers predate the round-1 fixes; they should be refreshed. (The higher `massive_client` coverage is *not* reassuring — see §2.1.)

Round-1 items confirmed fixed: hatchling wheel config present; `massive` imported at module level; `_generate_events` correctly annotated `AsyncGenerator[str, None]`; `GBMSimulator.get_tickers()` public; `DEFAULT_CORR` removed; unused test imports gone. Round-1 items **still open**: 3.4 (`version` property not under lock), 3.6 (module-level router), and all three gaps under 4.2 (missing tests).

---

## 2. Critical Findings

### C1 — The Massive data source silently discards every price it fetches (Severity: **Critical**)

`massive_client.py:103` reads `snap.last_trade.timestamp`. That attribute **does not exist** on the SDK's `LastTrade` model.

```
$ python -c "from massive.rest.models import LastTrade; print(hasattr(LastTrade,'timestamp'))"
False
```

`LastTrade`'s actual fields are: `ticker, trf_timestamp, sequence_number, sip_timestamp, participant_timestamp, conditions, correction, id, price, trf_id, size, exchange, tape`.

The access raises `AttributeError`, which is caught by the handler two lines below (`massive_client.py:110`) — the one written to skip *malformed* snapshots. So every well-formed snapshot is treated as malformed, logged at WARNING, and dropped. `processed` stays at 0. The cache is never written.

Verified by feeding a genuine `massive.rest.models.TickerSnapshot` through `_poll_once()`:

```
WARNING Skipping snapshot for AAPL: 'LastTrade' object has no attribute 'timestamp'
cache.get_price('AAPL') = None      <-- expected 190.5
```

**User-visible effect:** set `MASSIVE_API_KEY` and the entire application has no prices. The watchlist is empty, the SSE stream sends nothing (the cache version never changes), portfolio valuation has nothing to value, and trades cannot fill. The only symptom is a WARNING line per ticker per poll.

**Second bug in the same three lines:** `timestamp / 1000.0` assumes milliseconds. Massive/Polygon trade timestamps are **nanoseconds** (`sip_timestamp` is a 19-digit integer). Even with the attribute fixed, `/1000.0` yields a timestamp ~10^6 times too large. The correct divisor is `1e9`.

**Fix:**

```python
price = snap.last_trade.price
timestamp = snap.last_trade.sip_timestamp / 1e9   # ns -> s
```

Guard against `sip_timestamp is None` (it is `Optional[int]`) by falling back to `time.time()` — otherwise a null timestamp reintroduces the same silent-skip via `TypeError`.

**Also fix the error handling that hid this.** Catching `AttributeError` around a block that does normal attribute access is what turned a hard schema mismatch into a silent no-op. Narrow the guard to explicit `None` checks on `snap.last_trade` / `snap.ticker`, and log at ERROR (not WARNING) when a poll processes 0 of N tickers — a poll that updates nothing is never normal.

### C2 — Shock events swamp the GBM engine, nullifying the correlation and volatility design (Severity: **High**)

The simulator's two headline features — per-ticker volatility tuning and Cholesky-correlated sector moves — are not observable in the shipped configuration. Measured over 20,000 ticks on the 10 default tickers:

| Measurement | `event_probability=0` | `event_probability=0.001` (shipped) | Target |
|---|---:|---:|---:|
| corr AAPL/GOOGL | +0.598 | **+0.003** | 0.60 |
| corr JPM/V | +0.501 | **−0.000** | 0.50 |
| corr TSLA/AAPL | +0.304 | **+0.003** | 0.30 |
| realized ann. σ, AAPL | 0.221 | **3.684** (16.7×) | 0.22 |
| realized ann. σ, V | 0.169 | **4.810** (28.3×) | 0.17 |
| realized ann. σ, TSLA | 0.501 | **3.827** (7.7×) | 0.50 |
| realized ann. σ, NVDA | 0.399 | **3.919** (9.8×) | 0.40 |

With events off, the GBM is **mathematically exact** — every correlation and every volatility lands on target to three decimals. The math in `simulator.py` is correct and well implemented. The problem is purely the shock term drowning it.

**Variance budget per tick (AAPL):**

| Source | Return variance | Return sd |
|---|---:|---:|
| GBM diffusion | 4.10e-09 | 6.41e-05 |
| Shock events | 1.30e-06 | 1.14e-03 |
| **Ratio** | **317×** | 17.8× |

Because shocks are drawn independently per ticker, they carry zero correlation, so they dilute the intended correlation by the same 317:1 ratio — hence 0.6 collapsing to 0.003. And because every ticker gets the same shock distribution regardless of its `sigma`, all realized volatilities converge to roughly the same value: the carefully chosen contrast between TSLA (0.50) and V (0.17) is gone, and V ends up *more* volatile than TSLA in practice.

**Price drift over one simulated hour (7,200 ticks):**

| | min move | max move | mean abs move |
|---|---:|---:|---:|
| `event_probability=0` | −1.32% | +1.02% | 0.70% |
| `event_probability=0.001` | −14.68% | +17.79% | **9.21%** |

At the shipped rate each ticker takes ~7.2 permanent 2–5% steps per hour. Since shocks never mean-revert, prices random-walk on 3% steps: after a trading day a ticker will routinely be 20–40% from its seed price. `NVDA` at $800 will not stay recognisably near $800.

The code comment at `simulator.py:103-104` ("With 10 tickers at 2 ticks/sec, expect an event ~every 50 seconds") is arithmetically right about the *aggregate* rate but understates what it means per ticker over a session.

**Recommended fix — pick one:**

- **(a) Lower the rate by ~100×** to `event_probability=1e-5`. That gives roughly one shock per ticker per two hours, restores the GBM as the dominant process, and keeps occasional drama. Cheapest fix, one constant.
- **(b) Make shocks mean-reverting** — apply the shock, then decay it back over the following ~60 ticks. Keeps the visual spike while leaving the long-run price path governed by GBM. More realistic, ~15 lines.
- **(c) Keep the rate but shrink the magnitude** to 0.2–0.5%. Loses the drama the feature exists for; least attractive.

Option (a) is the recommendation. Whichever is chosen, add the statistical regression tests described in §4.

---

## 3. Medium Findings

### M1 — The two `MarketDataSource` implementations disagree on ticker normalization

`MassiveDataSource.add_ticker` upper-cases and strips (`massive_client.py:67`). `SimulatorDataSource.add_ticker` does neither. The ABC in `interface.py` specifies nothing, so downstream code has no contract to rely on:

```
simulator tickers after start(["AAPL"]), add_ticker("aapl"), add_ticker(" tsla "):
  ['AAPL', 'aapl', ' tsla ']
```

Under the simulator, `add_ticker("aapl")` creates a *second, distinct* ticker with a random $50–300 seed price and no relationship to AAPL. `remove_ticker("aapl")` then would not remove `AAPL`, and the watchlist would show both. This is exactly the path `POST /api/watchlist` and the LLM's `watchlist_changes` will take.

**Fix:** normalize once, at the boundary. Either state in `interface.py` that implementations must accept any case and normalize to `UPPER`, and do so in both — or (better) normalize in the API/service layer before it ever reaches a data source, and document that data sources receive pre-normalized symbols. Add the same normalization to `remove_ticker` and to `start()`, which currently normalizes in neither implementation.

### M2 — `dt` is decoupled from `update_interval`

`SimulatorDataSource.__init__` accepts `update_interval` (`simulator.py:210`) but constructs `GBMSimulator` without passing a matching `dt` (`simulator.py:220-223`), so `dt` is always `DEFAULT_DT` — hardcoded to 0.5 s of a trading year. Configure a 2-second interval and the simulation runs at ¼ the intended volatility; configure 0.1 s and it runs at 5×. The tests exercise `update_interval` values of 0.01–0.1 s and never notice, because they only assert that the version counter moved.

**Fix:** derive it — `dt = update_interval / GBMSimulator.TRADING_SECONDS_PER_YEAR` — and pass it through.

### M3 — Module-level router causes duplicate route registration

`stream.py:17` builds `router` at import time; `create_stream_router()` registers `/prices` onto that shared instance and returns it. Two calls therefore mutate the same object:

```
r1 is r2 (module-level singleton): True
route paths after two factory calls: ['/api/stream/prices', '/api/stream/prices']
```

The factory signature promises injection but delivers a singleton: the *first* call's `price_cache` wins, and any later call's cache is silently ignored while leaving a dead duplicate route. This defeats the stated purpose ("lets us inject the PriceCache without globals") and will bite the moment anyone writes a second SSE test with a second cache — which §4 recommends doing.

**Fix:** move `router = APIRouter(...)` inside the factory. One-line change, and it makes the docstring true.

### M4 — `cache.update(timestamp=0)` silently substitutes the current time

`cache.py:30` uses `ts = timestamp or time.time()`. Unix epoch 0 is falsy, so an explicitly-passed `0` is discarded. Confirmed: passing `timestamp=0` stored `1789029673.57`.

Low practical impact today, but it becomes a real hazard the moment C1 is fixed — a Massive snapshot with a zero/absent timestamp would then be silently backdated to *now* rather than flagged. Use `ts = time.time() if timestamp is None else timestamp`.

### M5 — Cross-thread read of `self._tickers` in the Massive poller

`_fetch_snapshots` (`massive_client.py:123`) runs on a worker thread via `asyncio.to_thread` and passes `self._tickers` — the live list object — to the SDK. Meanwhile `add_ticker` appends to that same list from the event loop. `remove_ticker` rebinds (safe), but `append` during the SDK's iteration is not guaranteed safe. Pass a snapshot: `tickers=list(self._tickers)`, or better, capture the list in `_poll_once` and pass it as an argument.

---

## 4. The Test Suite's Blind Spot

73 tests, 91% coverage, and both critical findings walked straight through. It is worth naming why, because the fix is structural rather than "add more tests".

**C1 survived because the Massive tests construct their own snapshot shape.** `_make_snapshot` (`test_massive.py:11-18`) builds a `MagicMock` and assigns `snap.last_trade.timestamp`. A `MagicMock` grows whatever attribute you touch, so the test asserts that the code can read the field *the test invented* — the very field the real model lacks. The test and the code share one wrong assumption, so they agree perfectly. Coverage went *up* to 94% on this module while its correctness went to zero, which is a good illustration of why the coverage number is not the signal here.

> **Fix:** build fixtures from the real `massive.rest.models.TickerSnapshot` / `LastTrade` classes (they are plain model classes and construct fine offline), or add one contract test asserting the field names the client depends on actually exist on the SDK types. Either would have caught this on day one. `spec=`/`autospec=` on the mocks is the minimum bar.

**C2 survived because nothing tests what the simulator is for.** `test_simulator.py` asserts prices are positive, that they change, that `_pairwise_correlation` returns the right *constants*, and that Cholesky is non-`None`. It never checks that the correlation constants produce correlated *output*, or that `sigma=0.22` produces 22% annualized volatility. Those are the simulator's actual deliverables, and they were 100% and 1600% wrong respectively while every test stayed green.

> **Fix:** add statistical regression tests. Seed the RNG, run ~20k steps with `event_probability=0`, and assert realized correlation and realized annualized σ are within tolerance of target. They are fast (the 20k-step run above takes ~2 s) and they pin the exact property that broke.

**Three further gaps, two carried over from round 1:**

- **`stream.py` at 33% has no tests at all** — the SSE endpoint is the primary consumer of `PriceCache` and the one interface the frontend depends on. It is testable: I exercised it end-to-end against uvicorn in a few lines (see §5). At minimum, assert the content type, the `retry:` preamble, that a cache update produces a `data:` frame, and that the generator terminates on disconnect.
- **No concurrency test for `PriceCache`** despite it being the one deliberately thread-safe component and despite the Massive source genuinely writing from a worker thread.
- **No test builds the full 10-ticker default set.** I checked this one directly and it is fine — the correlation matrix is comfortably positive-definite (min eigenvalue 0.400), and stays PSD with 30–50 unknown tickers added (min eigenvalue 0.40–0.70). So `np.linalg.cholesky` will not raise for realistic watchlists. Worth a cheap test to keep it that way, since a `LinAlgError` here would surface as a 500 on `POST /api/watchlist`.

**Minor test-hygiene items:**
- `asyncio_mode = "auto"` is set in `pyproject.toml`, so the explicit `@pytest.mark.asyncio` decorators in `test_massive.py` and `test_simulator_source.py` are redundant.
- The `event_loop_policy` fixture in `conftest.py` only returns the default policy — it has no effect and can be deleted.
- Several tests reach into private state (`sim._tickers`, `sim._cholesky`, `source._task`, `source._api_key`). Acceptable for white-box unit tests, but `sim._tickers` in `test_add_duplicate_is_noop` now has a public `get_tickers()` to use instead.
- `test_prices_are_positive` runs 10,000 steps to assert `exp()` is positive. It cannot fail. 100 steps would do.

---

## 5. SSE Layer — Verified Behaviour

I ran the stream against a real uvicorn server (`GET /api/stream/prices`) with a live simulator. It works, and the frontend contract is confirmed as:

```
HTTP/1.1 200 OK
cache-control: no-cache
connection: keep-alive
x-accel-buffering: no
content-type: text/event-stream; charset=utf-8
transfer-encoding: chunked

retry: 1000

data: {"AAPL": {"ticker":"AAPL","price":189.96,"previous_price":189.96,"timestamp":...,
       "change":0.0,"change_percent":0.0,"direction":"flat"}, "GOOGL": {...}, ...}
```

Confirmed for `planning/PLAN.md` §A5: **unnamed events** (client uses `onmessage`, not `addEventListener`); **one frame carrying all tickers** keyed by symbol, not one frame per ticker; `retry: 1000` sent once as the first frame; payload includes `change_percent`, which the plan's prose omits.

**Two behaviours the frontend engineer needs to know:**

- **No keepalive during quiet periods.** With the producer frozen, a 6-second connection received 520 bytes — the initial burst and then complete silence. The loop only emits when `price_cache.version` changes. Under the simulator this is a non-issue (the version moves every 500 ms), but with the Massive source outside US market hours, or on a 15-second poll interval, the stream can go silent for a long time. Intermediate proxies and load balancers commonly idle out such connections at 30–60 s. `EventSource` will reconnect, so this self-heals, but it will look like connection flapping in the status indicator. **Recommend a `: keepalive\n\n` comment frame every ~15 s.** This also directly answers the open question in PLAN §A5.
- **`request.is_disconnected()` is not what actually cleans up.** Server logs across two disconnected clients:

  ```
  SSE client connected: 127.0.0.1      x2
  SSE client disconnected: 127.0.0.1   x0
  SSE stream cancelled for: 127.0.0.1  x2
  ```

  Starlette cancels the generator task on disconnect, so the `CancelledError` handler fires and the `is_disconnected()` branch never does. **Cleanup is correct and there is no leak** — but the polling check is effectively dead code, and PLAN §C7's suggested unit test ("the stream generator exits cleanly on client disconnect") should assert the cancellation path, not the `is_disconnected` path.

One design note: every connected client re-serializes the full price dict independently on every version change. Irrelevant for a single-user app; if this ever goes multi-user, serialize once per version in the cache and fan the string out.

---

## 6. Findings Against the Plan's Open Questions

The review notes in `PLAN.md` §13 flag several contract gaps. Three intersect directly with this code.

**A1 — "daily change %" has no source of truth.** Still true, and still blocking the frontend. `PriceUpdate.change_percent` is tick-over-tick (~500 ms), which is not what a watchlist column means. **But the Massive path can supply this for free:** `TickerSnapshot` already carries `todays_change`, `todays_change_percent`, and `prev_day` (an `Agg` with the previous close) — all currently discarded. That turns PLAN option (b) into a few lines for real data, with the simulator seeding an `open_price` at startup to match. Worth doing while `massive_client.py` is open for the C1 fix.

**A2 — tracked ticker set.** The code takes the position the plan warns against: `SimulatorDataSource.remove_ticker` and `MassiveDataSource.remove_ticker` both unconditionally call `self._cache.remove(ticker)`. Remove a ticker from the watchlist while holding a position in it, and its price vanishes from the cache — portfolio valuation then has nothing to value and the position silently disappears from the total. The data-source layer cannot know about positions, so **the guard belongs in the watchlist service**: only call `remove_ticker` when the position quantity is zero. This needs to be written down before the Portfolio agent starts, or it will be an integration bug.

**A3 — unknown tickers.** The simulator accepts anything and assigns `random.uniform(50.0, 300.0)` with default GBM params (`simulator.py:151`), so PLAN's implied "accept any symbol" option is already the de-facto behaviour — but with no validation whatsoever. `ZZZZ`, `zzzz`, `""`, and `"; DROP TABLE"` are all accepted as distinct tickers. Note also that the seed price is **random per process**, so restarting the container re-rolls the price of any non-default ticker, and any position in it will show a wild P&L jump. Validation (1–5 uppercase letters) belongs at the API boundary; a deterministic seed (e.g. hash the symbol into the 50–300 range) belongs in `_add_ticker_internal`.

**A4 — trading a ticker with no cached price.** Not addressed here, and correctly so — it belongs to the Portfolio agent. Worth noting the market layer gives it what it needs: `cache.get_price()` returns `None` unambiguously.

---

## 7. Smaller Observations

- **`PriceCache.version` is read without the lock** (`cache.py:64-67`) — carried over from round 1, unresolved. Harmless under CPython's GIL; inconsistent with every other method on the class. One line to fix.
- **`massive` is a hard runtime dependency** even for the default simulator-only path. Round 1 moved the imports to module level to make the tests patchable, which was the right call for testability but means every user installs the Polygon SDK to run a GBM loop. Acceptable; just be aware it is a deliberate trade, not an oversight.
- **`stream.py` is not wired to anything.** There is no `app/main.py` yet, so the SSE router has never run inside the real application. That is expected at this stage — flagging it so nobody reads "complete" as "integrated".
- **No CI test gate.** `.github/workflows/` contains only the two Claude review actions; nothing runs `pytest` or `ruff` on a PR. Given that this project is explicitly a demonstration of agent-built software, a 15-line workflow running `uv run --extra dev pytest` would be cheap insurance and good pedagogy.
- **`_run_loop` sleeps for a fixed interval after doing work** (`simulator.py:270`), so the tick period is `interval + work_time` and drifts. Immaterial at 500 ms with 10 tickers.
- **The simulator's RNG is the un-seedable NumPy/`random` global state.** Fine for production, but it is why statistical tests need `np.random.seed()` — worth accepting a `seed` parameter on `GBMSimulator` to make the §4 tests robust.
- **`market_data_demo.py` hardcodes the 10-ticker list** (line 30) rather than deriving it from `SEED_PRICES`, which it already imports. Cosmetic drift risk.
- **Concurrency inside the simulator is safe.** `add_ticker`/`remove_ticker` mutate `_tickers`, `_prices` and `_cholesky` while `_run_loop` iterates them, but all four run on the same event loop and none of them `await` mid-mutation, so no interleaving is possible. Correct as written — worth a comment saying so, since it is load-bearing and non-obvious.

---

## 8. Recommended Order of Work

**Must fix before the Massive path is claimed to work**
1. C1 — `sip_timestamp` instead of `timestamp`, `/1e9` instead of `/1000.0`, narrow the exception guard, ERROR-log a 0-of-N poll.
2. Rebuild the `test_massive.py` fixtures on the real SDK models so C1 cannot recur.

**Should fix before the simulator is called representative**
3. C2 — drop `event_probability` to ~1e-5 (or make shocks mean-revert).
4. Add statistical regression tests for realized σ and realized correlation.

**Should fix before the API layer is built on top**
5. M1 — settle ticker normalization in the interface contract and apply it consistently.
6. M3 — move `router` inside `create_stream_router`.
7. A2 — write down the "never untrack a ticker with an open position" rule in `PLAN.md`.
8. Add an SSE keepalive frame, and document the confirmed event shape from §5 in `PLAN.md` §6 (closing A5).

**Worth doing while nearby**
9. M2 (`dt`/`update_interval`), M4 (`timestamp=0`), M5 (cross-thread list), `version` under lock.
10. Surface `prev_day` / `todays_change_percent` from the Massive snapshot to close A1.
11. Add SSE and `PriceCache` concurrency tests; add a `pytest` CI workflow.
12. Refresh the coverage figures in `MARKET_DATA_SUMMARY.md` (91%, not 84%) and drop the "all issues resolved" framing.

---

## 9. Closing Assessment

The architecture is right and the hard parts are done well — the GBM implementation is textbook-correct, the Cholesky approach is the proper way to correlate the moves, the cache/source separation is clean, and the lifecycle handling is disciplined. None of the findings above require rethinking any of that.

What this round shows is a gap between *the code being well-structured* and *the system doing what it says*. One integration point (the Massive SDK's schema) was never checked against reality, and one tuning constant (`event_probability`) was never checked against its own design goals. Both are small edits. The more valuable change is the testing posture in §4 — verifying against real dependency types, and asserting the statistical properties that are the simulator's actual output — because that is what turns "73 tests pass" into evidence.
