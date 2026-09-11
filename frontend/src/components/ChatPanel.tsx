"use client";

import { useEffect, useRef, useState } from "react";
import { fmtClock, fmtMoney, fmtQuantity } from "@/lib/format";
import type { ChatAction, ChatMessage } from "@/lib/types";

interface ChatPanelProps {
  messages: ChatMessage[];
  pending: boolean;
  collapsed: boolean;
  onToggle: () => void;
  onSend: (message: string) => Promise<void>;
}

/** Turns an action receipt into the sentence shown on its chip (B6). */
export function describeAction(action: ChatAction): string {
  if (action.type === "trade") {
    const size = `${fmtQuantity(action.quantity)} ${action.ticker}`;
    if (action.ok) {
      const verb = action.side === "buy" ? "Bought" : "Sold";
      const at = action.price != null ? ` at ${fmtMoney(action.price)}` : "";
      return `${verb} ${size}${at}`;
    }
    const verb = action.side === "buy" ? "Buy" : "Sell";
    return `${verb} ${size} rejected: ${action.error ?? "unknown reason"}`;
  }

  const verb = action.action === "add" ? "Added" : "Removed";
  if (action.ok) return `${verb} ${action.ticker}`;
  return `${action.action === "add" ? "Add" : "Remove"} ${action.ticker} rejected: ${
    action.error ?? "unknown reason"
  }`;
}

function ActionChip({ action }: { action: ChatAction }) {
  const tone = action.ok
    ? action.type === "trade" && action.side === "sell"
      ? "border-down/50 text-down"
      : "border-up/50 text-up"
    : "border-down/50 text-down";

  return (
    <span
      data-testid="chat-action-chip"
      data-ok={action.ok ? "true" : "false"}
      className={`num inline-flex items-center rounded-xs border bg-void/60 px-1.5 py-0.5 text-[10px] ${tone}`}
    >
      {describeAction(action)}
    </span>
  );
}

export function ChatPanel({ messages, pending, collapsed, onToggle, onSend }: ChatPanelProps) {
  const [draft, setDraft] = useState("");
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = scroller.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [messages, pending]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || pending) return;
    setDraft("");
    await onSend(text);
  }

  if (collapsed) {
    return (
      <section
        data-testid="chat-panel"
        data-collapsed="true"
        className="flex w-full shrink-0 items-center justify-between border-edge bg-ground px-3 py-2 lg:w-[38px] lg:flex-col lg:justify-start lg:border-l lg:px-0 lg:py-3"
      >
        <button
          type="button"
          onClick={onToggle}
          aria-label="Open the assistant panel"
          className="font-cond text-[11px] text-ink-mid hover:text-accent lg:[writing-mode:vertical-rl]"
        >
          Assistant
        </button>
      </section>
    );
  }

  return (
    <section
      data-testid="chat-panel"
      data-collapsed="false"
      className="flex w-full shrink-0 flex-col border-edge bg-ground lg:w-[360px] lg:border-l"
    >
      <div className="flex h-8 shrink-0 items-center justify-between border-b border-edge px-3">
        <span className="panel-title">Assistant</span>
        <button
          type="button"
          onClick={onToggle}
          aria-label="Collapse the assistant panel"
          className="font-cond text-[11px] text-ink-dim hover:text-accent"
        >
          Hide
        </button>
      </div>

      <div ref={scroller} className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
        {messages.length === 0 && !pending && (
          <p className="text-[12px] leading-relaxed text-ink-dim">
            Ask about the portfolio, or say what to trade. Trades run as soon as the assistant
            decides on them.
          </p>
        )}

        {messages.map((message, index) => {
          const mine = message.role === "user";
          return (
            <div
              key={message.id || index}
              data-testid={`chat-message-${index}`}
              data-role={message.role}
              className={mine ? "pl-6" : ""}
            >
              <div className="mb-1 flex items-baseline gap-2">
                <span
                  className={`font-cond text-[10px] tracking-[0.04em] ${
                    mine ? "text-blue" : "text-accent"
                  }`}
                >
                  {mine ? "You" : "FinAlly"}
                </span>
                <span className="num text-[10px] text-ink-dim">{fmtClock(message.created_at)}</span>
              </div>

              <div
                className={`rounded-xs border px-2.5 py-2 text-[12px] leading-relaxed whitespace-pre-wrap ${
                  mine ? "border-edge bg-panel text-ink-mid" : "border-edge-bright bg-panel text-ink"
                }`}
              >
                {message.content}
              </div>

              {message.actions && message.actions.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {message.actions.map((action, actionIndex) => (
                    <ActionChip key={actionIndex} action={action} />
                  ))}
                </div>
              )}
            </div>
          );
        })}

        {pending && (
          <div data-testid="chat-loading" className="flex items-center gap-2 text-[11px] text-ink-dim">
            <span className="pulse-dot h-[6px] w-[6px] rounded-full bg-accent" aria-hidden="true" />
            Thinking
          </div>
        )}
      </div>

      <form onSubmit={submit} className="shrink-0 border-t border-edge p-2">
        <div className="flex gap-1.5">
          <input
            data-testid="chat-input"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            disabled={pending}
            placeholder="Ask or instruct"
            aria-label="Message the assistant"
            className="min-w-0 flex-1 rounded-xs border border-edge bg-panel px-2 py-1.5 text-[12px] placeholder:text-ink-dim disabled:opacity-50"
          />
          <button
            type="submit"
            data-testid="chat-send"
            disabled={pending}
            className="rounded-xs bg-purple px-3 py-1.5 text-[12px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </form>
    </section>
  );
}
