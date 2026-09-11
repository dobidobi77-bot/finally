import { test, expect } from "../helpers/fixtures";

const TICKER = "MSFT";

/**
 * Each test builds its own position through the API - the buy is setup, not the
 * thing under test - and asserts on deltas, so it does not care what earlier
 * specs left behind.
 */
test.describe("selling shares", () => {
  test("a partial sell credits cash and leaves the position open", async ({ app, api }) => {
    const setup = await api.trade(TICKER, "buy", 2);
    expect(setup.status, `setup buy failed: ${JSON.stringify(setup.body)}`).toBe(200);

    await app.open();
    await expect(app.positionRow(TICKER)).toBeVisible();
    const before = await api.portfolio();
    const heldBefore = before.positions.find((p) => p.ticker === TICKER)!;

    const res = await app.submitTrade(TICKER, 1, "sell");
    expect(res.status, `POST /api/portfolio/trade -> ${JSON.stringify(res.body)}`).toBe(200);
    expect(res.body.trade).toMatchObject({ ticker: TICKER, side: "sell", quantity: 1 });

    const fill = res.body.trade.price as number;
    expect(res.body.portfolio.cash).toBeCloseTo(Number((before.cash + fill).toFixed(2)), 2);
    expect(res.body.portfolio.cash).toBeGreaterThan(before.cash);

    await expect
      .poll(async () => app.cash(), {
        message: "header cash never rose after the sell",
        timeout: 15_000,
      })
      .toBeGreaterThan(before.cash);

    // Shares remain, so the row stays and the quantity drops by exactly one.
    await expect(app.positionRow(TICKER)).toBeVisible();
    const position = (await api.portfolio()).positions.find((p) => p.ticker === TICKER);
    expect(position, `${TICKER} position disappeared after a partial sell`).toBeDefined();
    expect(position!.quantity).toBeCloseTo(heldBefore.quantity - 1, 6);
    // A sell never moves avg_cost (BUILD_CONTRACT B1).
    expect(position!.avg_cost).toBeCloseTo(heldBefore.avg_cost, 6);
  });

  test("selling the whole position removes the row", async ({ app, api }) => {
    const held = (await api.positionMap())[TICKER] ?? 0;
    if (held === 0) {
      const setup = await api.trade(TICKER, "buy", 1);
      expect(setup.status, `setup buy failed: ${JSON.stringify(setup.body)}`).toBe(200);
    }
    const quantity = (await api.positionMap())[TICKER];
    expect(quantity, `no ${TICKER} position to close`).toBeGreaterThan(0);

    await app.open();
    await expect(app.positionRow(TICKER)).toBeVisible();

    const res = await app.submitTrade(TICKER, quantity, "sell");
    expect(res.status, `POST /api/portfolio/trade -> ${JSON.stringify(res.body)}`).toBe(200);

    await expect(app.positionRow(TICKER)).toHaveCount(0);
    // BUILD_CONTRACT B2: the row is deleted, not left as a 1e-15 residue.
    const tickers = (await api.portfolio()).positions.map((p) => p.ticker);
    expect(tickers).not.toContain(TICKER);
  });
});
