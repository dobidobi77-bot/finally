import type { Locator } from "@playwright/test";

/**
 * Read the `data-points` attribute a chart container publishes (INTERFACES
 * section 5): the number of points actually plotted, with 0 rendered honestly
 * for an empty chart.
 *
 * This is the whole chart contract. The suite does not count rendering
 * primitives - that couples a test to an implementation nobody froze, breaks on
 * a purely visual refactor, and proves nothing about the data behind the chart.
 */
export async function dataPoints(chart: Locator): Promise<number> {
  const raw = await chart.getAttribute("data-points");
  if (raw === null) {
    throw new Error(
      `chart is missing its data-points attribute (INTERFACES section 5) - ` +
        `frontend-engineer owns this. 0 must be rendered, not omitted.`,
    );
  }
  const value = Number(raw);
  if (!Number.isInteger(value) || value < 0) {
    throw new Error(`data-points should be a non-negative integer, got ${JSON.stringify(raw)}`);
  }
  return value;
}
