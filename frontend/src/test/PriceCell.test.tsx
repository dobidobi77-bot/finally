import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PriceCell } from "@/components/PriceCell";

describe("PriceCell", () => {
  it("renders the price without a flash on first paint", () => {
    render(<PriceCell price={190.5} testId="p" />);
    const cell = screen.getByTestId("p");
    expect(cell).toHaveTextContent("190.50");
    expect(cell.className).not.toMatch(/flash-/);
  });

  it("flashes green on an uptick", () => {
    const { rerender } = render(<PriceCell price={190.5} testId="p" />);
    rerender(<PriceCell price={191.25} testId="p" />);

    const cell = screen.getByTestId("p");
    expect(cell).toHaveClass("flash-up");
    expect(cell).toHaveAttribute("data-direction", "up");
    expect(cell).toHaveTextContent("191.25");
  });

  it("flashes red on a downtick", () => {
    const { rerender } = render(<PriceCell price={190.5} testId="p" />);
    rerender(<PriceCell price={189.0} testId="p" />);

    const cell = screen.getByTestId("p");
    expect(cell).toHaveClass("flash-down");
    expect(cell).toHaveAttribute("data-direction", "down");
  });

  it("does not flash when the price is unchanged", () => {
    const { rerender } = render(<PriceCell price={190.5} testId="p" />);
    rerender(<PriceCell price={190.5} testId="p" />);
    expect(screen.getByTestId("p").className).not.toMatch(/flash-/);
  });

  it("shows a placeholder when no price has arrived", () => {
    render(<PriceCell price={null} testId="p" />);
    expect(screen.getByTestId("p")).toHaveTextContent("--");
  });
});
