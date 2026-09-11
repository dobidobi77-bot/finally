import { defineConfig, devices } from "@playwright/test";

/**
 * FinAlly E2E configuration.
 *
 * The app is expected to be already running at BASE_URL (docker compose up).
 * There is no webServer block on purpose: the container is owned by devops and
 * the suite must be able to run against any deployed instance.
 *
 * Single worker, no parallelism, no retries. The app is single-user: every spec
 * mutates one shared portfolio, watchlist and chat log, and there is no
 * state-reset endpoint. Parallel workers or a retry would replay trades against
 * a portfolio a previous attempt already changed.
 */
export const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:8000";

export default defineConfig({
  testDir: "./specs",
  globalSetup: require.resolve("./helpers/global-setup"),
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: !!process.env.CI,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    baseURL: BASE_URL,
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
