"""Trade execution, P&L math, and validation edges (BUILD_CONTRACT B1, B3, A4)."""

import pytest

from app import state
from app.db import repo_portfolio
from app.services import portfolio_service
from app.services.errors import ServiceError
from tests.api.conftest import FakeMarketSource


class TestGetPortfolio:
    async def test_empty_portfolio_is_all_cash(self, db, prices):
        portfolio = await portfolio_service.get_portfolio()
        assert portfolio == {
            "cash": 10000.0,
            "positions": [],
            "total_value": 10000.0,
            "unrealized_pnl": 0.0,
        }

    async def test_position_is_valued_at_the_live_price(self, db, prices):
        await portfolio_service.execute_trade("AAPL", "buy", 10)
        state.price_cache.update("AAPL", 200.0)

        portfolio = await portfolio_service.get_portfolio()
        position = portfolio["positions"][0]

        assert position["avg_cost"] == 190.0
        assert position["current_price"] == 200.0
        assert position["unrealized_pnl"] == 100.0  # (200 - 190) * 10
        assert position["pnl_percent"] == pytest.approx(5.26, abs=0.01)
        assert portfolio["cash"] == 8100.0  # 10000 - 1900
        assert portfolio["total_value"] == 10100.0  # 8100 + 2000

    async def test_a_loss_is_reported_negative(self, db, prices):
        await portfolio_service.execute_trade("AAPL", "buy", 10)
        state.price_cache.update("AAPL", 180.0)

        portfolio = await portfolio_service.get_portfolio()

        assert portfolio["positions"][0]["unrealized_pnl"] == -100.0
        assert portfolio["unrealized_pnl"] == -100.0

    async def test_falls_back_to_cost_when_the_cache_is_empty(self, db, prices):
        await portfolio_service.execute_trade("AAPL", "buy", 10)
        state.price_cache.remove("AAPL")

        portfolio = await portfolio_service.get_portfolio()

        assert portfolio["positions"][0]["current_price"] == 190.0
        assert portfolio["positions"][0]["unrealized_pnl"] == 0.0
        assert portfolio["total_value"] == 10000.0


class TestExecuteTrade:
    async def test_buy_fills_at_the_cached_price(self, db, prices):
        result = await portfolio_service.execute_trade("AAPL", "buy", 10)

        assert result["ok"] is True
        assert result["trade"]["price"] == 190.0
        assert result["trade"]["side"] == "buy"
        assert result["trade"]["quantity"] == 10.0
        assert result["portfolio"]["cash"] == 8100.0

    async def test_sell_returns_cash_and_leaves_avg_cost_alone(self, db, prices):
        await portfolio_service.execute_trade("AAPL", "buy", 10)
        state.price_cache.update("AAPL", 200.0)

        await portfolio_service.execute_trade("AAPL", "sell", 4)

        position = await repo_portfolio.get_position("AAPL")
        assert position.quantity == 6.0
        assert position.avg_cost == 190.0  # BUILD_CONTRACT B1
        assert (await repo_portfolio.get_cash()) == 8900.0  # 8100 + 4*200

    async def test_selling_the_whole_position_removes_it(self, db, prices):
        await portfolio_service.execute_trade("AAPL", "buy", 10)
        await portfolio_service.execute_trade("AAPL", "sell", 10)

        assert await repo_portfolio.get_position("AAPL") is None

    async def test_averaging_up_recomputes_avg_cost(self, db, prices):
        await portfolio_service.execute_trade("AAPL", "buy", 10)
        state.price_cache.update("AAPL", 210.0)
        await portfolio_service.execute_trade("AAPL", "buy", 10)

        position = await repo_portfolio.get_position("AAPL")
        assert position.quantity == 20.0
        assert position.avg_cost == 200.0  # (1900 + 2100) / 20

    async def test_fractional_quantities_are_supported(self, db, prices):
        result = await portfolio_service.execute_trade("AAPL", "buy", 0.5)
        assert result["trade"]["quantity"] == 0.5
        assert result["portfolio"]["cash"] == 9905.0

    async def test_ticker_is_uppercased(self, db, prices):
        result = await portfolio_service.execute_trade("aapl", "buy", 1)
        assert result["trade"]["ticker"] == "AAPL"

    async def test_a_trade_records_a_snapshot(self, db, prices):
        await portfolio_service.execute_trade("AAPL", "buy", 10)

        history = await portfolio_service.get_history()
        assert len(history["snapshots"]) == 1
        assert history["snapshots"][0]["total_value"] == 10000.0


class TestValidation:
    @pytest.mark.parametrize("quantity", [0, 0.0, -5, -0.001])
    async def test_non_positive_quantity_is_rejected(self, db, prices, quantity):
        with pytest.raises(ServiceError, match="Quantity"):
            await portfolio_service.execute_trade("AAPL", "buy", quantity)

    @pytest.mark.parametrize("quantity", ["abc", None, [1], {}, float("nan"), float("inf")])
    async def test_non_numeric_quantity_is_rejected(self, db, prices, quantity):
        with pytest.raises(ServiceError, match="Quantity must be a positive number"):
            await portfolio_service.execute_trade("AAPL", "buy", quantity)

    async def test_numeric_string_quantity_is_accepted(self, db, prices):
        result = await portfolio_service.execute_trade("AAPL", "buy", "2")
        assert result["trade"]["quantity"] == 2.0

    @pytest.mark.parametrize("ticker", ["", "TOOLONG", "AA PL", "123", "aa-pl", None, 7])
    async def test_bad_ticker_is_rejected(self, db, prices, ticker):
        with pytest.raises(ServiceError, match="Invalid ticker format"):
            await portfolio_service.execute_trade(ticker, "buy", 1)

    @pytest.mark.parametrize("side", ["hold", "", "BUYY", None])
    async def test_bad_side_is_rejected(self, db, prices, side):
        with pytest.raises(ServiceError, match="Side must be"):
            await portfolio_service.execute_trade("AAPL", side, 1)

    async def test_side_is_case_insensitive(self, db, prices):
        result = await portfolio_service.execute_trade("AAPL", "BUY", 1)
        assert result["trade"]["side"] == "buy"

    async def test_insufficient_cash_is_rejected(self, db, prices):
        with pytest.raises(ServiceError):
            await portfolio_service.execute_trade("AAPL", "buy", 1000)

        assert (await repo_portfolio.get_cash()) == 10000.0

    async def test_overselling_is_rejected(self, db, prices):
        await portfolio_service.execute_trade("AAPL", "buy", 5)

        with pytest.raises(ServiceError):
            await portfolio_service.execute_trade("AAPL", "sell", 6)

        assert (await repo_portfolio.get_position("AAPL")).quantity == 5.0

    async def test_selling_an_unheld_ticker_is_rejected(self, db, prices):
        with pytest.raises(ServiceError):
            await portfolio_service.execute_trade("MSFT", "sell", 1)


class TestUntrackedTicker:
    """BUILD_CONTRACT A4 - never fill at zero."""

    async def test_an_untracked_ticker_is_added_then_filled(self, db, market):
        result = await portfolio_service.execute_trade("PYPL", "buy", 1)

        assert "PYPL" in market.added
        assert result["trade"]["price"] == 100.0

    async def test_no_price_after_the_timeout_is_rejected(self, db, clean_state, monkeypatch):
        monkeypatch.setattr(portfolio_service, "FIRST_PRICE_TIMEOUT", 0.05)
        state.set_market_source(FakeMarketSource(state.price_cache, seed_price=None))

        with pytest.raises(ServiceError, match="No price available for PYPL"):
            await portfolio_service.execute_trade("PYPL", "buy", 1)

    async def test_no_market_source_is_rejected(self, db, clean_state):
        with pytest.raises(ServiceError, match="No price available"):
            await portfolio_service.execute_trade("PYPL", "buy", 1)


class TestSnapshots:
    async def test_history_is_empty_before_any_snapshot(self, db, prices):
        assert await portfolio_service.get_history() == {"snapshots": []}

    async def test_snapshot_now_records_total_value(self, db, prices):
        await portfolio_service.snapshot_now()

        snapshots = (await portfolio_service.get_history())["snapshots"]
        assert len(snapshots) == 1
        assert snapshots[0]["total_value"] == 10000.0
        assert snapshots[0]["recorded_at"]
