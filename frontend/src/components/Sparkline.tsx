"use client";

import { linePath, scalePoints } from "@/lib/series";
import type { SeriesPoint } from "@/lib/types";

interface SparklineProps {
  points: SeriesPoint[] | undefined;
  width?: number;
  height?: number;
  direction?: "up" | "down" | "flat";
}

/**
 * Mini price trace beside a watchlist row, accumulated from SSE since page
 * load. Draws nothing until two ticks have arrived.
 */
export function Sparkline({ points, width = 68, height = 18, direction = "flat" }: SparklineProps) {
  const data = points ?? [];
  const scaled = scalePoints(data, { width, height, pad: 2 });
  const path = linePath(scaled);
  const stroke =
    direction === "up" ? "var(--color-up)" : direction === "down" ? "var(--color-down)" : "var(--color-ink-dim)";

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      aria-hidden="true"
      className="overflow-visible"
    >
      {path ? (
        <path d={path} fill="none" stroke={stroke} strokeWidth={1} strokeLinejoin="round" />
      ) : (
        <line
          x1={0}
          y1={height / 2}
          x2={width}
          y2={height / 2}
          stroke="var(--color-edge-bright)"
          strokeWidth={1}
          strokeDasharray="2 3"
        />
      )}
    </svg>
  );
}
