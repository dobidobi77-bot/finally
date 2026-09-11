/**
 * Squarified treemap (Bruls, Huizing & van Wijk). Positions are laid out as
 * rectangles sized by portfolio weight; the caller colours them by P&L.
 */

export interface TreemapInput<T> {
  value: number;
  data: T;
}

export interface TreemapRect<T> {
  x: number;
  y: number;
  width: number;
  height: number;
  data: T;
}

interface FreeRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

interface Entry<T> {
  area: number;
  data: T;
}

/** Aspect-ratio cost of a candidate row laid along a side of length `side`. */
function worstRatio<T>(row: Entry<T>[], side: number): number {
  if (row.length === 0 || side <= 0) return Infinity;
  let sum = 0;
  let min = Infinity;
  let max = 0;
  for (const item of row) {
    sum += item.area;
    if (item.area < min) min = item.area;
    if (item.area > max) max = item.area;
  }
  if (sum <= 0 || min <= 0) return Infinity;
  const side2 = side * side;
  const sum2 = sum * sum;
  return Math.max((side2 * max) / sum2, sum2 / (side2 * min));
}

/** Places one finished row and shrinks the free rectangle behind it. */
function placeRow<T>(row: Entry<T>[], rect: FreeRect, out: TreemapRect<T>[]): void {
  const total = row.reduce((sum, item) => sum + item.area, 0);
  if (total <= 0) return;

  const horizontal = rect.w >= rect.h;
  if (horizontal) {
    const colWidth = total / rect.h;
    let y = rect.y;
    for (const item of row) {
      const h = (item.area / total) * rect.h;
      out.push({ x: rect.x, y, width: colWidth, height: h, data: item.data });
      y += h;
    }
    rect.x += colWidth;
    rect.w -= colWidth;
  } else {
    const rowHeight = total / rect.w;
    let x = rect.x;
    for (const item of row) {
      const w = (item.area / total) * rect.w;
      out.push({ x, y: rect.y, width: w, height: rowHeight, data: item.data });
      x += w;
    }
    rect.y += rowHeight;
    rect.h -= rowHeight;
  }
}

/**
 * Lays out `items` inside a `width` x `height` box, largest first.
 * Non-positive values are dropped; an empty result is a valid answer.
 */
export function squarify<T>(
  items: TreemapInput<T>[],
  width: number,
  height: number,
): TreemapRect<T>[] {
  const positive = items.filter((item) => item.value > 0);
  if (positive.length === 0 || width <= 0 || height <= 0) return [];

  const total = positive.reduce((sum, item) => sum + item.value, 0);
  const scale = (width * height) / total;
  const queue: Entry<T>[] = positive
    .map((item) => ({ area: item.value * scale, data: item.data }))
    .sort((a, b) => b.area - a.area);

  const rect: FreeRect = { x: 0, y: 0, w: width, h: height };
  const out: TreemapRect<T>[] = [];
  let row: Entry<T>[] = [];

  for (const entry of queue) {
    const side = Math.min(rect.w, rect.h);
    if (row.length === 0 || worstRatio([...row, entry], side) <= worstRatio(row, side)) {
      row.push(entry);
      continue;
    }
    placeRow(row, rect, out);
    row = [entry];
  }
  if (row.length) placeRow(row, rect, out);

  return out;
}
