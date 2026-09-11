"use client";

import { useEffect, useState } from "react";
import { fmtMoney } from "@/lib/format";
import type { PriceMap } from "@/lib/types";

interface TradeBarProps {
  prices: PriceMap;
  cash: number;
  selected: string | null;
  onTrade: (ticker: string, quantity: number, side: "buy" | "sell") => Promise<void>;
}

/**
 * The command bar. Market orders only: instant fill at the streaming price,
 * no confirmation step. Backend rejections land in the inline error region.
 */
export function TradeBar({ prices, cash, selected, onTrade }: TradeBarProps) {
  const [ticker, setTicker] = useState(selected ?? "");
  const [quantity, setQuantity] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<"buy" | "sell" | null>(null);

  // Selecting a symbol anywhere in the terminal loads it into the command bar.
  useEffect(() => {
    if (selected) setTicker(selected);
  }, [selected]);

  const live = ticker ? (prices[ticker]?.price ?? null) : null;
  const parsedQuantity = Number(quantity);
  const notional =
    live !== null && Number.isFinite(parsedQuantity) && parsedQuantity > 0
      ? live * parsedQuantity
      : null;

  async function submit(side: "buy" | "sell") {
    const symbol = ticker.trim().toUpperCase();
    setError(null);

    if (!symbol) {
      setError("Enter a ticker");
      return;
    }
    if (!Number.isFinite(parsedQuantity) || parsedQuantity <= 0) {
      setError("Quantity must be greater than zero");
      return;
    }

    setPending(side);
    try {
      await onTrade(symbol, parsedQuantity, side);
      setQuantity("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Trade failed");
    } finally {
      setPending(null);
    }
  }

  const inputClass =
    "num rounded-xs border border-edge bg-panel px-2 py-1 text-[12px] text-ink placeholder:font-sans placeholder:text-ink-dim";

  return (
    <footer className="flex h-[46px] shrink-0 flex-wrap items-center gap-2 border-t border-edge bg-ground px-3">
      <span className="num select-none text-[13px] text-accent" aria-hidden="true">
        &rsaquo;
      </span>

      <input
        data-testid="trade-ticker"
        value={ticker}
        onChange={(event) => setTicker(event.target.value.toUpperCase())}
        placeholder="Ticker"
        aria-label="Ticker to trade"
        className={`${inputClass} w-[86px] tracking-[0.06em]`}
      />

      <input
        data-testid="trade-quantity"
        value={quantity}
        onChange={(event) => setQuantity(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") void submit("buy");
        }}
        placeholder="Qty"
        inputMode="decimal"
        aria-label="Quantity to trade"
        className={`${inputClass} w-[84px] text-right`}
      />

      <button
        type="button"
        data-testid="trade-buy"
        disabled={pending !== null}
        onClick={() => void submit("buy")}
        className="rounded-xs border border-up px-4 py-1 text-[12px] font-medium text-up transition-colors hover:bg-up hover:text-void disabled:opacity-40"
      >
        Buy
      </button>

      <button
        type="button"
        data-testid="trade-sell"
        disabled={pending !== null}
        onClick={() => void submit("sell")}
        className="rounded-xs border border-down px-4 py-1 text-[12px] font-medium text-down transition-colors hover:bg-down hover:text-void disabled:opacity-40"
      >
        Sell
      </button>

      <span className="num text-[11px] text-ink-dim">
        {live !== null ? `last ${fmtMoney(live)}` : ticker ? "no price yet" : ""}
        {notional !== null ? `  ->  ${fmtMoney(notional)}` : ""}
      </span>

      {/* Wrapper holds the layout slot; the error region itself mounts only on an error. */}
      <span className="ml-auto max-w-[46%] truncate text-right text-[11px] text-down">
        {error && (
          <span data-testid="trade-error" role="status">
            {error}
          </span>
        )}
      </span>

      <span className="num border-l border-edge pl-3 text-[11px] text-ink-dim">
        buying power {fmtMoney(cash)}
      </span>
    </footer>
  );
}
