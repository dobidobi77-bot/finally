"use client";

import { useEffect, useRef, useState } from "react";
import { pushPoint } from "@/lib/series";
import type { ConnectionState, PriceMap, SeriesPoint } from "@/lib/types";

/** Rolling window per ticker. At ~500ms a tick this is roughly five minutes. */
const SERIES_LIMIT = 600;

export interface PriceStream {
  prices: PriceMap;
  series: Record<string, SeriesPoint[]>;
  status: ConnectionState;
}

/**
 * Subscribes to /api/stream/prices (BUILD_CONTRACT A5): one unnamed event whose
 * data is an object keyed by ticker. EventSource reconnects on its own, so the
 * hook only reports what state that retry loop is in.
 */
export function usePriceStream(enabled = true): PriceStream {
  const [prices, setPrices] = useState<PriceMap>({});
  const [series, setSeries] = useState<Record<string, SeriesPoint[]>>({});
  const [status, setStatus] = useState<ConnectionState>("disconnected");
  const seenAt = useRef<Record<string, number>>({});

  useEffect(() => {
    if (!enabled || typeof window === "undefined" || !("EventSource" in window)) return;

    const source = new EventSource("/api/stream/prices");

    source.onopen = () => setStatus("connected");

    source.onerror = () => {
      setStatus(source.readyState === EventSource.CLOSED ? "disconnected" : "reconnecting");
    };

    source.onmessage = (event: MessageEvent<string>) => {
      let payload: PriceMap;
      try {
        payload = JSON.parse(event.data) as PriceMap;
      } catch {
        return;
      }
      if (!payload || typeof payload !== "object") return;

      setStatus("connected");
      setPrices((current) => ({ ...current, ...payload }));

      setSeries((current) => {
        let changed = false;
        const next = { ...current };
        for (const [ticker, tick] of Object.entries(payload)) {
          if (!tick || typeof tick.price !== "number") continue;
          if (seenAt.current[ticker] === tick.timestamp) continue;
          seenAt.current[ticker] = tick.timestamp;
          next[ticker] = pushPoint(current[ticker], { t: tick.timestamp, v: tick.price }, SERIES_LIMIT);
          changed = true;
        }
        return changed ? next : current;
      });
    };

    return () => {
      source.close();
      setStatus("disconnected");
    };
  }, [enabled]);

  return { prices, series, status };
}
