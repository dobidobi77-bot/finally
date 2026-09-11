import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { promisify } from "node:util";
import { request } from "@playwright/test";
import { BASE_URL } from "../playwright.config";
import { waitForAppReady, type Health } from "./health";

const run = promisify(execFile);
const ROOT = path.resolve(__dirname, "..", "..");

/**
 * Lifecycle control for the app under test.
 *
 * There is no state-reset API endpoint and there will not be one (INTERFACES
 * 7.1), so the suite drives the devops scripts. Both are invoked with `--test`
 * so the compose override in INTERFACES 6.2 is layered on: the simulator and
 * the mock LLM, without anyone editing the user's .env.
 *
 * `docker compose config` is never run from here - it prints resolved env_file
 * values including real API keys in plaintext.
 */

/** Prefer PowerShell on Windows; override with E2E_SCRIPT_FLAVOR=sh|ps1. */
function flavour(): "sh" | "ps1" {
  const override = process.env.E2E_SCRIPT_FLAVOR;
  if (override === "sh" || override === "ps1") return override;
  return process.platform === "win32" ? "ps1" : "sh";
}

function scriptPath(name: string): string {
  const file = path.join(ROOT, "scripts", `${name}.${flavour()}`);
  if (!existsSync(file)) {
    throw new Error(
      `Missing ${path.relative(ROOT, file)}. The E2E suite drives the app through this ` +
        `script (INTERFACES.md section 7.1) - devops-engineer owns scripts/. ` +
        `Set E2E_SCRIPT_FLAVOR=sh to use the bash variant instead.`,
    );
  }
  return file;
}

async function invoke(name: string, args: string[], timeoutMs: number): Promise<void> {
  const file = scriptPath(name);
  const [command, commandArgs] =
    flavour() === "ps1"
      ? ["powershell", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", file, ...args]]
      : ["bash", [file, ...args]];

  try {
    await run(command as string, commandArgs as string[], {
      cwd: ROOT,
      timeout: timeoutMs,
      windowsHide: true,
    });
  } catch (err) {
    const e = err as { stdout?: string; stderr?: string; message: string };
    throw new Error(
      `scripts/${name}.${flavour()} ${args.join(" ")} failed: ${e.message}\n` +
        `stdout: ${(e.stdout ?? "").trim()}\nstderr: ${(e.stderr ?? "").trim()}`,
    );
  }
}

/** Poll health after a lifecycle change and confirm the test-mode market source. */
export async function confirmReady(timeoutMs = 90_000): Promise<Health> {
  const api = await request.newContext({ baseURL: BASE_URL });
  try {
    const health = await waitForAppReady(api, timeoutMs);
    assertTestMode(health);
    return health;
  } finally {
    await api.dispose();
  }
}

/**
 * Fail loudly when the test-mode override is not in effect. Real market data is
 * non-deterministic, rate-limited and flat outside US market hours, and a real
 * LLM costs money on every chat spec - a clear setup failure beats a suite that
 * silently goes flaky and expensive.
 */
export function assertTestMode(health: Health): void {
  if (health.market_source !== "simulator") {
    throw new Error(
      `market_source is "${health.market_source}", expected "simulator". The app was started ` +
        `without the test override. Start it with the -f docker-compose.test.yml layer ` +
        `(INTERFACES.md section 6.2), or let globalSetup call scripts/reset --yes --test.`,
    );
  }
}

/**
 * Prove the reset actually produced a fresh database instead of reporting
 * success while changing nothing.
 *
 * This is not paranoia: the database lives in the named Docker volume
 * `finally-data`, so deleting host files under `db/` is a silent no-op. Without
 * this check that mistake surfaces as a confusing fresh-start assertion failure
 * on the second run onward.
 */
export async function assertFreshState(): Promise<void> {
  const api = await request.newContext({ baseURL: BASE_URL });
  try {
    const portfolio = await (await api.get("/api/portfolio")).json();
    const chat = await (await api.get("/api/chat?limit=20")).json();
    const problems: string[] = [];
    if (portfolio.cash !== 10000) problems.push(`cash is ${portfolio.cash}, expected 10000`);
    if ((portfolio.positions ?? []).length > 0) {
      problems.push(`${portfolio.positions.length} open positions`);
    }
    if ((chat.messages ?? []).length > 0) problems.push(`${chat.messages.length} chat messages`);

    if (problems.length > 0) {
      throw new Error(
        `scripts/reset reported success but the state is not fresh: ${problems.join(", ")}. ` +
          `The database lives in the named volume finally-data (docker-compose.yml), not in ` +
          `./db, so reset must remove that volume - deleting host files under db/ does nothing.`,
      );
    }
  } finally {
    await api.dispose();
  }
}

/** Delete the database and restart in test mode. Used once, from globalSetup. */
export async function resetApp(): Promise<Health> {
  await invoke("reset", ["--yes", "--test"], 300_000);
  const health = await confirmReady();
  await assertFreshState();
  return health;
}

/**
 * Restart in test mode WITHOUT touching the database - the opposite of reset.
 * The restart-persistence spec needs the data to survive the bounce.
 */
export async function restartApp(): Promise<Health> {
  await invoke("restart", ["--yes", "--test"], 300_000);
  return confirmReady();
}
