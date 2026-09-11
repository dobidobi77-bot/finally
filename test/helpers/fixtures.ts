import { test as base } from "@playwright/test";
import { Api } from "./api";
import { App } from "./app";
import { waitForAppReady } from "./health";

/**
 * Every spec runs through these fixtures, so the health gate cannot be
 * forgotten: `ready` is automatic and blocks the test until the price cache is
 * populated (BUILD_CONTRACT B14).
 */
export const test = base.extend<{ app: App; api: Api; ready: void }>({
  api: async ({ request }, use) => {
    await use(new Api(request));
  },
  app: async ({ page }, use) => {
    await use(new App(page));
  },
  ready: [
    async ({ request }, use) => {
      await waitForAppReady(request, 30_000);
      await use();
    },
    { auto: true },
  ],
});

export { expect } from "@playwright/test";
