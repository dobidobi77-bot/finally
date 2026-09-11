import { test, expect } from "../helpers/fixtures";

const TICKER = "AAPL";
const QUANTITY = 1;

test.describe("buying shares", () => {
  test.beforeEach(async ({ app }) => {
    await app.open();
  });

  test("a buy debits cash, opens a position and keeps the total consistent", async ({
    app,
    api,
  }) => {
    const before = await api.portfolio();
    // Stated precondition rather than a silent assumption: this spec asserts an
    // opening buy, so it needs a flat book in this ticker.
    expect(
      before.positions.find((p) => p.ticker === TICKER),
      `${TICKER} was already held before the opening buy`,
    ).toBeUndefined();

    const res = await app.submitTrade(TICKER, QUANTITY, "buy");
    expect(res.status, `POST /api/portfolio/trade -> ${JSON.stringify(res.body)}`).toBe(200);
    expect(res.body.ok).toBe(true);
    expect(res.body.trade).toMatchObject({ ticker: TICKER, side: "buy", quantity: QUANTITY });

    const fill = res.body.trade.price as number;
    expect(fill, "fill price must never be zero - BUILD_CONTRACT A4").toBeGreaterThan(0);

    // Cash: exactly the fill, no fees (PLAN.md section 2).
    expect(res.body.portfolio.cash).toBeCloseTo(
      Number((before.cash - fill * QUANTITY).toFixed(2)),
      2,
    );
    expect(res.body.portfolio.cash).toBeLessThan(before.cash);

    // The header must catch up with the server.
    await expect
      .poll(async () => app.cash(), {
        message: "header cash never fell after the buy",
        timeout: 15_000,
      })
      .toBeLessThan(before.cash);
    expect(await app.cash()).toBeCloseTo(res.body.portfolio.cash, 2);

    // The position appears in the table and in the portfolio payload.
    await expect(app.positionsTable).toBeVisible();
    await expect(app.positionRow(TICKER)).toBeVisible();
    const after = await api.portfolio();
    const position = after.positions.find((p) => p.ticker === TICKER);
    expect(position, `no ${TICKER} position after the buy`).toBeDefined();
    expect(position!.quantity).toBeCloseTo(QUANTITY, 6);
    expect(position!.avg_cost).toBeCloseTo(fill, 2);

    // Total value: cash became stock, so the total is conserved apart from
    // price drift between the fill and this read.
    expect(Math.abs(after.total_value - before.total_value) / before.total_value).toBeLessThan(0.02);
    await expect
      .poll(async () => Math.abs((await app.total()) - (await api.portfolio()).total_value), {
        message: "header total value never converged on GET /api/portfolio",
        timeout: 15_000,
      })
      .toBeLessThan(Math.max(1, after.total_value * 0.02));
  });
});
