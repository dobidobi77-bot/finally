import { test, expect } from "../helpers/fixtures";

const TICKER = "TSLA";

test.describe("trade validation", () => {
  test("a non-positive quantity is rejected", async ({ api }) => {
    // BUILD_CONTRACT B3, checked at the API since the UI may block the input.
    for (const quantity of [0, -1]) {
      const res = await api.trade(TICKER, "buy", quantity);
      expect(res.status, `quantity ${quantity} -> ${JSON.stringify(res.body)}`).toBe(400);
      expect(res.body).toHaveProperty("error");
    }
  });

  // Everything below needs the served frontend.
  test.describe("through the UI", () => {
    test.beforeEach(async ({ app }) => {
      await app.open();
    });

    test("a buy the cash cannot cover is rejected and shown", async ({ app, api }) => {
      const before = await api.portfolio();
      const heldBefore = before.positions.find((p) => p.ticker === TICKER)?.quantity ?? 0;
      await expect(app.tradeError).toHaveCount(0);

      // A million shares is unaffordable at any seed price and any cash balance
      // this suite can reach.
      const res = await app.submitTrade(TICKER, 1_000_000, "buy");
      expect(res.status, `expected a 4xx, got ${JSON.stringify(res.body)}`).toBe(400);
      expect(res.body).toHaveProperty("error");

      await expect(app.tradeError).toBeVisible();
      await expect(app.tradeError).toContainText(String(res.body.error));

      // Nothing moved: no new shares, no cash change.
      const after = await api.portfolio();
      expect(after.positions.find((p) => p.ticker === TICKER)?.quantity ?? 0).toBeCloseTo(
        heldBefore,
        6,
      );
      expect(after.cash).toBeCloseTo(before.cash, 2);
    });

    test("a sell of more shares than held is rejected and shown", async ({ app, api }) => {
      // Set up the precondition explicitly: whatever is held, try to sell more.
      const held = (await api.positionMap())[TICKER] ?? 0;
      if (held === 0) {
        const setup = await api.trade(TICKER, "buy", 1);
        expect(setup.status, `setup buy failed: ${JSON.stringify(setup.body)}`).toBe(200);
      }
      const before = await api.portfolio();
      const heldBefore = before.positions.find((p) => p.ticker === TICKER)!.quantity;

      const res = await app.submitTrade(TICKER, heldBefore + 5, "sell");
      expect(res.status, `expected a 4xx, got ${JSON.stringify(res.body)}`).toBe(400);
      expect(res.body).toHaveProperty("error");

      await expect(app.tradeError).toBeVisible();
      await expect(app.tradeError).toContainText(String(res.body.error));

      // The held shares are still there and cash is untouched.
      const after = await api.portfolio();
      const position = after.positions.find((p) => p.ticker === TICKER);
      expect(position, "the rejected sell must leave the position intact").toBeDefined();
      expect(position!.quantity).toBeCloseTo(heldBefore, 6);
      expect(after.cash).toBeCloseTo(before.cash, 2);
    });
  });
});
