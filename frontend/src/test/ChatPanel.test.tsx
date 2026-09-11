import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ChatPanel, describeAction } from "@/components/ChatPanel";
import { chatMessages } from "./fixtures";

function renderPanel(overrides: Partial<React.ComponentProps<typeof ChatPanel>> = {}) {
  const props = {
    messages: chatMessages,
    pending: false,
    collapsed: false,
    onToggle: vi.fn(),
    onSend: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
  render(<ChatPanel {...props} />);
  return props;
}

describe("ChatPanel", () => {
  it("renders messages oldest first with indexed test ids", () => {
    renderPanel();
    expect(screen.getByTestId("chat-message-0")).toHaveTextContent("Buy 10 AAPL");
    expect(screen.getByTestId("chat-message-0")).toHaveAttribute("data-role", "user");
    expect(screen.getByTestId("chat-message-1")).toHaveTextContent("Adding 10 shares of AAPL");
  });

  it("renders one action chip per receipt, successes and failures alike", () => {
    renderPanel();
    const chips = screen.getAllByTestId("chat-action-chip");
    expect(chips).toHaveLength(3);
    expect(chips[0]).toHaveTextContent("Bought 10 AAPL at 195.00");
    expect(chips[1]).toHaveTextContent("Buy 100 TSLA rejected: Insufficient cash");
    expect(chips[1]).toHaveAttribute("data-ok", "false");
    expect(chips[2]).toHaveTextContent("Added PYPL");
  });

  it("shows a loading indicator and disables input while a request is in flight", () => {
    renderPanel({ pending: true });
    expect(screen.getByTestId("chat-loading")).toBeInTheDocument();
    expect(screen.getByTestId("chat-input")).toBeDisabled();
    expect(screen.getByTestId("chat-send")).toBeDisabled();
  });

  it("hides the loading indicator when idle", () => {
    renderPanel();
    expect(screen.queryByTestId("chat-loading")).not.toBeInTheDocument();
  });

  it("sends the trimmed draft and clears the input", async () => {
    const props = renderPanel({ messages: [] });
    const input = screen.getByTestId("chat-input");
    await userEvent.type(input, "  how am I doing?  ");
    await userEvent.click(screen.getByTestId("chat-send"));

    expect(props.onSend).toHaveBeenCalledWith("how am I doing?");
    expect(input).toHaveValue("");
  });

  it("collapses to a rail that can be reopened", async () => {
    const props = renderPanel({ collapsed: true });
    const panel = screen.getByTestId("chat-panel");
    expect(panel).toHaveAttribute("data-collapsed", "true");
    expect(screen.queryByTestId("chat-input")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /open the assistant panel/i }));
    expect(props.onToggle).toHaveBeenCalled();
  });
});

describe("describeAction", () => {
  it("reads as a receipt for each action shape", () => {
    expect(
      describeAction({ type: "trade", ok: true, ticker: "AAPL", side: "sell", quantity: 2.5, price: 10 }),
    ).toBe("Sold 2.5 AAPL at 10.00");
    expect(describeAction({ type: "watchlist", ok: true, ticker: "PYPL", action: "remove" })).toBe(
      "Removed PYPL",
    );
    expect(
      describeAction({ type: "watchlist", ok: false, ticker: "ZZZZZZ", action: "add", error: "Invalid ticker format" }),
    ).toBe("Add ZZZZZZ rejected: Invalid ticker format");
  });
});
