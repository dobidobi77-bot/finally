"""System prompt and prompt assembly.

The model sees three things: who it is, a snapshot of the portfolio and
watchlist, and the recent conversation (BUILD_CONTRACT B5 - last 20 messages).
"""

from __future__ import annotations

from app.llm import deps

SYSTEM_PROMPT = """You are FinAlly, an AI trading assistant embedded in a simulated trading workstation.

Your job:
- Analyse portfolio composition, risk concentration, and profit and loss.
- Suggest trades and always give the reasoning behind them.
- Execute trades when the user asks for them or agrees to your suggestion.
- Manage the watchlist proactively when it helps the user.

Rules:
- Be concise and data-driven. Cite the numbers you were given.
- All money is simulated. Market orders only, filled instantly at the current price.
- Only put a trade in `trades` when the user asked for it or agreed to it. Never trade on a question.
- Tickers are 1 to 5 uppercase letters.
- The trades you list are executed after your message is written, so never claim a
  fill price or a result in your prose. Describe the intent instead.
- Always reply with JSON matching the required schema. `message` is required;
  `trades` and `watchlist_changes` may be empty."""


def format_context(portfolio: dict, watchlist: dict) -> str:
    """Render the portfolio and watchlist snapshot as compact prompt text."""
    lines = ["PORTFOLIO SNAPSHOT"]
    lines.append(f"Cash: ${portfolio.get('cash', 0):,.2f}")
    lines.append(f"Total value: ${portfolio.get('total_value', 0):,.2f}")
    lines.append(f"Unrealized P&L: ${portfolio.get('unrealized_pnl', 0):,.2f}")

    positions = portfolio.get("positions") or []
    if positions:
        lines.append("Positions (ticker, qty, avg cost, current, unrealized P&L, %):")
        for pos in positions:
            lines.append(
                f"- {pos.get('ticker')}: {pos.get('quantity')} @ ${pos.get('avg_cost', 0):,.2f}"
                f" | now ${pos.get('current_price', 0):,.2f}"
                f" | P&L ${pos.get('unrealized_pnl', 0):,.2f}"
                f" ({pos.get('pnl_percent', 0):+.2f}%)"
            )
    else:
        lines.append("Positions: none")

    tickers = watchlist.get("tickers") or []
    if tickers:
        lines.append("Watchlist (ticker, price, change % since open):")
        for row in tickers:
            price = row.get("price")
            price_text = f"${price:,.2f}" if isinstance(price, (int, float)) else "no price yet"
            change = row.get("change_percent")
            change_text = f"{change:+.2f}%" if isinstance(change, (int, float)) else "n/a"
            lines.append(f"- {row.get('ticker')}: {price_text} ({change_text})")
    else:
        lines.append("Watchlist: empty")

    return "\n".join(lines)


async def build_messages(history: list, message: str) -> list[dict]:
    """Build the message list for the LLM call.

    `history` already ends with the current user message, because `handle_chat`
    persists it before loading the window. The fallback covers an empty history.
    """
    portfolio = await deps.get_portfolio()
    watchlist = await deps.get_watchlist()
    turns = [{"role": m.role, "content": m.content} for m in history]
    if not turns:
        turns = [{"role": "user", "content": message}]
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": format_context(portfolio, watchlist)},
        *turns,
    ]
