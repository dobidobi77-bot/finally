import { expect, type Locator, type Page, type Response } from "@playwright/test";

/** Seeded watchlist from PLAN.md section 7. */
export const DEFAULT_TICKERS = [
  "AAPL",
  "GOOGL",
  "MSFT",
  "AMZN",
  "TSLA",
  "NVDA",
  "META",
  "JPM",
  "V",
  "NFLX",
] as const;

/**
 * Parse a money or percent string as rendered in the UI.
 * Handles "$10,000.00", "-$1,234.50", "($1,234.50)", "+2.31%".
 */
export function parseNumber(text: string | null): number {
  if (text === null) throw new Error("expected text, got null");
  const negative = /^\s*\(.*\)\s*$/.test(text) || text.includes("-");
  const digits = text.replace(/[^0-9.]/g, "");
  if (digits === "" || Number.isNaN(Number(digits))) {
    throw new Error(`cannot parse a number out of ${JSON.stringify(text)}`);
  }
  return Number(digits) * (negative ? -1 : 1);
}

/**
 * Page object over the data-testid contract frozen in INTERFACES section 5.
 * Every selector in the suite goes through here, so a renamed testid is one
 * edit rather than nine.
 */
export class App {
  constructor(readonly page: Page) {}

  async open(): Promise<void> {
    await this.page.goto("/");
    // The header is the first thing that must render; the connection dot proves
    // the SSE wiring got as far as trying.
    await expect(this.connectionStatus).toBeVisible();
  }

  // -- header ---------------------------------------------------------------
  get connectionStatus(): Locator {
    return this.page.getByTestId("connection-status");
  }
  get cashBalance(): Locator {
    return this.page.getByTestId("cash-balance");
  }
  get totalValue(): Locator {
    return this.page.getByTestId("total-value");
  }

  async cash(): Promise<number> {
    return parseNumber(await this.cashBalance.textContent());
  }
  async total(): Promise<number> {
    return parseNumber(await this.totalValue.textContent());
  }

  // -- watchlist ------------------------------------------------------------
  get watchlist(): Locator {
    return this.page.getByTestId("watchlist");
  }
  watchlistRow(ticker: string): Locator {
    return this.page.getByTestId(`watchlist-row-${ticker}`);
  }
  watchlistPrice(ticker: string): Locator {
    return this.page.getByTestId(`watchlist-price-${ticker}`);
  }
  get watchlistAddInput(): Locator {
    return this.page.getByTestId("watchlist-add-input");
  }
  get watchlistAddSubmit(): Locator {
    return this.page.getByTestId("watchlist-add-submit");
  }
  watchlistRemove(ticker: string): Locator {
    return this.page.getByTestId(`watchlist-remove-${ticker}`);
  }
  get watchlistError(): Locator {
    return this.page.getByTestId("watchlist-error");
  }

  // -- charts and tables ----------------------------------------------------
  get mainChart(): Locator {
    return this.page.getByTestId("main-chart");
  }
  get positionsTable(): Locator {
    return this.page.getByTestId("positions-table");
  }
  positionRow(ticker: string): Locator {
    return this.page.getByTestId(`position-row-${ticker}`);
  }
  get heatmap(): Locator {
    return this.page.getByTestId("portfolio-heatmap");
  }
  heatmapTile(ticker: string): Locator {
    return this.page.getByTestId(`heatmap-tile-${ticker}`);
  }
  get pnlChart(): Locator {
    return this.page.getByTestId("pnl-chart");
  }

  // -- trade bar ------------------------------------------------------------
  get tradeTicker(): Locator {
    return this.page.getByTestId("trade-ticker");
  }
  get tradeQuantity(): Locator {
    return this.page.getByTestId("trade-quantity");
  }
  get tradeBuy(): Locator {
    return this.page.getByTestId("trade-buy");
  }
  get tradeSell(): Locator {
    return this.page.getByTestId("trade-sell");
  }
  get tradeError(): Locator {
    return this.page.getByTestId("trade-error");
  }

  // -- chat -----------------------------------------------------------------
  get chatPanel(): Locator {
    return this.page.getByTestId("chat-panel");
  }
  get chatInput(): Locator {
    return this.page.getByTestId("chat-input");
  }
  get chatSend(): Locator {
    return this.page.getByTestId("chat-send");
  }
  get chatLoading(): Locator {
    return this.page.getByTestId("chat-loading");
  }
  chatMessage(index: number): Locator {
    return this.page.getByTestId(`chat-message-${index}`);
  }
  get chatMessages(): Locator {
    return this.page.locator('[data-testid^="chat-message-"]');
  }
  get actionChips(): Locator {
    return this.page.getByTestId("chat-action-chip");
  }
  /** Chips filtered by outcome - INTERFACES section 5 marks each with data-ok. */
  actionChipsWhere(ok: boolean): Locator {
    return this.page.locator(`[data-testid="chat-action-chip"][data-ok="${ok}"]`);
  }

  // -- actions --------------------------------------------------------------

  /**
   * Fill the trade bar and click buy or sell, returning the trade response so a
   * failing spec can report the server's own words rather than a UI guess.
   */
  async submitTrade(
    ticker: string,
    quantity: number,
    side: "buy" | "sell",
  ): Promise<{ status: number; body: any }> {
    await this.tradeTicker.fill(ticker);
    await this.tradeQuantity.fill(String(quantity));
    const waitFor = this.page.waitForResponse(
      (r) => r.url().includes("/api/portfolio/trade") && r.request().method() === "POST",
      { timeout: 20_000 },
    );
    await (side === "buy" ? this.tradeBuy : this.tradeSell).click();
    return describe(await waitFor);
  }

  /** Type a ticker into the watchlist add box and submit it. */
  async submitWatchlistAdd(ticker: string): Promise<{ status: number; body: any }> {
    await this.watchlistAddInput.fill(ticker);
    const waitFor = this.page.waitForResponse(
      (r) => r.url().includes("/api/watchlist") && r.request().method() === "POST",
      { timeout: 20_000 },
    );
    await this.watchlistAddSubmit.click();
    return describe(await waitFor);
  }

  /** Click the remove button for a ticker and wait for the DELETE to land. */
  async submitWatchlistRemove(ticker: string): Promise<{ status: number; body: any }> {
    const waitFor = this.page.waitForResponse(
      (r) => r.url().includes(`/api/watchlist/${ticker}`) && r.request().method() === "DELETE",
      { timeout: 20_000 },
    );
    await this.watchlistRemove(ticker).click();
    return describe(await waitFor);
  }

  /** Send a chat message and wait for the assistant turn to come back. */
  async sendChat(message: string): Promise<{ status: number; body: any }> {
    await this.chatInput.fill(message);
    const waitFor = this.page.waitForResponse(
      (r) => r.url().includes("/api/chat") && r.request().method() === "POST",
      { timeout: 45_000 },
    );
    await this.chatSend.click();
    return describe(await waitFor);
  }
}

async function describe(res: Response): Promise<{ status: number; body: any }> {
  const text = await res.text();
  try {
    return { status: res.status(), body: JSON.parse(text) };
  } catch {
    return { status: res.status(), body: text };
  }
}
