"use client";

import { useMeasure } from "@/hooks/useMeasure";
import { areaPath, linePath, scalePoints } from "@/lib/series";
import { fmtClock, fmtMoney, fmtPercent, signDirection } from "@/lib/format";
import type { Snapshot } from "@/lib/types";

interface PnlChartProps {
  snapshots: Snapshot[];
}

/** Total portfolio value over the last 24 hours (BUILD_CONTRACT B4). */
export function PnlChart({ snapshots }: PnlChartProps) {
  const [ref, size] = useMeasure<HTMLDivElement>();

  const points = snapshots.map((snapshot) => ({
    t: new Date(snapshot.recorded_at).getTime() / 1000,
    v: snapshot.total_value,
  }));

  const box = { width: size.width, height: size.height, pad: 8 };
  const scaled = scalePoints(points, box);
  const line = linePath(scaled);

  const first = points[0]?.v ?? 0;
  const last = points[points.length - 1]?.v ?? 0;
  const changePercent = first !== 0 ? ((last - first) / first) * 100 : 0;
  const direction = signDirection(last - first);
  const stroke =
    direction === "down" ? "var(--color-down)" : direction === "up" ? "var(--color-up)" : "var(--color-ink-dim)";

  return (
    <section data-testid="pnl-chart" data-points={points.length} className="flex min-w-0 flex-1 flex-col bg-ground">
      <div className="flex h-8 shrink-0 items-center justify-between border-b border-edge px-3">
        <span className="panel-title">Portfolio value</span>
        <span
          className={`num text-[11px] ${
            direction === "up" ? "text-up" : direction === "down" ? "text-down" : "text-ink-dim"
          }`}
        >
          {points.length > 1 ? fmtPercent(changePercent) : ""}
        </span>
      </div>

      <div ref={ref} className="relative min-h-0 flex-1">
        {size.width > 0 && line && (
          <svg width={size.width} height={size.height} className="absolute inset-0">
            <defs>
              <linearGradient id="pnlFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={stroke} stopOpacity="0.18" />
                <stop offset="100%" stopColor={stroke} stopOpacity="0" />
              </linearGradient>
            </defs>
            <path d={areaPath(scaled, box)} fill="url(#pnlFill)" />
            <path d={line} fill="none" stroke={stroke} strokeWidth={1.5} strokeLinejoin="round" />
          </svg>
        )}

        {points.length < 2 && (
          <p className="absolute inset-0 flex items-center justify-center px-6 text-center text-[12px] text-ink-dim">
            Value is recorded after every trade. The line starts once there are two points.
          </p>
        )}

        {points.length >= 2 && (
          <div className="pointer-events-none absolute inset-x-0 bottom-1 flex justify-between px-2 text-[10px] text-ink-dim">
            <span className="num">{fmtClock(snapshots[0].recorded_at)}</span>
            <span className="num">{fmtMoney(last)}</span>
          </div>
        )}
      </div>
    </section>
  );
}
