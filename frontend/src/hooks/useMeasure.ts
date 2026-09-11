"use client";

import { useEffect, useRef, useState } from "react";

export interface Size {
  width: number;
  height: number;
}

/**
 * Tracks an element's content box. Charts draw in real pixels rather than a
 * stretched viewBox, so strokes keep an even weight at any panel size.
 */
export function useMeasure<T extends HTMLElement>(): [React.RefObject<T | null>, Size] {
  const ref = useRef<T>(null);
  const [size, setSize] = useState<Size>({ width: 0, height: 0 });

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const read = () => {
      setSize({ width: element.clientWidth, height: element.clientHeight });
    };
    read();

    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(read);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return [ref, size];
}
