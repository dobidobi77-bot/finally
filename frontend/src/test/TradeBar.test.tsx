import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TradeBar } from "@/components/TradeBar";
import { prices } from "./fixtures";

function renderBar(overrides: Partial<React.ComponentProps<typeof TradeBar>> = {}) {
  const props = {
    prices,
    cash: 5000,
    selected: "AAPL" as string | null,
    onTrade: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
  render(<TradeBar {...props} />);
  return props;
}

describe("TradeBar", () => {
  it("loads the selected ticker and shows the live notional", async () => {
    renderBar();
    expect(screen.getByTestId("trade-ticker")).toHaveValue("AAPL");
    await userEvent.type(screen.getByTestId("trade-quantity"), "10");
    expect(screen.getByText(/1,950\.00/)).toBeInTheDocument();
  });

  it("buys at the market with no confirmation step", async () => {
    const props = renderBar();
    await userEvent.type(screen.getByTestId("trade-quantity"), "3");
    await userEvent.click(screen.getByTestId("trade-buy"));
    expect(props.onTrade).toHaveBeenCalledWith("AAPL", 3, "buy");
  });

  it("sells with the same inputs", async () => {
    const props = renderBar();
    await userEvent.type(screen.getByTestId("trade-quantity"), "1.5");
    await userEvent.click(screen.getByTestId("trade-sell"));
    expect(props.onTrade).toHaveBeenCalledWith("AAPL", 1.5, "sell");
  });

  it("rejects a non-positive quantity before calling the backend", async () => {
    const props = renderBar();
    await userEvent.type(screen.getByTestId("trade-quantity"), "0");
    await userEvent.click(screen.getByTestId("trade-buy"));

    expect(props.onTrade).not.toHaveBeenCalled();
    expect(screen.getByTestId("trade-error")).toHaveTextContent("Quantity must be greater than zero");
  });

  it("asks for a ticker when the field is empty", async () => {
    const props = renderBar({ selected: null });
    await userEvent.type(screen.getByTestId("trade-quantity"), "5");
    await userEvent.click(screen.getByTestId("trade-buy"));

    expect(props.onTrade).not.toHaveBeenCalled();
    expect(screen.getByTestId("trade-error")).toHaveTextContent("Enter a ticker");
  });

  it("shows a backend rejection inline", async () => {
    renderBar({ onTrade: vi.fn().mockRejectedValue(new Error("Insufficient cash")) });
    await userEvent.type(screen.getByTestId("trade-quantity"), "500");
    await userEvent.click(screen.getByTestId("trade-buy"));

    expect(await screen.findByTestId("trade-error")).toHaveTextContent("Insufficient cash");
  });

  it("mounts the error region only while there is an error", async () => {
    renderBar({ onTrade: vi.fn().mockRejectedValue(new Error("Insufficient cash")) });
    expect(screen.queryByTestId("trade-error")).not.toBeInTheDocument();

    await userEvent.type(screen.getByTestId("trade-quantity"), "500");
    await userEvent.click(screen.getByTestId("trade-buy"));
    expect(await screen.findByTestId("trade-error")).toBeInTheDocument();
  });

  it("passes a long ticker through uncut so the backend can reject it", async () => {
    const props = renderBar({ selected: null });
    await userEvent.type(screen.getByTestId("trade-ticker"), "GOOGLE");
    await userEvent.type(screen.getByTestId("trade-quantity"), "1");
    await userEvent.click(screen.getByTestId("trade-buy"));
    expect(props.onTrade).toHaveBeenCalledWith("GOOGLE", 1, "buy");
  });

  it("uppercases a manually typed ticker", async () => {
    const props = renderBar({ selected: null });
    await userEvent.type(screen.getByTestId("trade-ticker"), "tsla");
    await userEvent.type(screen.getByTestId("trade-quantity"), "2");
    await userEvent.click(screen.getByTestId("trade-buy"));
    expect(props.onTrade).toHaveBeenCalledWith("TSLA", 2, "buy");
  });
});
