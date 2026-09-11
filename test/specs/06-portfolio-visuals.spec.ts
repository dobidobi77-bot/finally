import { test, expect } from "../helpers/fixtures";
import { dataPoints } from "../helpers/charts";

const TICKERS = ["AAPL", "NVDA"];

/**
 * Charts expose their data, not their rendering (INTERFACES section 5): one
 * heatmap-tile-<T> per position, and data-points="<n>" on the P&L chart.
 * Nothing here counts SVG primitives or canvas pixels.
 */
test.describe("portfolio visualisations", () => {
  test.beforeEach(async ({ api, app }) => {
    for (const ticker of TICKERS) {
      const res = await api.trade(ticker, "buy", 1);
      expect(res.status, `setup buy of ${ticker} failed: ${JSON.stringify(res.body)}`).toBe(200);
    }
    await app.open();
  });

  test("the heatmap renders one tile per position", async ({ app, api }) => {
    await expect(app.heatmap).toBeVisible();
    const positions = (await api.portfolio()).positions;
    expect(positions.length).toBeGreaterThanOrEqual(TICKERS.length);

    for (const position of positions) {
      await expect(
        app.heatmapTile(position.ticker),
        `heatmap-tile-${position.ticker} for an open position - frontend-engineer owns portfolio-heatmap`,
      ).toBeVisible();
    }
    // No tile for a ticker that is not held.
    await expect(app.heatmapTile("MSFT")).toHaveCount(0);
  });

  test("the P&L chart plots the snapshot series", async ({ app, api }) => {
    // The snapshots are the data behind the chart - assert they exist first, so
    // an empty chart can be blamed on the right layer.
    const before = await api.history();
    expect(
      before.snapshots.length,
      "no portfolio snapshots after trading - BUILD_CONTRACT B4 records one per trade",
    ).toBeGreaterThan(0);
    for (const snapshot of before.snapshots) {
      expect(snapshot.total_value).toBeGreaterThan(0);
      expect(Date.parse(snapshot.recorded_at), `unparseable recorded_at ${snapshot.recorded_at}`)
        .not.toBeNaN();
    }

    await expect(app.pnlChart).toBeVisible();
    await expect
      .poll(async () => dataPoints(app.pnlChart), {
        message: "pnl-chart data-points stayed at 0 although snapshots exist",
        timeout: 15_000,
      })
      .toBeGreaterThan(0);
  });

  test("the main chart accumulates points from the price stream", async ({ app }) => {
    await expect(app.mainChart).toBeVisible();
    const first = await dataPoints(app.mainChart);
    await expect
      .poll(async () => dataPoints(app.mainChart), {
        message: "main-chart data-points did not grow while prices were streaming",
        timeout: 15_000,
      })
      .toBeGreaterThan(first);
  });

  test("every trade records a new snapshot", async ({ api }) => {
    const before = (await api.history()).snapshots.length;
    const res = await api.trade("AAPL", "buy", 1);
    expect(res.status, `buy failed: ${JSON.stringify(res.body)}`).toBe(200);

    await expect
      .poll(async () => (await api.history()).snapshots.length, {
        message: "snapshot count did not grow after a trade",
        timeout: 10_000,
      })
      .toBeGreaterThan(before);
  });
});
