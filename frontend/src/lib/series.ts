/** Path builders for the hand-drawn SVG charts. */
import type { SeriesPoint } from "./types";

export interface ChartBox {
  width: number;
  height: number;
  /** Inset in px kept clear on every side so strokes are not clipped. */
  pad?: number;
}

export interface Scaled {
  points: Array<{ x: number; y: number; point: SeriesPoint }>;
  min: number;
  max: number;
}

/**
 * Maps points into pixel space. A flat series is centred vertically instead of
 * collapsing onto an edge, which is what a fresh SSE stream looks like.
 */
export function scalePoints(points: SeriesPoint[], box: ChartBox): Scaled {
  const pad = box.pad ?? 2;
  const innerW = Math.max(box.width - pad * 2, 1);
  const innerH = Math.max(box.height - pad * 2, 1);

  const values = points.map((p) => p.v);
  let min = values.length ? Math.min(...values) : 0;
  let max = values.length ? Math.max(...values) : 0;
  if (max - min < 1e-9) {
    const nudge = Math.max(Math.abs(max) * 0.001, 0.01);
    min -= nudge;
    max += nudge;
  }

  const span = max - min;
  const lastIndex = Math.max(points.length - 1, 1);

  return {
    min,
    max,
    points: points.map((point, i) => ({
      x: pad + (i / lastIndex) * innerW,
      y: pad + innerH - ((point.v - min) / span) * innerH,
      point,
    })),
  };
}

/** Polyline through the scaled points. Empty string for fewer than two. */
export function linePath(scaled: Scaled): string {
  if (scaled.points.length < 2) return "";
  return scaled.points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(2)} ${p.y.toFixed(2)}`).join(" ");
}

/** The same line closed down to the baseline, for a subtle fill. */
export function areaPath(scaled: Scaled, box: ChartBox): string {
  if (scaled.points.length < 2) return "";
  const base = box.height;
  const first = scaled.points[0];
  const last = scaled.points[scaled.points.length - 1];
  return `${linePath(scaled)} L${last.x.toFixed(2)} ${base} L${first.x.toFixed(2)} ${base} Z`;
}

/**
 * Keeps a rolling window of points. Charts fill from SSE since page load
 * (BUILD_CONTRACT A6), so the arrays would otherwise grow without bound.
 */
export function pushPoint(
  series: SeriesPoint[] | undefined,
  point: SeriesPoint,
  limit: number,
): SeriesPoint[] {
  const next = series ? [...series, point] : [point];
  return next.length > limit ? next.slice(next.length - limit) : next;
}
