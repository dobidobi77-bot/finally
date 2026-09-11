"use client";

import { useEffect, useMemo, useState } from "react";
import { ChatPanel } from "@/components/ChatPanel";
import { Header } from "@/components/Header";
import { Heatmap } from "@/components/Heatmap";
import { MainChart } from "@/components/MainChart";
import { PnlChart } from "@/components/PnlChart";
import { PositionsTable } from "@/components/PositionsTable";
import { TradeBar } from "@/components/TradeBar";
import { Watchlist } from "@/components/Watchlist";
import { usePriceStream } from "@/hooks/usePriceStream";
import { useTerminal } from "@/hooks/useTerminal";
import type { Position } from "@/lib/types";

export default function Terminal() {
  const terminal = useTerminal();
  const { prices, series, status } = usePriceStream();
  const [selected, setSelected] = useState<string | null>(null);
  const [chatCollapsed, setChatCollapsed] = useState(false);

  // Land on the first watched symbol so the chart is never blank by default.
  useEffect(() => {
    if (selected === null && terminal.watchlist.length > 0) {
      setSelected(terminal.watchlist[0].ticker);
    }
  }, [selected, terminal.watchlist]);

  /** Positions revalued at the streaming price so P&L moves between fetches. */
  const livePositions = useMemo<Position[]>(
    () =>
      terminal.portfolio.positions.map((position) => {
        const price = prices[position.ticker]?.price ?? position.current_price;
        const cost = position.avg_cost * position.quantity;
        const value = price * position.quantity;
        return {
          ...position,
          current_price: price,
          unrealized_pnl: value - cost,
          pnl_percent: cost !== 0 ? ((value - cost) / cost) * 100 : 0,
        };
      }),
    [terminal.portfolio.positions, prices],
  );

  const liveUnrealized = livePositions.reduce((sum, p) => sum + p.unrealized_pnl, 0);
  const liveTotal =
    terminal.portfolio.cash + livePositions.reduce((sum, p) => sum + p.current_price * p.quantity, 0);

  return (
    <div className="flex min-h-screen flex-col lg:h-screen lg:overflow-hidden">
      <Header
        totalValue={liveTotal}
        cash={terminal.portfolio.cash}
        unrealizedPnl={liveUnrealized}
        status={status}
        marketSource={terminal.marketSource}
      />

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <Watchlist
          entries={terminal.watchlist}
          prices={prices}
          series={series}
          selected={selected}
          onSelect={setSelected}
          onAdd={terminal.addTicker}
          onRemove={terminal.removeTicker}
          error={terminal.watchlistError}
        />

        <main className="flex min-w-0 flex-1 flex-col">
          <MainChart
            ticker={selected}
            tick={selected ? prices[selected] : undefined}
            points={selected ? series[selected] : undefined}
          />

          <div className="flex h-[214px] shrink-0 flex-col border-t border-edge lg:flex-row">
            <Heatmap positions={livePositions} selected={selected} onSelect={setSelected} />
            <div className="border-t border-edge lg:border-t-0 lg:border-l" />
            <PnlChart snapshots={terminal.snapshots} />
          </div>

          <div className="h-[250px] shrink-0 border-t border-edge">
            <PositionsTable
              positions={livePositions}
              prices={prices}
              selected={selected}
              onSelect={setSelected}
            />
          </div>
        </main>

        <ChatPanel
          messages={terminal.messages}
          pending={terminal.chatPending}
          collapsed={chatCollapsed}
          onToggle={() => setChatCollapsed((value) => !value)}
          onSend={terminal.sendChat}
        />
      </div>

      <TradeBar
        prices={prices}
        cash={terminal.portfolio.cash}
        selected={selected}
        onTrade={terminal.trade}
      />
    </div>
  );
}
