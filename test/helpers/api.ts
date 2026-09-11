import type { APIRequestContext, APIResponse } from "@playwright/test";

/** Shapes from BUILD_CONTRACT section 4 and INTERFACES section 3. */
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

export interface WatchlistEntry {
  ticker: string;
  price: number | null;
  previous_price?: number | null;
  open_price?: number | null;
  change?: number | null;
  change_percent?: number | null;
  direction?: string;
  timestamp?: number;
}

export type ChatAction =
  | { type: "trade"; ok: true; ticker: string; side: string; quantity: number; price: number }
  | { type: "trade"; ok: false; ticker: string; side: string; quantity: number; error: string }
  | { type: "watchlist"; ok: boolean; ticker: string; action: string; error?: string };

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  actions: ChatAction[] | null;
  created_at: string;
}

export interface Snapshot {
  total_value: number;
  recorded_at: string;
}

/** Status plus decoded body, so a spec can assert on a 400 as easily as a 200. */
export interface Result<T> {
  status: number;
  body: T;
}

async function decode<T>(res: APIResponse): Promise<Result<T>> {
  const text = await res.text();
  let body: unknown;
  try {
    body = JSON.parse(text);
  } catch {
    throw new Error(
      `${res.url()} returned ${res.status()} with a non-JSON body: ${text.slice(0, 400)}`,
    );
  }
  return { status: res.status(), body: body as T };
}

/** Thin typed client over the HTTP contract. Used for setup and for
 * corroborating what the UI shows against what the server actually holds. */
export class Api {
  constructor(private readonly request: APIRequestContext) {}

  async portfolio(): Promise<Portfolio> {
    const { status, body } = await decode<Portfolio>(await this.request.get("/api/portfolio"));
    if (status !== 200) throw new Error(`GET /api/portfolio -> ${status}: ${JSON.stringify(body)}`);
    return body;
  }

  async trade(
    ticker: string,
    side: "buy" | "sell",
    quantity: number,
  ): Promise<Result<{ ok?: boolean; trade?: unknown; portfolio?: Portfolio; error?: string }>> {
    return decode(
      await this.request.post("/api/portfolio/trade", { data: { ticker, side, quantity } }),
    );
  }

  async history(): Promise<{ snapshots: Snapshot[] }> {
    const { body } = await decode<{ snapshots: Snapshot[] }>(
      await this.request.get("/api/portfolio/history"),
    );
    return body;
  }

  async watchlist(): Promise<WatchlistEntry[]> {
    const { body } = await decode<{ tickers: WatchlistEntry[] }>(
      await this.request.get("/api/watchlist"),
    );
    return body.tickers;
  }

  async addTicker(ticker: string): Promise<Result<{ ok?: boolean; ticker?: string; error?: string }>> {
    return decode(await this.request.post("/api/watchlist", { data: { ticker } }));
  }

  async removeTicker(ticker: string): Promise<Result<{ ok?: boolean; error?: string }>> {
    return decode(await this.request.delete(`/api/watchlist/${ticker}`));
  }

  async chatHistory(limit = 20): Promise<ChatMessage[]> {
    const { body } = await decode<{ messages: ChatMessage[] }>(
      await this.request.get(`/api/chat?limit=${limit}`),
    );
    return body.messages;
  }

  async sendChat(message: string): Promise<Result<ChatMessage & { error?: string }>> {
    return decode(await this.request.post("/api/chat", { data: { message }, timeout: 30_000 }));
  }

  /** Flatten a position list to {ticker: quantity} for readable assertions. */
  async positionMap(): Promise<Record<string, number>> {
    const p = await this.portfolio();
    return Object.fromEntries(p.positions.map((x) => [x.ticker, x.quantity]));
  }
}
