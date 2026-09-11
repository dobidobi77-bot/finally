"use client";

import { useCallback, useEffect, useState } from "react";
import * as api from "@/lib/api";
import type { ChatMessage, Portfolio, Snapshot, WatchlistEntry } from "@/lib/types";

const EMPTY_PORTFOLIO: Portfolio = {
  cash: 0,
  positions: [],
  total_value: 0,
  unrealized_pnl: 0,
};

function messageOf(cause: unknown, fallback: string): string {
  return cause instanceof Error ? cause.message : fallback;
}

/**
 * Everything the terminal loads over HTTP. Prices arrive separately over SSE.
 * On page load the four bootstrap calls run together so a refresh keeps the
 * portfolio, the watchlist, the value history and the conversation; the health
 * check rides along to name the active price source.
 */
export function useTerminal() {
  const [portfolio, setPortfolio] = useState<Portfolio>(EMPTY_PORTFOLIO);
  const [watchlist, setWatchlist] = useState<WatchlistEntry[]>([]);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatPending, setChatPending] = useState(false);
  const [watchlistError, setWatchlistError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [marketSource, setMarketSource] = useState<string | null>(null);

  const refreshPortfolio = useCallback(async () => {
    try {
      setPortfolio(await api.getPortfolio());
    } catch {
      /* the header keeps the last good figures */
    }
  }, []);

  const refreshWatchlist = useCallback(async () => {
    try {
      const response = await api.getWatchlist();
      setWatchlist(response.tickers ?? []);
    } catch {
      /* keep the current rows; SSE still updates their prices */
    }
  }, []);

  const refreshHistory = useCallback(async () => {
    try {
      const response = await api.getHistory();
      setSnapshots(response.snapshots ?? []);
    } catch {
      /* leave the chart as it is */
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [, , , chat, health] = await Promise.all([
        refreshPortfolio(),
        refreshWatchlist(),
        refreshHistory(),
        api.getChatHistory(20).catch(() => ({ messages: [] })),
        api.getHealth().catch(() => null),
      ]);
      if (!cancelled) {
        setMessages(chat.messages ?? []);
        setMarketSource(health?.market_source ?? null);
        setLoaded(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshPortfolio, refreshWatchlist, refreshHistory]);

  const trade = useCallback(
    async (ticker: string, quantity: number, side: "buy" | "sell") => {
      const response = await api.executeTrade(ticker, quantity, side);
      if (response?.portfolio) setPortfolio(response.portfolio);
      else await refreshPortfolio();
      await Promise.all([refreshWatchlist(), refreshHistory()]);
    },
    [refreshPortfolio, refreshWatchlist, refreshHistory],
  );

  const addTicker = useCallback(
    async (ticker: string) => {
      setWatchlistError(null);
      try {
        await api.addWatchlistTicker(ticker);
        await refreshWatchlist();
      } catch (cause) {
        setWatchlistError(messageOf(cause, "Could not add that ticker"));
      }
    },
    [refreshWatchlist],
  );

  const removeTicker = useCallback(
    async (ticker: string) => {
      setWatchlistError(null);
      try {
        await api.removeWatchlistTicker(ticker);
        setWatchlist((current) => current.filter((entry) => entry.ticker !== ticker));
      } catch (cause) {
        setWatchlistError(messageOf(cause, "Could not remove that ticker"));
      }
    },
    [],
  );

  const sendChat = useCallback(
    async (text: string) => {
      const optimistic: ChatMessage = {
        id: `local-${Date.now()}`,
        role: "user",
        content: text,
        actions: null,
        created_at: new Date().toISOString(),
      };
      setMessages((current) => [...current, optimistic]);
      setChatPending(true);

      try {
        const reply = await api.sendChatMessage(text);
        setMessages((current) => [...current, reply]);
        await Promise.all([refreshPortfolio(), refreshWatchlist(), refreshHistory()]);
      } catch (cause) {
        setMessages((current) => [
          ...current,
          {
            id: `error-${Date.now()}`,
            role: "assistant",
            content: messageOf(cause, "The assistant is unavailable right now."),
            actions: null,
            created_at: new Date().toISOString(),
          },
        ]);
      } finally {
        setChatPending(false);
      }
    },
    [refreshPortfolio, refreshWatchlist, refreshHistory],
  );

  return {
    portfolio,
    watchlist,
    snapshots,
    messages,
    chatPending,
    watchlistError,
    marketSource,
    loaded,
    trade,
    addTicker,
    removeTicker,
    sendChat,
  };
}
