import type { APIRequestContext } from "@playwright/test";

/** Body of GET /api/health (BUILD_CONTRACT B14). */
export interface Health {
  status: string;
  market_source: "simulator" | "massive";
  cache_ready: boolean;
}

/**
 * Poll GET /api/health until status is "ok" and the price cache holds at least
 * one price. This is the only readiness gate the suite uses - never a sleep,
 * never a guess at the UI (BUILD_CONTRACT B14, INTERFACES section 7).
 */
export async function waitForAppReady(
  api: APIRequestContext,
  timeoutMs = 60_000,
): Promise<Health> {
  const deadline = Date.now() + timeoutMs;
  let lastProblem = "no request attempted";

  while (Date.now() < deadline) {
    try {
      const res = await api.get("/api/health", { timeout: 5_000 });
      if (!res.ok()) {
        lastProblem = `GET /api/health returned ${res.status()}: ${await res.text()}`;
      } else {
        const body = (await res.json()) as Health;
        if (body.status === "ok" && body.cache_ready === true) return body;
        lastProblem = `health not ready: ${JSON.stringify(body)}`;
      }
    } catch (err) {
      lastProblem = `request failed: ${(err as Error).message}`;
    }
    await new Promise((r) => setTimeout(r, 500));
  }

  throw new Error(
    `App not ready within ${timeoutMs}ms. Last problem: ${lastProblem}\n` +
      `Start the app first (docker compose up), then re-run the suite.`,
  );
}
