import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Terminal from "@/app/page";
import { chatMessages, portfolio, snapshots, watchlist } from "./fixtures";

const api = vi.hoisted(() => ({
  getPortfolio: vi.fn(),
  getWatchlist: vi.fn(),
  getHistory: vi.fn(),
  getChatHistory: vi.fn(),
  getHealth: vi.fn(),
  executeTrade: vi.fn(),
  addWatchlistTicker: vi.fn(),
  removeWatchlistTicker: vi.fn(),
  sendChatMessage: vi.fn(),
}));

vi.mock("@/lib/api", () => ({ ...api, ApiError: Error }));

beforeEach(() => {
  api.getPortfolio.mockResolvedValue(portfolio);
  api.getWatchlist.mockResolvedValue({ tickers: watchlist });
  api.getHistory.mockResolvedValue({ snapshots });
  api.getChatHistory.mockResolvedValue({ messages: chatMessages });
  api.getHealth.mockResolvedValue({ status: "ok", market_source: "simulator", cache_ready: true });
  api.executeTrade.mockResolvedValue({ ok: true, trade: {}, portfolio });
  api.addWatchlistTicker.mockResolvedValue({ ok: true, ticker: "PYPL" });
  api.removeWatchlistTicker.mockResolvedValue({ ok: true });
  api.sendChatMessage.mockResolvedValue({
    id: "m3",
    role: "assistant",
    content: "Done.",
    actions: [{ type: "trade", ok: true, ticker: "AAPL", side: "buy", quantity: 1, price: 195 }],
    created_at: "2026-09-11T10:05:00Z",
  });
});

describe("Terminal bootstrap", () => {
  it("loads portfolio, watchlist, history and chat on page load", async () => {
    render(<Terminal />);
    await waitFor(() => expect(screen.getByTestId("watchlist-row-AAPL")).toBeInTheDocument());

    expect(api.getPortfolio).toHaveBeenCalled();
    expect(api.getWatchlist).toHaveBeenCalled();
    expect(api.getHistory).toHaveBeenCalled();
    expect(api.getChatHistory).toHaveBeenCalledWith(20);
    expect(screen.getByTestId("chat-message-0")).toHaveTextContent("Buy 10 AAPL");
  });

  it("mounts every panel of the terminal", async () => {
    render(<Terminal />);
    await waitFor(() => expect(screen.getByTestId("watchlist-row-AAPL")).toBeInTheDocument());

    for (const id of [
      "connection-status",
      "cash-balance",
      "total-value",
      "watchlist",
      "main-chart",
      "positions-table",
      "portfolio-heatmap",
      "pnl-chart",
      "trade-ticker",
      "trade-quantity",
      "trade-buy",
      "trade-sell",
      "chat-panel",
      "chat-input",
      "chat-send",
    ]) {
      expect(screen.getByTestId(id)).toBeInTheDocument();
    }
  });

  it("values the portfolio as cash plus positions at the last price", async () => {
    render(<Terminal />);
    // 5,000 cash + 10 AAPL at 195.00
    await waitFor(() => expect(screen.getByTestId("total-value")).toHaveTextContent("6,950.00"));
    expect(screen.getByTestId("cash-balance")).toHaveTextContent("5,000.00");
  });

  it("selects the first watched symbol so the chart is never blank", async () => {
    render(<Terminal />);
    await waitFor(() =>
      expect(screen.getByTestId("watchlist-row-AAPL")).toHaveAttribute("data-selected", "true"),
    );
    expect(screen.getByTestId("trade-ticker")).toHaveValue("AAPL");
  });
});

describe("Terminal actions", () => {
  it("adds a ticker and reloads the watchlist", async () => {
    render(<Terminal />);
    await waitFor(() => expect(screen.getByTestId("watchlist-row-AAPL")).toBeInTheDocument());

    await userEvent.type(screen.getByTestId("watchlist-add-input"), "PYPL");
    await userEvent.click(screen.getByTestId("watchlist-add-submit"));

    await waitFor(() => expect(api.addWatchlistTicker).toHaveBeenCalledWith("PYPL"));
    expect(api.getWatchlist).toHaveBeenCalledTimes(2);
  });

  it("drops a removed ticker from the rail straight away", async () => {
    render(<Terminal />);
    await waitFor(() => expect(screen.getByTestId("watchlist-row-GOOGL")).toBeInTheDocument());

    await userEvent.click(screen.getByTestId("watchlist-remove-GOOGL"));

    await waitFor(() => expect(screen.queryByTestId("watchlist-row-GOOGL")).not.toBeInTheDocument());
    expect(api.removeWatchlistTicker).toHaveBeenCalledWith("GOOGL");
  });

  it("reports a rejected add without dropping the rows", async () => {
    api.addWatchlistTicker.mockRejectedValue(new Error("Invalid ticker format"));
    render(<Terminal />);
    await waitFor(() => expect(screen.getByTestId("watchlist-row-AAPL")).toBeInTheDocument());

    await userEvent.type(screen.getByTestId("watchlist-add-input"), "ZZZZZ");
    await userEvent.click(screen.getByTestId("watchlist-add-submit"));

    expect(await screen.findByText("Invalid ticker format")).toBeInTheDocument();
    expect(screen.getByTestId("watchlist-row-AAPL")).toBeInTheDocument();
  });

  it("executes a market buy and refreshes the portfolio", async () => {
    render(<Terminal />);
    await waitFor(() => expect(screen.getByTestId("watchlist-row-AAPL")).toBeInTheDocument());

    await userEvent.type(screen.getByTestId("trade-quantity"), "2");
    await userEvent.click(screen.getByTestId("trade-buy"));

    await waitFor(() => expect(api.executeTrade).toHaveBeenCalledWith("AAPL", 2, "buy"));
    await waitFor(() => expect(api.getHistory).toHaveBeenCalledTimes(2));
  });

  it("surfaces a trade rejection in the command bar", async () => {
    api.executeTrade.mockRejectedValue(new Error("Insufficient cash"));
    render(<Terminal />);
    await waitFor(() => expect(screen.getByTestId("watchlist-row-AAPL")).toBeInTheDocument());

    await userEvent.type(screen.getByTestId("trade-quantity"), "9999");
    await userEvent.click(screen.getByTestId("trade-buy"));

    expect(await screen.findByTestId("trade-error")).toHaveTextContent("Insufficient cash");
  });

  it("appends the user message, then the reply and its receipts", async () => {
    render(<Terminal />);
    await waitFor(() => expect(screen.getByTestId("chat-message-1")).toBeInTheDocument());

    await userEvent.type(screen.getByTestId("chat-input"), "buy one AAPL");
    await userEvent.click(screen.getByTestId("chat-send"));

    expect(await screen.findByTestId("chat-message-2")).toHaveTextContent("buy one AAPL");
    expect(await screen.findByTestId("chat-message-3")).toHaveTextContent("Done.");
    await waitFor(() => expect(api.sendChatMessage).toHaveBeenCalledWith("buy one AAPL"));
  });
});
