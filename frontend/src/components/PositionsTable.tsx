"use client";

import { PriceCell } from "./PriceCell";
import { fmtMoney, fmtPercent, fmtQuantity, fmtSigned, signDirection } from "@/lib/format";
import type { PriceMap, Position } from "@/lib/types";

interface PositionsTableProps {
  positions: Position[];
  prices: PriceMap;
  selected: string | null;
  onSelect: (ticker: string) => void;
}

export function PositionsTable({ positions, prices, selected, onSelect }: PositionsTableProps) {
  return (
    <section data-testid="positions-table" className="flex h-full min-h-0 flex-col bg-ground">
      <div className="flex h-8 shrink-0 items-center justify-between border-b border-edge px-3">
        <span className="panel-title">Positions</span>
        <span className="num text-[10px] text-ink-dim">{positions.length}</span>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <table className="w-full border-collapse">
          <thead className="sticky top-0 bg-ground">
            <tr className="border-b border-edge">
              <th className="col-head px-3 py-1.5 text-left">Symbol</th>
              <th className="col-head px-3 py-1.5 text-right">Qty</th>
              <th className="col-head px-3 py-1.5 text-right">Avg cost</th>
              <th className="col-head px-3 py-1.5 text-right">Last</th>
              <th className="col-head px-3 py-1.5 text-right">Market value</th>
              <th className="col-head px-3 py-1.5 text-right">Unrealized</th>
              <th className="col-head px-3 py-1.5 text-right">Change</th>
            </tr>
          </thead>
          <tbody>
            {positions.length === 0 && (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-[12px] text-ink-dim">
                  No open positions. Use the command bar below to buy.
                </td>
              </tr>
            )}

            {positions.map((position) => {
              const live = prices[position.ticker]?.price ?? position.current_price;
              const direction = signDirection(position.unrealized_pnl);
              const pnlColor =
                direction === "up" ? "text-up" : direction === "down" ? "text-down" : "text-ink-mid";

              return (
                <tr
                  key={position.ticker}
                  data-testid={`position-row-${position.ticker}`}
                  onClick={() => onSelect(position.ticker)}
                  className={`cursor-pointer border-b border-edge/60 hover:bg-raised ${
                    selected === position.ticker ? "bg-raised" : ""
                  }`}
                >
                  <td className="num px-3 py-1.5 text-left text-[12px] font-medium text-ink">
                    {position.ticker}
                  </td>
                  <td className="num px-3 py-1.5 text-right text-[12px] text-ink-mid">
                    {fmtQuantity(position.quantity)}
                  </td>
                  <td className="num px-3 py-1.5 text-right text-[12px] text-ink-mid">
                    {fmtMoney(position.avg_cost)}
                  </td>
                  <td className="px-2 py-1.5 text-right text-[12px] text-ink">
                    <PriceCell price={live} />
                  </td>
                  <td className="num px-3 py-1.5 text-right text-[12px] text-ink">
                    {fmtMoney(position.quantity * live)}
                  </td>
                  <td className={`num px-3 py-1.5 text-right text-[12px] ${pnlColor}`}>
                    {fmtSigned(position.unrealized_pnl)}
                  </td>
                  <td className={`num px-3 py-1.5 text-right text-[12px] ${pnlColor}`}>
                    {fmtPercent(position.pnl_percent)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
