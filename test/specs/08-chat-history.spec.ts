import { test, expect } from "../helpers/fixtures";

const TICKER = "NFLX";

/**
 * A refresh must not lose the conversation (BUILD_CONTRACT A6): the frontend
 * calls GET /api/chat on load and renders history through the same path as a
 * live reply.
 */
test.describe("chat history", () => {
  test("a message is still there after a reload", async ({ app, api }) => {
    await app.open();
    const probe = `history probe ${Date.now()}`;

    const res = await app.sendChat(probe);
    expect(res.status, `POST /api/chat -> ${JSON.stringify(res.body)}`).toBe(200);
    await expect(app.chatPanel).toContainText(probe);

    await app.page.reload();
    await expect(app.chatPanel).toBeVisible();
    await expect(app.chatPanel, "the conversation did not survive a reload").toContainText(probe);

    const messages = await api.chatHistory();
    expect(messages.map((m) => m.content)).toContain(probe);
  });

  test("action receipts are still rendered after a reload", async ({ app, api }) => {
    await app.open();

    const res = await app.sendChat(`buy 1 ${TICKER}`);
    expect(res.status, `POST /api/chat -> ${JSON.stringify(res.body)}`).toBe(200);
    expect(res.body.actions[0]).toMatchObject({ type: "trade", ok: true, ticker: TICKER });

    await app.page.reload();
    await expect(app.chatPanel).toBeVisible();
    await expect
      .poll(async () => app.actionChipsWhere(true).count(), {
        message: "no success chip after a reload - actions are not being replayed from GET /api/chat",
        timeout: 15_000,
      })
      .toBeGreaterThan(0);
    await expect(app.actionChipsWhere(true).last()).toContainText(TICKER);

    const stored = await api.chatHistory();
    const withTicker = stored.filter((m) =>
      (m.actions ?? []).some((a) => a.type === "trade" && a.ticker === TICKER),
    );
    expect(withTicker.length, "the trade receipt was not persisted with the message").toBeGreaterThan(
      0,
    );
  });

  test("GET /api/chat returns at most 20 messages, oldest first", async ({ api }) => {
    // BUILD_CONTRACT B5 and A6.
    const messages = await api.chatHistory();
    expect(messages.length).toBeLessThanOrEqual(20);
    const times = messages.map((m) => Date.parse(m.created_at));
    for (const t of times) expect(t, "unparseable created_at").not.toBeNaN();
    expect(times, "messages must be returned oldest first").toEqual([...times].sort((a, b) => a - b));

    // The actions null-vs-empty convention: null means "user message",
    // [] means "the assistant executed nothing".
    for (const message of messages) {
      if (message.role === "user") {
        expect(message.actions, `user message ${message.id} must have null actions`).toBeNull();
      } else {
        expect(
          Array.isArray(message.actions),
          `assistant message ${message.id} must have an array of actions, got ${JSON.stringify(message.actions)}`,
        ).toBe(true);
      }
    }
  });
});
