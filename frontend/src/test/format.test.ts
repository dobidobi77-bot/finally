import { describe, expect, it } from "vitest";
import {
  dailyChangePercent,
  fmtMoney,
  fmtPercent,
  fmtQuantity,
  fmtSigned,
  signDirection,
} from "@/lib/format";

describe("formatting", () => {
  it("renders money with two decimals and thousands separators", () => {
    expect(fmtMoney(1234.5)).toBe("1,234.50");
    expect(fmtMoney(0)).toBe("0.00");
    expect(fmtMoney(null)).toBe("--");
  });

  it("signs P&L figures explicitly", () => {
    expect(fmtSigned(50)).toBe("+50.00");
    expect(fmtSigned(-50)).toBe("-50.00");
    expect(fmtSigned(0)).toBe("0.00");
  });

  it("formats percentages with a sign", () => {
    expect(fmtPercent(2.6316)).toBe("+2.63%");
    expect(fmtPercent(-1)).toBe("-1.00%");
    expect(fmtPercent(null)).toBe("--");
  });

  it("trims trailing zeros from quantities", () => {
    expect(fmtQuantity(10)).toBe("10");
    expect(fmtQuantity(0.5)).toBe("0.5");
    expect(fmtQuantity(1.0000004)).toBe("1");
  });

  it("computes the daily change against the session open (A1)", () => {
    expect(dailyChangePercent(195, 190)).toBeCloseTo(2.6316, 3);
    expect(dailyChangePercent(170, 175)).toBeCloseTo(-2.8571, 3);
  });

  it("returns null when the backend has not supplied an open price", () => {
    expect(dailyChangePercent(195, null)).toBeNull();
    expect(dailyChangePercent(195, 0)).toBeNull();
    expect(dailyChangePercent(null, 190)).toBeNull();
  });

  it("maps signs onto directions", () => {
    expect(signDirection(1)).toBe("up");
    expect(signDirection(-1)).toBe("down");
    expect(signDirection(0)).toBe("flat");
    expect(signDirection(null)).toBe("flat");
  });
});
