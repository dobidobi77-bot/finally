import { resetApp } from "./appctl";
import { BASE_URL } from "../playwright.config";

/**
 * Put the app into a known state before the suite runs: a deleted database and
 * a restart in test mode (INTERFACES 7.1 and 6.2). Every assertion downstream
 * is then unconditional - the $10,000 fresh-start check is a hard assertion,
 * never a conditional skip.
 *
 * The script exits non-zero on failure, so a broken environment fails setup
 * loudly here instead of surfacing as 25 mysterious test failures.
 */
export default async function globalSetup(): Promise<void> {
  if (process.env.E2E_SKIP_RESET === "1") {
    // Escape hatch for iterating on a single spec against an app you already
    // have running. Never used in a full run.
    console.log("[e2e] E2E_SKIP_RESET=1 - reusing the running app, state is not fresh");
    const { confirmReady } = await import("./appctl");
    const health = await confirmReady(Number(process.env.E2E_READY_TIMEOUT_MS ?? 30_000));
    console.log(`[e2e] app ready at ${BASE_URL} - market_source=${health.market_source}`);
    return;
  }

  console.log("[e2e] resetting the app (scripts/reset --yes --test)");
  const health = await resetApp();
  console.log(
    `[e2e] app ready at ${BASE_URL} - market_source=${health.market_source}, ` +
      `cache_ready=${health.cache_ready}`,
  );
}
