import { test, expect } from "../helpers/fixtures";
import { DEFAULT_TICKERS } from "../helpers/app";

/**
 * Fresh start: the seeded watchlist, the seeded cash, and live prices.
 * Read-only - this spec never trades, so it can run first against a clean
 * database and leave it clean.
 */
test.describe("fresh start", () => {
  test.beforeEach(async ({ app }) => {
    await app.open();
  });

  test("the ten seeded tickers are listed, and only those ten", async ({ app, api }) => {
    await expect(app.watchlist).toBeVisible();
    for (const ticker of DEFAULT_TICKERS) {
      await expect(app.watchlistRow(ticker), `watchlist row for ${ticker}`).toBeVisible();
    }
    // Exactly ten on a fresh database - a longer list means the seed ran twice.
    expect((await api.watchlist()).map((t) => t.ticker).sort()).toEqual([...DEFAULT_TICKERS].sort());
  });

  test("the header shows the $10,000 seed cash and no positions", async ({ app, api }) => {
    // globalSetup deleted the database and restarted, so this is unconditional.
    const portfolio = await api.portfolio();
    expect(portfolio.cash).toBe(10000);
    expect(portfolio.positions).toEqual([]);
    expect(portfolio.total_value).toBe(10000);

    expect(await app.cash()).toBeCloseTo(10000, 2);
    await expect(app.positionRow("AAPL")).toHaveCount(0);
  });

  test("header cash and total value agree with GET /api/portfolio", async ({ app, api }) => {
    const portfolio = await api.portfolio();
    expect(await app.cash()).toBeCloseTo(portfolio.cash, 2);
    // Total value moves with every tick, so compare within a tolerance wide
    // enough for a few ticks of drift but far too narrow to hide a real bug.
    const uiTotal = await app.total();
    expect(Math.abs(uiTotal - portfolio.total_value) / portfolio.total_value).toBeLessThan(0.02);
  });

  test("the connection indicator reports a live stream", async ({ app }) => {
    await expect(app.connectionStatus).toHaveAttribute("data-state", "connected");
  });

  test("prices stream into the watchlist", async ({ app }) => {
    const cell = app.watchlistPrice("AAPL");
    await expect(cell).toBeVisible();
    const first = await cell.textContent();
    expect(first?.trim(), "price cell should render a price on load").toBeTruthy();

    // Assert movement, not a value: the simulator ticks about twice a second.
    await expect
      .poll(async () => cell.textContent(), {
        message: `watchlist price for AAPL never changed from ${first}`,
        timeout: 20_000,
        intervals: [250],
      })
      .not.toBe(first);
  });
});
