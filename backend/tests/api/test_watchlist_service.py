"""Watchlist mutations, the tracked-ticker set (A2), and seed persistence (A3)."""

import pytest

from app import state
from app.db import repo_seeds, repo_watchlist
from app.market.seed_prices import DEFAULT_SEED_PRICE
from app.services import portfolio_service, watchlist_service
from app.services.errors import ServiceError

DEFAULT_TICKERS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]


class TestGetWatchlist:
    async def test_seeded_watchlist_in_added_at_order(self, db, market):
        result = await watchlist_service.get_watchlist()
        assert [row["ticker"] for row in result["tickers"]] == DEFAULT_TICKERS

    async def test_a_priced_ticker_carries_the_full_payload(self, db, prices):
        state.price_cache.update("AAPL", 195.0)

        rows = (await watchlist_service.get_watchlist())["tickers"]
        aapl = next(r for r in rows if r["ticker"] == "AAPL")

        assert aapl["price"] == 195.0
        assert aapl["previous_price"] == 190.0
        assert aapl["open_price"] == 190.0
        assert aapl["direction"] == "up"
        assert aapl["change"] == 5.0

    async def test_an_unticked_ticker_reports_null_price(self, db, market):
        rows = (await watchlist_service.get_watchlist())["tickers"]
        assert rows[0]["price"] is None
        assert rows[0]["direction"] == "flat"


class TestAddTicker:
    async def test_adds_and_tracks(self, db, market):
        result = await watchlist_service.add_ticker("PYPL")

        assert result == {"ok": True, "ticker": "PYPL"}
        assert "PYPL" in await repo_watchlist.list_watchlist()
        assert "PYPL" in market.added

    async def test_lowercase_input_is_normalised(self, db, market):
        result = await watchlist_service.add_ticker("  pypl  ")
        assert result["ticker"] == "PYPL"

    async def test_an_unknown_symbol_gets_a_persisted_seed(self, db, market):
        await watchlist_service.add_ticker("PYPL")

        seed = await repo_seeds.get_ticker_seed("PYPL")
        assert seed is not None
        assert seed.seed_price == DEFAULT_SEED_PRICE

    async def test_a_known_symbol_is_not_given_a_seed_row(self, db, market):
        await watchlist_service.add_ticker("AAPL")
        assert await repo_seeds.get_ticker_seed("AAPL") is None

    async def test_adding_twice_is_not_an_error(self, db, market):
        await watchlist_service.add_ticker("PYPL")
        result = await watchlist_service.add_ticker("PYPL")

        assert result["ok"] is True
        tickers = await repo_watchlist.list_watchlist()
        assert tickers.count("PYPL") == 1

    @pytest.mark.parametrize("ticker", ["", "TOOLONG", "PY PL", "123", "PY-PL", None])
    async def test_bad_symbols_are_rejected(self, db, market, ticker):
        with pytest.raises(ServiceError, match="Invalid ticker format"):
            await watchlist_service.add_ticker(ticker)


class TestRemoveTicker:
    async def test_removes_and_stops_tracking(self, db, prices):
        await watchlist_service.remove_ticker("AAPL")

        assert "AAPL" not in await repo_watchlist.list_watchlist()
        assert "AAPL" in state.get_market_source().removed

    async def test_an_open_position_keeps_the_price_feed(self, db, prices):
        """BUILD_CONTRACT A2 - otherwise the position could not be valued."""
        await portfolio_service.execute_trade("AAPL", "buy", 1)

        await watchlist_service.remove_ticker("AAPL")

        assert "AAPL" not in await repo_watchlist.list_watchlist()
        assert "AAPL" not in state.get_market_source().removed
        assert state.price_cache.get_price("AAPL") == 190.0

    async def test_tracking_stops_once_the_position_is_closed(self, db, prices):
        await portfolio_service.execute_trade("AAPL", "buy", 1)
        await portfolio_service.execute_trade("AAPL", "sell", 1)

        await watchlist_service.remove_ticker("AAPL")

        assert "AAPL" in state.get_market_source().removed

    async def test_removing_an_absent_ticker_is_not_an_error(self, db, market):
        assert await watchlist_service.remove_ticker("PYPL") == {"ok": True}

    async def test_bad_symbol_is_rejected(self, db, market):
        with pytest.raises(ServiceError, match="Invalid ticker format"):
            await watchlist_service.remove_ticker("TOOLONG")


class TestTrackedTickers:
    async def test_defaults_to_the_watchlist(self, db, market):
        assert await watchlist_service.tracked_tickers() == DEFAULT_TICKERS

    async def test_includes_held_tickers_off_the_watchlist(self, db, prices):
        await portfolio_service.execute_trade("AAPL", "buy", 1)
        await watchlist_service.remove_ticker("AAPL")

        tracked = await watchlist_service.tracked_tickers()

        assert "AAPL" in tracked
        assert tracked.count("AAPL") == 1

    async def test_no_duplicates_for_a_held_watchlist_ticker(self, db, prices):
        await portfolio_service.execute_trade("AAPL", "buy", 1)

        tracked = await watchlist_service.tracked_tickers()

        assert tracked.count("AAPL") == 1
