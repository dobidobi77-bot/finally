"use client";

import { useMeasure } from "@/hooks/useMeasure";
import { squarify } from "@/lib/treemap";
import { fmtPercent } from "@/lib/format";
import type { Position } from "@/lib/types";

interface HeatmapProps {
  positions: Position[];
  selected: string | null;
  onSelect: (ticker: string) => void;
}

/** Saturation rises with the size of the move, capped at a 6% swing. */
function tileColor(pnlPercent: number): string {
  const magnitude = Math.min(Math.abs(pnlPercent) / 6, 1);
  const alpha = 0.14 + magnitude * 0.62;
  if (pnlPercent > 0) return `rgba(38, 166, 154, ${alpha.toFixed(3)})`;
  if (pnlPercent < 0) return `rgba(239, 83, 80, ${alpha.toFixed(3)})`;
  return "rgba(100, 112, 130, 0.18)";
}

export function Heatmap({ positions, selected, onSelect }: HeatmapProps) {
  const [ref, size] = useMeasure<HTMLDivElement>();

  const rects = squarify(
    positions.map((position) => ({
      value: Math.abs(position.quantity * position.current_price),
      data: position,
    })),
    size.width,
    size.height,
  );

  return (
    <section data-testid="portfolio-heatmap" className="flex min-w-0 flex-1 flex-col bg-ground">
      <div className="flex h-8 shrink-0 items-center justify-between border-b border-edge px-3">
        <span className="panel-title">Allocation</span>
        <span className="panel-title">sized by weight, coloured by P&amp;L</span>
      </div>

      <div ref={ref} className="relative min-h-0 flex-1">
        {rects.map((rect) => {
          const position = rect.data;
          const compact = rect.width < 62 || rect.height < 34;
          return (
            <button
              key={position.ticker}
              data-testid={`heatmap-tile-${position.ticker}`}
              type="button"
              onClick={() => onSelect(position.ticker)}
              title={`${position.ticker} ${fmtPercent(position.pnl_percent)}`}
              className="absolute overflow-hidden border border-void/70 text-left"
              style={{
                left: rect.x,
                top: rect.y,
                width: rect.width,
                height: rect.height,
                background: tileColor(position.pnl_percent),
                outline: selected === position.ticker ? "1px solid var(--color-accent)" : undefined,
                outlineOffset: "-1px",
              }}
            >
              <span className="num absolute top-1 left-1.5 text-[11px] font-medium text-ink">
                {position.ticker}
              </span>
              {!compact && (
                <span className="num absolute bottom-1 left-1.5 text-[10px] text-ink/80">
                  {fmtPercent(position.pnl_percent)}
                </span>
              )}
            </button>
          );
        })}

        {positions.length === 0 && (
          <p className="absolute inset-0 flex items-center justify-center px-6 text-center text-[12px] text-ink-dim">
            Buy a position and it appears here, sized by weight.
          </p>
        )}
      </div>
    </section>
  );
}
