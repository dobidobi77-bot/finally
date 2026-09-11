"use client";

import { useState } from "react";
import { PriceCell } from "./PriceCell";
import { Sparkline } from "./Sparkline";
import { dailyChangePercent, fmtPercent, signDirection } from "@/lib/format";
import type { PriceMap, SeriesPoint, WatchlistEntry } from "@/lib/types";

interface WatchlistProps {
  entries: WatchlistEntry[];
  prices: PriceMap;
  series: Record<string, SeriesPoint[]>;
  selected: string | null;
  onSelect: (ticker: string) => void;
  onAdd: (ticker: string) => Promise<void> | void;
  onRemove: (ticker: string) => Promise<void> | void;
  error?: string | null;
}

interface Mover {
  ticker: string;
  change: number;
}

/** Best and worst performer on the watchlist, by change against the open. */
function findMovers(entries: WatchlistEntry[], prices: PriceMap): [Mover | null, Mover | null] {
  const ranked = entries
    .map((entry) => {
      const tick = prices[entry.ticker];
      return {
        ticker: entry.ticker,
        change: dailyChangePercent(
          tick?.price ?? entry.price ?? null,
          tick?.open_price ?? entry.open_price ?? null,
        ),
      };
    })
    .filter((item): item is Mover => item.change !== null)
    .sort((a, b) => b.change - a.change);

  if (ranked.length < 2) return [null, null];
  return [ranked[0], ranked[ranked.length - 1]];
}

function MoverRow({ label, mover }: { label: string; mover: Mover }) {
  const positive = mover.change > 0;
  return (
    <div className="flex items-baseline justify-between">
      <span className="panel-title">{label}</span>
      <span className="num text-[11px] text-ink">
        {mover.ticker}
        <span className={`ml-2 ${positive ? "text-up" : "text-down"}`}>
          {fmtPercent(mover.change)}
        </span>
      </span>
    </div>
  );
}

export function Watchlist({
  entries,
  prices,
  series,
  selected,
  onSelect,
  onAdd,
  onRemove,
  error,
}: WatchlistProps) {
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [leader, laggard] = findMovers(entries, prices);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const ticker = draft.trim().toUpperCase();
    if (!ticker || busy) return;
    setBusy(true);
    try {
      await onAdd(ticker);
      setDraft("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      data-testid="watchlist"
      className="flex w-full shrink-0 flex-col border-edge bg-ground lg:w-[286px] lg:border-r"
    >
      <div className="flex h-8 shrink-0 items-center justify-between border-b border-edge px-3">
        <span className="panel-title">Watchlist</span>
        <span className="num text-[10px] text-ink-dim">{entries.length}</span>
      </div>

      <div className="flex-1 overflow-y-auto">
        {entries.length === 0 ? (
          <p className="px-3 py-6 text-[12px] leading-relaxed text-ink-dim">
            Nothing on the watchlist. Add a symbol below to start streaming it.
          </p>
        ) : (
          entries.map((entry) => {
            const tick = prices[entry.ticker];
            const price = tick?.price ?? entry.price ?? null;
            const open = tick?.open_price ?? entry.open_price ?? null;
            const change = dailyChangePercent(price, open);
            const direction = signDirection(change);
            const isSelected = selected === entry.ticker;

            return (
              <div
                key={entry.ticker}
                data-testid={`watchlist-row-${entry.ticker}`}
                data-selected={isSelected ? "true" : "false"}
                role="button"
                tabIndex={0}
                onClick={() => onSelect(entry.ticker)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect(entry.ticker);
                  }
                }}
                className={`group relative grid h-[34px] cursor-pointer grid-cols-[54px_1fr_auto] items-center gap-2 border-b border-edge/60 pr-2 pl-3 transition-colors hover:bg-raised ${
                  isSelected ? "bg-accent/8" : ""
                }`}
              >
                {isSelected && (
                  <span className="absolute top-0 bottom-0 left-0 w-[2px] bg-accent" aria-hidden="true" />
                )}

                <span
                  className={`num text-[12px] font-medium ${isSelected ? "text-accent" : "text-ink"}`}
                >
                  {entry.ticker}
                </span>

                <span className="flex justify-center">
                  <Sparkline points={series[entry.ticker]} direction={direction} />
                </span>

                <span className="flex items-center justify-end gap-1.5">
                  <PriceCell
                    price={price}
                    testId={`watchlist-price-${entry.ticker}`}
                    className="text-[12px] text-ink"
                  />
                  <span
                    className={`num w-[54px] text-right text-[11px] ${
                      direction === "up" ? "text-up" : direction === "down" ? "text-down" : "text-ink-dim"
                    }`}
                  >
                    {fmtPercent(change)}
                  </span>
                  <button
                    type="button"
                    data-testid={`watchlist-remove-${entry.ticker}`}
                    aria-label={`Remove ${entry.ticker} from the watchlist`}
                    onClick={(event) => {
                      event.stopPropagation();
                      void onRemove(entry.ticker);
                    }}
                    className="w-4 text-[13px] leading-none text-ink-dim opacity-0 transition-opacity group-hover:opacity-100 hover:text-down focus-visible:opacity-100"
                  >
                    &times;
                  </button>
                </span>
              </div>
            );
          })
        )}
      </div>

      {leader && laggard && (
        <div className="shrink-0 space-y-1 border-t border-edge px-3 py-2">
          <MoverRow label="Leading" mover={leader} />
          <MoverRow label="Lagging" mover={laggard} />
        </div>
      )}

      <form onSubmit={submit} className="shrink-0 border-t border-edge p-2">
        <div className="flex gap-1.5">
          <input
            data-testid="watchlist-add-input"
            value={draft}
            onChange={(event) => setDraft(event.target.value.toUpperCase())}
            placeholder="Add symbol"
            aria-label="Add a ticker to the watchlist"
            className="num min-w-0 flex-1 rounded-xs border border-edge bg-panel px-2 py-1.5 text-[12px] tracking-[0.06em] placeholder:font-sans placeholder:tracking-normal placeholder:text-ink-dim"
          />
          <button
            type="submit"
            data-testid="watchlist-add-submit"
            disabled={busy}
            className="rounded-xs bg-purple px-3 py-1.5 text-[12px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            Add
          </button>
        </div>
        {error && (
          <p data-testid="watchlist-error" className="mt-1.5 text-[11px] text-down">
            {error}
          </p>
        )}
      </form>
    </section>
  );
}
