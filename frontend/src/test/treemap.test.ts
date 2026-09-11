import { describe, expect, it } from "vitest";
import { squarify } from "@/lib/treemap";

describe("squarify", () => {
  const items = [
    { value: 50, data: "A" },
    { value: 30, data: "B" },
    { value: 20, data: "C" },
  ];

  it("fills the whole box", () => {
    const rects = squarify(items, 400, 200);
    const area = rects.reduce((sum, rect) => sum + rect.width * rect.height, 0);
    expect(area).toBeCloseTo(400 * 200, 3);
  });

  it("sizes rectangles in proportion to their value", () => {
    const rects = squarify(items, 400, 200);
    const byTicker = Object.fromEntries(rects.map((rect) => [rect.data, rect.width * rect.height]));
    expect(byTicker.A / byTicker.C).toBeCloseTo(50 / 20, 3);
  });

  it("keeps every rectangle inside the box", () => {
    for (const rect of squarify(items, 400, 200)) {
      expect(rect.x).toBeGreaterThanOrEqual(-1e-6);
      expect(rect.y).toBeGreaterThanOrEqual(-1e-6);
      expect(rect.x + rect.width).toBeLessThanOrEqual(400 + 1e-6);
      expect(rect.y + rect.height).toBeLessThanOrEqual(200 + 1e-6);
    }
  });

  it("drops non-positive values and tolerates an empty box", () => {
    expect(squarify([{ value: 0, data: "A" }], 400, 200)).toEqual([]);
    expect(squarify(items, 0, 200)).toEqual([]);
    expect(squarify([], 400, 200)).toEqual([]);
  });
});
