/**
 * Same-origin calls to the FastAPI backend. No host, no CORS: the static
 * export is served by the same process that answers /api/*.
 */
import type {
  ChatHistoryResponse,
  ChatMessage,
  HistoryResponse,
  Portfolio,
  TradeResponse,
  WatchlistResponse,
} from "./types";

/** Backend errors are always `{"error": "..."}` with a 4xx status. */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError("Cannot reach the server", 0);
  }

  const body = await res.text();
  let parsed: unknown = null;
  if (body) {
    try {
      parsed = JSON.parse(body);
    } catch {
      parsed = null;
    }
  }

  if (!res.ok) {
    const message =
      parsed && typeof parsed === "object" && "error" in parsed
        ? String((parsed as { error: unknown }).error)
        : `Request failed (${res.status})`;
    throw new ApiError(message, res.status);
  }

  return parsed as T;
}

export const getHealth = () =>
  request<{ status: string; market_source: string; cache_ready: boolean }>("/api/health");

export const getPortfolio = () => request<Portfolio>("/api/portfolio");

export const getHistory = () => request<HistoryResponse>("/api/portfolio/history");

export const getWatchlist = () => request<WatchlistResponse>("/api/watchlist");

export const getChatHistory = (limit = 20) =>
  request<ChatHistoryResponse>(`/api/chat?limit=${limit}`);

export const executeTrade = (ticker: string, quantity: number, side: "buy" | "sell") =>
  request<TradeResponse>("/api/portfolio/trade", {
    method: "POST",
    body: JSON.stringify({ ticker, quantity, side }),
  });

export const addWatchlistTicker = (ticker: string) =>
  request<{ ok: boolean; ticker: string }>("/api/watchlist", {
    method: "POST",
    body: JSON.stringify({ ticker }),
  });

export const removeWatchlistTicker = (ticker: string) =>
  request<{ ok: boolean }>(`/api/watchlist/${encodeURIComponent(ticker)}`, {
    method: "DELETE",
  });

export const sendChatMessage = (message: string) =>
  request<ChatMessage>("/api/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
