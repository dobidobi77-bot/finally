/** Number formatting shared by every readout in the terminal. */

const money2 = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** 1234.5 -> "1,234.50" */
export function fmtMoney(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "--";
  return money2.format(value);
}

/** Money with an explicit sign, for P&L figures. */
export function fmtSigned(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "--";
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  return `${sign}${money2.format(Math.abs(value))}`;
}

/** 1.234 -> "+1.23%" */
export function fmtPercent(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "--";
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  return `${sign}${Math.abs(value).toFixed(digits)}%`;
}

/** Trims trailing zeros so 10 shows as "10" but 0.5 stays "0.5". */
export function fmtQuantity(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "--";
  return String(Number(value.toFixed(6)));
}

/**
 * Daily change against the session baseline (BUILD_CONTRACT A1).
 * Returns null when the backend has not supplied an open price yet.
 */
export function dailyChangePercent(
  price: number | null | undefined,
  openPrice: number | null | undefined,
): number | null {
  if (price === null || price === undefined) return null;
  if (openPrice === null || openPrice === undefined || openPrice === 0) return null;
  return ((price - openPrice) / openPrice) * 100;
}

/** "up" | "down" | "flat" from any signed number. */
export function signDirection(value: number | null | undefined): "up" | "down" | "flat" {
  if (value === null || value === undefined || value === 0 || !Number.isFinite(value)) {
    return "flat";
  }
  return value > 0 ? "up" : "down";
}

/** Clock time for chat bubbles and chart axes. */
export function fmtClock(iso: string | number): string {
  const d = typeof iso === "number" ? new Date(iso * 1000) : new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
}
