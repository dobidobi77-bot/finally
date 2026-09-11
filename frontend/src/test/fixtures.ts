/** Mock data shaped exactly like BUILD_CONTRACT section 4 and the A5 SSE payload. */
import type {
  ChatMessage,
  Portfolio,
  PriceMap,
  Snapshot,
  WatchlistEntry,
} from "@/lib/types";

export function tick(
  ticker: string,
  price: number,
  previous = price,
  open = price,
): PriceMap[string] {
  return {
    ticker,
    price,
    previous_price: previous,
    open_price: open,
    timestamp: 1_757_000_000,
    change: Number((price - previous).toFixed(4)),
    change_percent: previous ? Number((((price - previous) / previous) * 100).toFixed(4)) : 0,
    direction: price > previous ? "up" : price < previous ? "down" : "flat",
  };
}

export const prices: PriceMap = {
  AAPL: tick("AAPL", 195.0, 194.5, 190.0),
  GOOGL: tick("GOOGL", 170.0, 170.5, 175.0),
};

export const watchlist: WatchlistEntry[] = [
  { ticker: "AAPL", price: 195.0, open_price: 190.0 },
  { ticker: "GOOGL", price: 170.0, open_price: 175.0 },
];

export const portfolio: Portfolio = {
  cash: 5000,
  total_value: 6950,
  unrealized_pnl: 50,
  positions: [
    {
      ticker: "AAPL",
      quantity: 10,
      avg_cost: 190,
      current_price: 195,
      unrealized_pnl: 50,
      pnl_percent: 2.6316,
    },
  ],
};

export const snapshots: Snapshot[] = [
  { total_value: 10000, recorded_at: "2026-09-11T09:00:00Z" },
  { total_value: 10240, recorded_at: "2026-09-11T09:30:00Z" },
  { total_value: 10180, recorded_at: "2026-09-11T10:00:00Z" },
];

export const chatMessages: ChatMessage[] = [
  {
    id: "m1",
    role: "user",
    content: "Buy 10 AAPL",
    actions: null,
    created_at: "2026-09-11T10:00:00Z",
  },
  {
    id: "m2",
    role: "assistant",
    content: "Adding 10 shares of AAPL to the book.",
    actions: [
      { type: "trade", ok: true, ticker: "AAPL", side: "buy", quantity: 10, price: 195 },
      {
        type: "trade",
        ok: false,
        ticker: "TSLA",
        side: "buy",
        quantity: 100,
        error: "Insufficient cash",
      },
      { type: "watchlist", ok: true, ticker: "PYPL", action: "add" },
    ],
    created_at: "2026-09-11T10:00:02Z",
  },
];
