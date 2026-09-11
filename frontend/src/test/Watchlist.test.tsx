import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Watchlist } from "@/components/Watchlist";
import { prices, watchlist } from "./fixtures";

function renderWatchlist(overrides: Partial<React.ComponentProps<typeof Watchlist>> = {}) {
  const props = {
    entries: watchlist,
    prices,
    series: { AAPL: [{ t: 1, v: 190 }, { t: 2, v: 195 }] },
    selected: "AAPL",
    onSelect: vi.fn(),
    onAdd: vi.fn(),
    onRemove: vi.fn(),
    error: null,
    ...overrides,
  };
  render(<Watchlist {...props} />);
  return props;
}

describe("Watchlist", () => {
  it("renders a row per ticker with the live price", () => {
    renderWatchlist();
    expect(screen.getByTestId("watchlist")).toBeInTheDocument();
    expect(screen.getByTestId("watchlist-row-AAPL")).toBeInTheDocument();
    expect(screen.getByTestId("watchlist-price-AAPL")).toHaveTextContent("195.00");
    expect(screen.getByTestId("watchlist-price-GOOGL")).toHaveTextContent("170.00");
  });

  it("shows the daily change against the session open", () => {
    renderWatchlist();
    // AAPL 195 against an open of 190; GOOGL 170 against an open of 175.
    expect(screen.getByTestId("watchlist-row-AAPL")).toHaveTextContent("+2.63%");
    expect(screen.getByTestId("watchlist-row-GOOGL")).toHaveTextContent("-2.86%");
  });

  it("marks the selected row and selects on click", async () => {
    const props = renderWatchlist();
    expect(screen.getByTestId("watchlist-row-AAPL")).toHaveAttribute("data-selected", "true");

    await userEvent.click(screen.getByTestId("watchlist-row-GOOGL"));
    expect(props.onSelect).toHaveBeenCalledWith("GOOGL");
  });

  it("adds a ticker, upper-casing the input", async () => {
    const props = renderWatchlist();
    await userEvent.type(screen.getByTestId("watchlist-add-input"), "pypl");
    await userEvent.click(screen.getByTestId("watchlist-add-submit"));
    expect(props.onAdd).toHaveBeenCalledWith("PYPL");
  });

  it("passes a long symbol through uncut so the backend can reject it", async () => {
    const props = renderWatchlist();
    await userEvent.type(screen.getByTestId("watchlist-add-input"), "ZZZZZZ");
    await userEvent.click(screen.getByTestId("watchlist-add-submit"));
    expect(props.onAdd).toHaveBeenCalledWith("ZZZZZZ");
  });

  it("removes a ticker without selecting the row", async () => {
    const props = renderWatchlist();
    await userEvent.click(screen.getByTestId("watchlist-remove-GOOGL"));
    expect(props.onRemove).toHaveBeenCalledWith("GOOGL");
    expect(props.onSelect).not.toHaveBeenCalled();
  });

  it("surfaces a rejection from the backend verbatim", () => {
    renderWatchlist({ error: "Invalid ticker format" });
    expect(screen.getByTestId("watchlist-error")).toHaveTextContent("Invalid ticker format");
  });

  it("mounts the error region only while there is an error", () => {
    renderWatchlist({ error: null });
    expect(screen.queryByTestId("watchlist-error")).not.toBeInTheDocument();
  });

  it("invites the first symbol when the list is empty", () => {
    renderWatchlist({ entries: [] });
    expect(screen.getByText(/Add a symbol below/i)).toBeInTheDocument();
  });
});
