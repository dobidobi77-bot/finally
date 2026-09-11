"use client";

import { useEffect, useState } from "react";
import { fmtMoney, fmtPercent, fmtSigned, signDirection } from "@/lib/format";
import type { ConnectionState } from "@/lib/types";

interface HeaderProps {
  totalValue: number;
  cash: number;
  unrealizedPnl: number;
  status: ConnectionState;
  marketSource: string | null;
}

/** Terminals show the wall clock; it also proves the page is alive. */
function Clock() {
  const [now, setNow] = useState<string>("");

  useEffect(() => {
    const render = () =>
      setNow(new Date().toLocaleTimeString("en-US", { hour12: false }));
    render();
    const timer = window.setInterval(render, 1000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <span suppressHydrationWarning className="num text-[13px] text-ink-mid">
      {now}
    </span>
  );
}

const STATUS_COPY: Record<ConnectionState, string> = {
  connected: "Live",
  reconnecting: "Reconnecting",
  disconnected: "Offline",
};

const STATUS_COLOR: Record<ConnectionState, string> = {
  connected: "var(--color-up)",
  reconnecting: "var(--color-accent)",
  disconnected: "var(--color-down)",
};

function Readout({
  label,
  children,
  width,
}: {
  label: string;
  children: React.ReactNode;
  width?: string;
}) {
  return (
    <div className="flex flex-col justify-center border-l border-edge px-4 py-1" style={{ minWidth: width }}>
      <span className="panel-title leading-none">{label}</span>
      <span className="mt-1 leading-none">{children}</span>
    </div>
  );
}

export function Header({ totalValue, cash, unrealizedPnl, status, marketSource }: HeaderProps) {
  const pnlDirection = signDirection(unrealizedPnl);
  const pnlColor =
    pnlDirection === "up" ? "text-up" : pnlDirection === "down" ? "text-down" : "text-ink-mid";
  const invested = totalValue - cash;
  const pnlPercent = invested !== 0 ? (unrealizedPnl / Math.abs(invested)) * 100 : 0;

  return (
    <header className="flex h-[52px] shrink-0 items-stretch border-b border-edge bg-ground">
      <div className="flex items-center gap-2.5 pl-4 pr-5">
        <span className="h-5 w-[3px] bg-accent" aria-hidden="true" />
        <span className="font-cond text-[17px] font-semibold tracking-[0.01em] text-ink">FinAlly</span>
      </div>

      <Readout label="Portfolio value" width="152px">
        <span data-testid="total-value" className="num text-[19px] font-medium text-ink">
          {fmtMoney(totalValue)}
        </span>
      </Readout>

      <Readout label="Unrealized" width="140px">
        <span className={`num text-[15px] ${pnlColor}`}>
          {fmtSigned(unrealizedPnl)}
          <span className="ml-2 text-[12px] opacity-70">{fmtPercent(pnlPercent)}</span>
        </span>
      </Readout>

      <Readout label="Cash" width="128px">
        <span data-testid="cash-balance" className="num text-[15px] text-ink-mid">
          {fmtMoney(cash)}
        </span>
      </Readout>

      <div className="flex-1 border-l border-edge" />

      <Readout label={marketSource === "massive" ? "Live market feed" : "Simulated feed"}>
        <Clock />
      </Readout>

      <div
        data-testid="connection-status"
        data-state={status}
        className="flex items-center gap-2 border-l border-edge px-4"
        title={`Price stream: ${STATUS_COPY[status]}`}
      >
        <span
          className={`h-[7px] w-[7px] rounded-full ${status === "reconnecting" ? "pulse-dot" : ""}`}
          style={{ background: STATUS_COLOR[status] }}
          aria-hidden="true"
        />
        <span className="font-cond text-[11px] text-ink-mid">{STATUS_COPY[status]}</span>
      </div>
    </header>
  );
}
