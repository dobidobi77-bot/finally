import { test, expect } from "../helpers/fixtures";
import { restartApp } from "../helpers/appctl";
import { DEFAULT_TICKERS } from "../helpers/app";

/**
 * The app must never undo a user's changes on restart.
 *
 * Seeding is meant to fire only for a genuinely new database. If it instead
 * fires whenever a table happens to be empty, removing every watchlist ticker
 * and restarting silently brings all ten back - a user's deletions reversed by
 * a bounce. These tests restart WITHOUT resetting, which is the opposite of
 * what globalSetup does, and assert the state survived.
 *
 * Runs last: a restart is disruptive to anything sharing the app.
 */
const REMOVED = "JPM"; // no position in it, so removal really untracks it
const HELD = "V";

test.describe.serial("persistence across a restart", () => {
  test.slow(); // a container bounce takes far longer than a normal action

  test("a removed ticker stays removed", async ({ app, api }) => {
    const before = (await api.watchlist()).map((t) => t.ticker);
    expect(before, `${REMOVED} should be in the seeded watchlist`).toContain(REMOVED);

    const removed = await api.removeTicker(REMOVED);
    expect(removed.status, `DELETE failed: ${JSON.stringify(removed.body)}`).toBe(200);
    expect((await api.watchlist()).map((t) => t.ticker)).not.toContain(REMOVED);

    await restartApp();

    const after = (await api.watchlist()).map((t) => t.ticker);
    expect(
      after,
      `${REMOVED} came back after a restart - seeding must be gated on a NEW database, ` +
        `not on an empty table (db-engineer owns app/db/init.py)`,
    ).not.toContain(REMOVED);
    // The survivors are still there exactly once, not re-seeded alongside.
    expect(after.sort()).toEqual(before.filter((t) => t !== REMOVED).sort());

    await app.open();
    await expect(app.watchlistRow(REMOVED)).toHaveCount(0);
  });

  test("a position and the cash balance survive", async ({ app, api }) => {
    const buy = await api.trade(HELD, "buy", 2);
    expect(buy.status, `setup buy failed: ${JSON.stringify(buy.body)}`).toBe(200);

    const before = await api.portfolio();
    const position = before.positions.find((p) => p.ticker === HELD);
    expect(position, `no ${HELD} position after the buy`).toBeDefined();
    expect(before.cash).toBeLessThan(10000);

    await restartApp();

    const after = await api.portfolio();
    expect(after.cash, "cash was reset by a restart").toBeCloseTo(before.cash, 2);
    const survivor = after.positions.find((p) => p.ticker === HELD);
    expect(survivor, `the ${HELD} position vanished across a restart`).toBeDefined();
    expect(survivor!.quantity).toBeCloseTo(position!.quantity, 6);
    expect(survivor!.avg_cost).toBeCloseTo(position!.avg_cost, 6);

    await app.open();
    await expect(app.positionRow(HELD)).toBeVisible();
    expect(await app.cash()).toBeCloseTo(before.cash, 2);
  });

  test("the chat log survives", async ({ app, api }) => {
    const probe = `restart probe ${Date.now()}`;
    const sent = await api.sendChat(probe);
    expect(sent.status, `POST /api/chat -> ${JSON.stringify(sent.body)}`).toBe(200);

    await restartApp();

    expect((await api.chatHistory()).map((m) => m.content)).toContain(probe);
    await app.open();
    await expect(app.chatPanel).toContainText(probe);
  });

  test("the seeded watchlist is not duplicated by a restart", async ({ api }) => {
    // A re-seed on a populated database would show up as repeated tickers.
    const tickers = (await api.watchlist()).map((t) => t.ticker);
    expect(new Set(tickers).size, `duplicate tickers in the watchlist: ${tickers}`).toBe(
      tickers.length,
    );
    for (const ticker of DEFAULT_TICKERS) {
      if (ticker === REMOVED) continue;
      expect(tickers, `${ticker} disappeared`).toContain(ticker);
    }
  });
});
