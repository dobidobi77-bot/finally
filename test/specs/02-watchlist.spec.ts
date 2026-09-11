import { test, expect } from "../helpers/fixtures";

const EXTRA = "PYPL"; // a real symbol with no seed price - BUILD_CONTRACT A3
// Both fail ^[A-Z]{1,5}$: one on a digit, one on length. The six-letter case
// only reaches the backend if the add input does not clip it client-side.
const MALFORMED = "AB1";
const MALFORMED_ALL = ["AB1", "ZZZZZZ"];

test.describe("watchlist", () => {
  test("a malformed ticker is rejected by the API", async ({ api }) => {
    const res = await api.addTicker(MALFORMED);
    expect(res.status).toBe(400);
    expect(res.body).toHaveProperty("error");
    expect((await api.watchlist()).map((t) => t.ticker)).not.toContain(MALFORMED);
  });

  // Everything below needs the served frontend.
  test.describe("through the UI", () => {
    test.beforeEach(async ({ app }) => {
      await app.open();
    });

    test("a ticker can be added and removed", async ({ app, api }) => {
      await expect(app.watchlistRow(EXTRA)).toHaveCount(0);

      const added = await app.submitWatchlistAdd(EXTRA);
      expect(added.status, `POST /api/watchlist -> ${JSON.stringify(added.body)}`).toBe(200);
      expect(added.body).toMatchObject({ ok: true, ticker: EXTRA });

      await expect(app.watchlistRow(EXTRA)).toBeVisible();
      // An unseeded symbol still has to get a price (seeded at 100.00 per A3).
      await expect
        .poll(async () => (await app.watchlistPrice(EXTRA).textContent())?.trim(), {
          message: `${EXTRA} was added but never received a price`,
          timeout: 20_000,
        })
        .toBeTruthy();
      expect((await api.watchlist()).map((t) => t.ticker)).toContain(EXTRA);

      const removed = await app.submitWatchlistRemove(EXTRA);
      expect(
        removed.status,
        `DELETE /api/watchlist/${EXTRA} -> ${JSON.stringify(removed.body)}`,
      ).toBe(200);
      await expect(app.watchlistRow(EXTRA)).toHaveCount(0);
      expect((await api.watchlist()).map((t) => t.ticker)).not.toContain(EXTRA);
    });

    for (const symbol of MALFORMED_ALL) {
      test(`a malformed ticker (${symbol}) shows the backend error`, async ({ app }) => {
        // No error region before anything goes wrong.
        await expect(app.watchlistError).toHaveCount(0);

        await app.watchlistAddInput.fill(symbol);
        // If the input clips the value client-side the request would be valid and
        // this test would pass for the wrong reason - fail here instead, loudly.
        await expect(
          app.watchlistAddInput,
          "the add input must let a malformed symbol through so the backend can reject it",
        ).toHaveValue(symbol);

        const res = await app.submitWatchlistAdd(symbol);
        expect(res.status, `POST /api/watchlist -> ${JSON.stringify(res.body)}`).toBe(400);
        expect(res.body.error).toBe("Invalid ticker format");

        // INTERFACES section 5: the region renders the backend string verbatim.
        await expect(app.watchlistError).toBeVisible();
        await expect(app.watchlistError).toContainText("Invalid ticker format");
        await expect(app.watchlistRow(symbol)).toHaveCount(0);
      });
    }
  });
});
