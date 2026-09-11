"use client";

import { useEffect, useRef, useState } from "react";
import { fmtMoney } from "@/lib/format";

interface PriceCellProps {
  price: number | null | undefined;
  testId?: string;
  className?: string;
}

/**
 * A price readout that flashes green on an uptick and red on a downtick,
 * fading out over 500ms. The flash element is keyed on a counter so a run of
 * consecutive upticks restarts the animation instead of ignoring it.
 */
export function PriceCell({ price, testId, className = "" }: PriceCellProps) {
  const previous = useRef<number | null>(null);
  const sequence = useRef(0);
  const [flash, setFlash] = useState<{ direction: "up" | "down"; seq: number } | null>(null);

  useEffect(() => {
    if (price === null || price === undefined) return;
    const before = previous.current;
    previous.current = price;
    if (before === null || before === price) return;

    sequence.current += 1;
    setFlash({ direction: price > before ? "up" : "down", seq: sequence.current });
    const timer = window.setTimeout(() => setFlash(null), 520);
    return () => window.clearTimeout(timer);
  }, [price]);

  const flashClass = flash ? `flash-${flash.direction}` : "";

  return (
    <span
      key={flash?.seq ?? "idle"}
      data-testid={testId}
      data-direction={flash?.direction ?? "flat"}
      className={`num inline-block px-1 tabular-nums ${flashClass} ${className}`}
    >
      {fmtMoney(price)}
    </span>
  );
}
