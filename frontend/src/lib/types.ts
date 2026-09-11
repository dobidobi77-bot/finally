/** Shapes of the HTTP contract in planning/BUILD_CONTRACT.md section 4. */

export type Direction = "up" | "down" | "flat";

/** One ticker inside the SSE payload (BUILD_CONTRACT A5). */
export interface PriceTick {
  ticker: string;
  price: number;
  previous_price: number;
  /** Session baseline for the daily change % (A1). */
  open_price: number | null;
  /** Unix seconds. */
  timestamp: number;
  change: number;
  /** Tick-to-tick percent, not the daily figure. */
  change_percent: number;
  direction: Direction;
}

/** The whole SSE `data:` object, keyed by ticker. */
export type PriceMap = Record<string, PriceTick>;

export interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  unrealized_pnl: number;
  pnl_percent: number;
}

export interface Portfolio {
  cash: number;
  positions: Position[];
  total_value: number;
  unrealized_pnl: number;
}

export interface Snapshot {
  total_value: number;
  recorded_at: string;
}

export interface HistoryResponse {
  snapshots: Snapshot[];
}

/** A watchlist entry: identity plus whatever the price cache knows so far. */
export interface WatchlistEntry {
  ticker: string;
  price: number | null;
  previous_price?: number | null;
  open_price?: number | null;
  change?: number | null;
  change_percent?: number | null;
  direction?: Direction | null;
  timestamp?: number | null;
}

export interface WatchlistResponse {
  tickers: WatchlistEntry[];
}

export interface TradeReceipt {
  ticker: string;
  side: "buy" | "sell";
  quantity: number;
  price: number;
  executed_at?: string;
  id?: string;
}

export interface TradeResponse {
  ok: boolean;
  trade: TradeReceipt;
  portfolio: Portfolio;
}

/** Action receipts rendered as chips beneath an assistant message (B6). */
export interface TradeAction {
  type: "trade";
  ok: boolean;
  ticker: string;
  side: "buy" | "sell";
  quantity: number;
  price?: number;
  error?: string;
}

export interface WatchlistAction {
  type: "watchlist";
  ok: boolean;
  ticker: string;
  action: "add" | "remove";
  error?: string;
}

export type ChatAction = TradeAction | WatchlistAction;

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  actions: ChatAction[] | null;
  created_at: string;
}

export interface ChatHistoryResponse {
  messages: ChatMessage[];
}

export type ConnectionState = "connected" | "reconnecting" | "disconnected";

/** One accumulated price point for the sparklines and the main chart. */
export interface SeriesPoint {
  t: number;
  v: number;
}
