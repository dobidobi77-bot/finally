import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Header } from "@/components/Header";
import { Heatmap } from "@/components/Heatmap";
import { MainChart } from "@/components/MainChart";
import { PnlChart } from "@/components/PnlChart";
import { PositionsTable } from "@/components/PositionsTable";
import { portfolio, prices, snapshots, tick } from "./fixtures";

/** jsdom reports a 0x0 client box; give useMeasure a real one so layouts run. */
function sized(width = 400, height = 200) {
  vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(width);
  vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(height);
}

describe("Header", () => {
  it("shows the portfolio figures", () => {
    render(<Header totalValue={6950} cash={5000} unrealizedPnl={50} status="connected" marketSource="simulator" />);
    expect(screen.getByTestId("total-value")).toHaveTextContent("6,950.00");
    expect(screen.getByTestId("cash-balance")).toHaveTextContent("5,000.00");
    expect(screen.getByText("+50.00", { exact: false })).toBeInTheDocument();
  });

  it("reports the stream state on the status dot", () => {
    const { rerender } = render(
      <Header totalValue={0} cash={0} unrealizedPnl={0} status="connected" marketSource="simulator" />,
    );
    expect(screen.getByTestId("connection-status")).toHaveAttribute("data-state", "connected");

    rerender(<Header totalValue={0} cash={0} unrealizedPnl={0} status="reconnecting" marketSource="simulator" />);
    expect(screen.getByTestId("connection-status")).toHaveAttribute("data-state", "reconnecting");

    rerender(<Header totalValue={0} cash={0} unrealizedPnl={0} status="disconnected" marketSource="simulator" />);
    expect(screen.getByTestId("connection-status")).toHaveAttribute("data-state", "disconnected");
  });
});

describe("PositionsTable", () => {
  it("renders a row per position with market value from the live price", () => {
    render(
      <PositionsTable
        positions={portfolio.positions}
        prices={prices}
        selected={null}
        onSelect={vi.fn()}
      />,
    );
    const row = screen.getByTestId("position-row-AAPL");
    expect(row).toHaveTextContent("10"); // quantity
    expect(row).toHaveTextContent("190.00"); // avg cost
    expect(row).toHaveTextContent("1,950.00"); // 10 shares at the streaming 195.00
    expect(row).toHaveTextContent("+50.00"); // unrealized
    expect(row).toHaveTextContent("+2.63%");
  });

  it("selects a ticker when a row is clicked", async () => {
    const onSelect = vi.fn();
    render(
      <PositionsTable
        positions={portfolio.positions}
        prices={prices}
        selected={null}
        onSelect={onSelect}
      />,
    );
    await userEvent.click(screen.getByTestId("position-row-AAPL"));
    expect(onSelect).toHaveBeenCalledWith("AAPL");
  });

  it("invites a first trade when flat", () => {
    render(<PositionsTable positions={[]} prices={{}} selected={null} onSelect={vi.fn()} />);
    expect(screen.getByText(/No open positions/i)).toBeInTheDocument();
  });
});

describe("Heatmap", () => {
  it("mounts with the expected test id", () => {
    render(<Heatmap positions={portfolio.positions} selected="AAPL" onSelect={vi.fn()} />);
    expect(screen.getByTestId("portfolio-heatmap")).toBeInTheDocument();
  });

  it("explains itself when there are no positions", () => {
    render(<Heatmap positions={[]} selected={null} onSelect={vi.fn()} />);
    expect(screen.getByText(/Buy a position and it appears here/i)).toBeInTheDocument();
  });

  it("renders one heatmap-tile-<T> per position once it has a size", () => {
    sized();
    const positions = [
      ...portfolio.positions,
      { ticker: "GOOGL", quantity: 5, avg_cost: 175, current_price: 170, unrealized_pnl: -25, pnl_percent: -2.86 },
    ];
    render(<Heatmap positions={positions} selected={null} onSelect={vi.fn()} />);
    expect(screen.getByTestId("heatmap-tile-AAPL")).toBeInTheDocument();
    expect(screen.getByTestId("heatmap-tile-GOOGL")).toBeInTheDocument();
    expect(screen.getAllByTestId(/^heatmap-tile-/)).toHaveLength(2);
  });

  it("selects the ticker when a tile is clicked", async () => {
    sized();
    const onSelect = vi.fn();
    render(<Heatmap positions={portfolio.positions} selected={null} onSelect={onSelect} />);
    await userEvent.click(screen.getByTestId("heatmap-tile-AAPL"));
    expect(onSelect).toHaveBeenCalledWith("AAPL");
  });
});

describe("MainChart", () => {
  it("names the selected ticker and its daily change", () => {
    render(<MainChart ticker="AAPL" tick={tick("AAPL", 195, 194.5, 190)} points={[]} />);
    const chart = screen.getByTestId("main-chart");
    expect(chart).toHaveTextContent("AAPL");
    expect(chart).toHaveTextContent("195.00");
    expect(chart).toHaveTextContent("+2.63%");
  });

  it("says the chart fills from the stream before any ticks arrive", () => {
    render(<MainChart ticker="AAPL" tick={undefined} points={[]} />);
    expect(screen.getByText(/draws itself as AAPL ticks arrive/i)).toBeInTheDocument();
  });

  it("reports data-points=0 while empty, never omitting the attribute", () => {
    render(<MainChart ticker={null} tick={undefined} points={undefined} />);
    expect(screen.getByTestId("main-chart")).toHaveAttribute("data-points", "0");
  });

  it("reports the number of SSE points plotted", () => {
    sized();
    const points = [
      { t: 1_757_000_000, v: 194.5 },
      { t: 1_757_000_001, v: 195.0 },
      { t: 1_757_000_002, v: 195.2 },
    ];
    render(<MainChart ticker="AAPL" tick={tick("AAPL", 195.2, 195, 190)} points={points} />);
    expect(screen.getByTestId("main-chart")).toHaveAttribute("data-points", "3");
  });
});

describe("PnlChart", () => {
  it("mounts and reports the change across the window", () => {
    render(<PnlChart snapshots={snapshots} />);
    const chart = screen.getByTestId("pnl-chart");
    expect(chart).toBeInTheDocument();
    expect(chart).toHaveTextContent("+1.80%"); // 10000 -> 10180
  });

  it("waits for a second snapshot before drawing", () => {
    render(<PnlChart snapshots={[snapshots[0]]} />);
    expect(screen.getByText(/recorded after every trade/i)).toBeInTheDocument();
  });

  it("reports data-points=0 with no snapshots, never omitting the attribute", () => {
    render(<PnlChart snapshots={[]} />);
    expect(screen.getByTestId("pnl-chart")).toHaveAttribute("data-points", "0");
  });

  it("reports the number of snapshots plotted", () => {
    sized();
    render(<PnlChart snapshots={snapshots} />);
    expect(screen.getByTestId("pnl-chart")).toHaveAttribute("data-points", "3");
  });
});
