"use client";

import { useMeasure } from "@/hooks/useMeasure";
import { areaPath, linePath, scalePoints } from "@/lib/series";
import { dailyChangePercent, fmtClock, fmtMoney, fmtPercent, signDirection } from "@/lib/format";
import type { PriceTick, SeriesPoint } from "@/lib/types";

interface MainChartProps {
  ticker: string | null;
  tick: PriceTick | undefined;
  points: SeriesPoint[] | undefined;
}

/**
 * Price trace for the selected ticker. There is no price-history endpoint by
 * design (BUILD_CONTRACT A6), so it starts empty and fills from the stream.
 */
export function MainChart({ ticker, tick, points }: MainChartProps) {
  const [ref, size] = useMeasure<HTMLDivElement>();
  const data = points ?? [];
  const box = { width: size.width, height: size.height, pad: 8 };
  const scaled = scalePoints(data, box);
  const line = linePath(scaled);
  const area = areaPath(scaled, box);

  const change = dailyChangePercent(tick?.price ?? null, tick?.open_price ?? null);
  const direction = signDirection(change);
  const changeColor =
    direction === "up" ? "text-up" : direction === "down" ? "text-down" : "text-ink-mid";

  const last = scaled.points[scaled.points.length - 1];
  const first = data[0];

  return (
    <section data-testid="main-chart" data-points={data.length} className="flex min-h-[240px] flex-1 flex-col bg-ground">
      <div className="flex h-9 shrink-0 items-center gap-4 border-b border-edge px-3">
        <span className="num text-[14px] font-medium text-ink">{ticker ?? "--"}</span>
        <span className="num text-[14px] text-ink">{fmtMoney(tick?.price ?? null)}</span>
        <span className={`num text-[12px] ${changeColor}`}>{fmtPercent(change)}</span>
        <span className="panel-title ml-auto">
          {tick?.open_price != null ? `Session open ${fmtMoney(tick.open_price)}` : "Awaiting open"}
        </span>
      </div>

      <div ref={ref} className="relative min-h-0 flex-1">
        {size.width > 0 && (
          <svg width={size.width} height={size.height} className="absolute inset-0">
            <defs>
              <linearGradient id="mainChartFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--color-blue)" stopOpacity="0.22" />
                <stop offset="100%" stopColor="var(--color-blue)" stopOpacity="0" />
              </linearGradient>
            </defs>

            {[0.25, 0.5, 0.75].map((fraction) => (
              <line
                key={fraction}
                x1={0}
                x2={size.width}
                y1={size.height * fraction}
                y2={size.height * fraction}
                stroke="var(--color-edge)"
                strokeWidth={1}
              />
            ))}

            {line && (
              <>
                <path d={area} fill="url(#mainChartFill)" />
                <path
                  d={line}
                  fill="none"
                  stroke="var(--color-blue)"
                  strokeWidth={1.5}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
                {last && (
                  <>
                    <line
                      x1={0}
                      x2={size.width}
                      y1={last.y}
                      y2={last.y}
                      stroke="var(--color-accent)"
                      strokeWidth={1}
                      strokeDasharray="3 4"
                      opacity={0.55}
                    />
                    <circle cx={last.x} cy={last.y} r={2.5} fill="var(--color-accent)" />
                  </>
                )}
              </>
            )}
          </svg>
        )}

        {data.length < 2 && (
          <p className="absolute inset-0 flex items-center justify-center px-6 text-center text-[12px] leading-relaxed text-ink-dim">
            {ticker
              ? `The chart draws itself as ${ticker} ticks arrive.`
              : "Pick a symbol from the watchlist."}
          </p>
        )}

        {data.length >= 2 && (
          <div className="pointer-events-none absolute inset-x-0 bottom-1 flex justify-between px-2 text-[10px] text-ink-dim">
            <span className="num">{first ? fmtClock(first.t) : ""}</span>
            <span className="num">{fmtMoney(scaled.min)} - {fmtMoney(scaled.max)}</span>
            <span className="num">{data.length} ticks</span>
          </div>
        )}
      </div>
    </section>
  );
}
