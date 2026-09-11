import { test, expect } from "../helpers/fixtures";

/**
 * Chat against the deterministic mock (INTERFACES section 3.1, LLM_MOCK=true).
 * The mock replaces only the model call: trades still run through the real
 * service layer, so a failing trade really fails and really produces an
 * ok:false receipt.
 */
const TICKER = "GOOGL";
const EXTRA = "SHOP"; // not seeded, and not used by the watchlist spec

test.describe("AI chat", () => {
  test.beforeEach(async ({ app }) => {
    await app.open();
    await expect(app.chatPanel).toBeVisible();
  });

  test("a message with no trade in it gets a reply and no chips", async ({ app }) => {
    const chipsBefore = await app.actionChips.count();

    const res = await app.sendChat("how is my portfolio looking");
    expect(res.status, `POST /api/chat -> ${JSON.stringify(res.body)}`).toBe(200);
    expect(res.body.role).toBe("assistant");
    // An assistant turn that executed nothing persists [], never null.
    expect(res.body.actions).toEqual([]);

    await expect(app.chatPanel).toContainText("how is my portfolio looking");
    await expect(app.chatMessages.last()).toContainText("Mock mode");
    expect(await app.actionChips.count()).toBe(chipsBefore);
  });

  test("the input is locked and a loading indicator shows while a turn is in flight", async ({
    app,
    page,
  }) => {
    // Hold the response open so the in-flight state is observable rather than
    // raced against a fast mock. BUILD_CONTRACT B7: a double submit would trade
    // twice, so the input must be disabled meanwhile.
    await page.route("**/api/chat", async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      await new Promise((r) => setTimeout(r, 2_000));
      await route.continue();
    });

    try {
      await app.chatInput.fill("hold on");
      await app.chatSend.click();
      await expect(app.chatLoading).toBeVisible();
      await expect(app.chatInput).toBeDisabled();
      await expect(app.chatLoading).toBeHidden({ timeout: 20_000 });
      await expect(app.chatInput).toBeEnabled();
    } finally {
      await page.unroute("**/api/chat");
    }
  });

  test("a trade the assistant executes appears as a success chip", async ({ app, api }) => {
    const okChipsBefore = await app.actionChipsWhere(true).count();
    const heldBefore = (await api.positionMap())[TICKER] ?? 0;

    const res = await app.sendChat(`buy 1 ${TICKER}`);
    expect(res.status, `POST /api/chat -> ${JSON.stringify(res.body)}`).toBe(200);
    expect(res.body.content).toMatch(new RegExp(`Buying 1(\\.0+)? ${TICKER}`, "i"));
    expect(res.body.actions).toHaveLength(1);
    expect(res.body.actions[0]).toMatchObject({
      type: "trade",
      ok: true,
      ticker: TICKER,
      side: "buy",
    });
    expect(res.body.actions[0].price).toBeGreaterThan(0);

    // The receipt is the authoritative record (BUILD_CONTRACT B6).
    await expect
      .poll(async () => app.actionChipsWhere(true).count(), {
        message: "no success chip rendered for an executed trade",
        timeout: 15_000,
      })
      .toBeGreaterThan(okChipsBefore);
    await expect(app.actionChipsWhere(true).last()).toContainText(TICKER);

    // And the trade really happened, through the same service path as a manual
    // trade (BUILD_CONTRACT B3).
    const heldAfter = (await api.positionMap())[TICKER] ?? 0;
    expect(heldAfter, `chat trade did not add a ${TICKER} share`).toBeCloseTo(heldBefore + 1, 6);
    await expect(app.positionRow(TICKER)).toBeVisible();
  });

  test("a trade that fails validation appears as a failure chip", async ({ app, api }) => {
    const failChipsBefore = await app.actionChipsWhere(false).count();
    const before = await api.portfolio();
    const heldBefore = before.positions.find((p) => p.ticker === TICKER)?.quantity ?? 0;

    const res = await app.sendChat(`buy 99999 ${TICKER}`);
    expect(res.status, `POST /api/chat -> ${JSON.stringify(res.body)}`).toBe(200);
    expect(res.body.actions).toHaveLength(1);
    const action = res.body.actions[0];
    expect(action).toMatchObject({ type: "trade", ok: false, ticker: TICKER, side: "buy" });
    expect(String(action.error), "a failed receipt must carry the service error").not.toBe("");

    await expect
      .poll(async () => app.actionChipsWhere(false).count(), {
        message: "no failure chip rendered for a rejected trade",
        timeout: 15_000,
      })
      .toBeGreaterThan(failChipsBefore);
    await expect(app.actionChipsWhere(false).last()).toContainText(String(action.error));

    // Nothing was bought and cash is untouched.
    const after = await api.portfolio();
    expect(after.positions.find((p) => p.ticker === TICKER)?.quantity ?? 0).toBeCloseTo(
      heldBefore,
      6,
    );
    expect(after.cash).toBeCloseTo(before.cash, 2);
  });

  test("the assistant can add and remove a watchlist ticker", async ({ app, api }) => {
    const added = await app.sendChat(`watch ${EXTRA}`);
    expect(added.status, `POST /api/chat -> ${JSON.stringify(added.body)}`).toBe(200);
    expect(added.body.actions).toHaveLength(1);
    expect(added.body.actions[0]).toMatchObject({
      type: "watchlist",
      ok: true,
      ticker: EXTRA,
      action: "add",
    });
    await expect(app.watchlistRow(EXTRA)).toBeVisible();
    expect((await api.watchlist()).map((t) => t.ticker)).toContain(EXTRA);

    const removed = await app.sendChat(`unwatch ${EXTRA}`);
    expect(removed.status, `POST /api/chat -> ${JSON.stringify(removed.body)}`).toBe(200);
    expect(removed.body.actions[0]).toMatchObject({
      type: "watchlist",
      ok: true,
      ticker: EXTRA,
      action: "remove",
    });
    await expect(app.watchlistRow(EXTRA)).toHaveCount(0);
    expect((await api.watchlist()).map((t) => t.ticker)).not.toContain(EXTRA);
  });
});
