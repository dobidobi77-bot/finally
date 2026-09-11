"""Tests for MassiveDataSource (mocked)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.market.cache import PriceCache
from app.market.massive_client import (
    MassiveDataSource,
    resolve_open_price,
    resolve_price,
)


def _snapshot(ticker: str, **bars) -> SimpleNamespace:
    """A Massive TickerSnapshot lookalike. Bars not given are None, as the
    API returns them when the plan or the hour has no data for them."""
    fields = {"last_trade": None, "min": None, "day": None, "prev_day": None, "updated": None}
    fields.update({k: SimpleNamespace(**v) if isinstance(v, dict) else v for k, v in bars.items()})
    return SimpleNamespace(ticker=ticker, **fields)


def _make_snapshot(ticker: str, price: float, timestamp_ms: int) -> SimpleNamespace:
    """A snapshot from a plan with a trades entitlement."""
    return _snapshot(ticker, last_trade={"price": price, "timestamp": timestamp_ms})


@pytest.mark.asyncio
class TestMassiveDataSource:
    """Unit tests for MassiveDataSource with mocked API."""

    async def test_poll_updates_cache(self):
        """Test that polling updates the cache."""
        cache = PriceCache()
        source = MassiveDataSource(
            api_key="test-key",
            price_cache=cache,
            poll_interval=60.0,  # Long interval so the loop doesn't auto-poll
        )
        source._tickers = ["AAPL", "GOOGL"]
        source._client = MagicMock()  # Satisfy the _poll_once guard

        mock_snapshots = [
            _make_snapshot("AAPL", 190.50, 1707580800000),
            _make_snapshot("GOOGL", 175.25, 1707580800000),
        ]

        with patch.object(source, "_fetch_snapshots", return_value=mock_snapshots):
            await source._poll_once()

        assert cache.get_price("AAPL") == 190.50
        assert cache.get_price("GOOGL") == 175.25

    async def test_snapshot_with_no_price_at_all_is_skipped(self):
        """A payload with every bar empty cannot be priced; skip it, keep the rest."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)
        source._tickers = ["AAPL", "BAD"]
        source._client = MagicMock()  # Satisfy the _poll_once guard

        good_snap = _make_snapshot("AAPL", 190.50, 1707580800000)
        empty_snap = _snapshot("BAD", day={"open": 0, "close": 0}, prev_day={"close": 0})

        with patch.object(source, "_fetch_snapshots", return_value=[good_snap, empty_snap]):
            await source._poll_once()

        assert cache.get_price("AAPL") == 190.50
        assert cache.get_price("BAD") is None

    async def test_plan_without_last_trade_still_populates_cache(self):
        """Real closed-market payload from a plan with no trades entitlement:
        last_trade is None but the minute/day/prev_day bars are present."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)
        source._tickers = ["AAPL"]
        source._client = MagicMock()
        snap = _snapshot(
            "AAPL",
            last_trade=None,
            min={"close": 325.7986, "timestamp": 1789084740000},
            day={"open": 316.67, "close": 326.57},
            prev_day={"open": 315.485, "close": 315.34},
            updated=1789084800000000000,
        )

        with patch.object(source, "_fetch_snapshots", return_value=[snap]):
            await source._poll_once()

        update = cache.get("AAPL")
        assert update is not None
        assert update.price == 325.80  # PriceCache rounds to cents
        assert update.timestamp == 1789084740.0
        assert cache.get_open_price("AAPL") == 316.67
        assert len(cache) == 1

    async def test_api_error_does_not_crash(self):
        """Test that API errors don't crash the poller."""
        cache = PriceCache()
        source = MassiveDataSource(
            api_key="test-key",
            price_cache=cache,
            poll_interval=60.0,
        )
        source._tickers = ["AAPL"]
        source._client = MagicMock()  # Satisfy the _poll_once guard

        with patch.object(source, "_fetch_snapshots", side_effect=Exception("network error")):
            await source._poll_once()  # Should not raise

        assert cache.get_price("AAPL") is None  # No update happened

    async def test_timestamp_conversion(self):
        """Test that timestamps are converted from milliseconds to seconds."""
        cache = PriceCache()
        source = MassiveDataSource(
            api_key="test-key",
            price_cache=cache,
            poll_interval=60.0,
        )
        source._tickers = ["AAPL"]
        source._client = MagicMock()  # Satisfy the _poll_once guard

        mock_snapshots = [_make_snapshot("AAPL", 190.50, 1707580800000)]

        with patch.object(source, "_fetch_snapshots", return_value=mock_snapshots):
            await source._poll_once()

        update = cache.get("AAPL")
        assert update is not None
        assert update.timestamp == 1707580800.0  # Converted to seconds

    async def test_add_ticker(self):
        """Test adding a ticker."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache)

        await source.add_ticker("AAPL")
        assert "AAPL" in source.get_tickers()

    async def test_add_ticker_uppercase_normalization(self):
        """Test that tickers are normalized to uppercase."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache)

        await source.add_ticker("aapl")
        assert "AAPL" in source.get_tickers()

    async def test_add_ticker_strips_whitespace(self):
        """Test that ticker whitespace is stripped."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache)

        await source.add_ticker("  AAPL  ")
        assert "AAPL" in source.get_tickers()

    async def test_remove_ticker(self):
        """Test removing a ticker."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache)
        source._tickers = ["AAPL", "GOOGL"]
        cache.update("AAPL", 190.00)

        await source.remove_ticker("AAPL")
        assert "AAPL" not in source.get_tickers()
        assert cache.get("AAPL") is None

    async def test_get_tickers(self):
        """Test getting the list of active tickers."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache)
        source._tickers = ["AAPL", "GOOGL"]

        tickers = source.get_tickers()
        assert tickers == ["AAPL", "GOOGL"]

    async def test_empty_tickers_skips_poll(self):
        """Test that polling is skipped when there are no tickers."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache)
        source._tickers = []

        # Should not call _fetch_snapshots
        with patch.object(source, "_fetch_snapshots") as mock_fetch:
            await source._poll_once()
            mock_fetch.assert_not_called()

    async def test_stop_is_idempotent(self):
        """Test that stop() can be called multiple times."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache)

        await source.stop()
        await source.stop()  # Should not raise

    async def test_stop_cancels_task(self):
        """Test that stop() cancels the polling task."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=10.0)

        # Mock the client and start
        with patch("app.market.massive_client.RESTClient"):
            with patch.object(source, "_fetch_snapshots", return_value=[]):
                await source.start(["AAPL"])

        # Verify task is running
        assert source._task is not None
        assert not source._task.done()

        # Stop and verify task is cancelled
        await source.stop()
        assert source._task is None

    async def test_fetch_passes_the_string_market_type_to_the_library(self):
        """The library boundary. massive's SnapshotMarketType is a plain Enum,
        so passing it renders 'SnapshotMarketType.STOCKS' into the URL and
        every poll 404s. Patching _fetch_snapshots would hide that again."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)

        with patch("app.market.massive_client.RESTClient") as client_cls:
            client_cls.return_value.get_snapshot_all.return_value = [
                _make_snapshot("AAPL", 190.50, 1707580800000)
            ]
            await source.start(["AAPL", "MSFT"])
            await source.stop()

        client_cls.assert_called_once_with(api_key="test-key")
        client_cls.return_value.get_snapshot_all.assert_called_once_with(
            market_type="stocks", tickers=["AAPL", "MSFT"]
        )
        assert cache.get_price("AAPL") == 190.50

    async def test_start_immediate_poll(self):
        """Test that start() does an immediate poll before starting the loop."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)

        mock_snapshots = [_make_snapshot("AAPL", 190.50, 1707580800000)]

        with patch("app.market.massive_client.RESTClient"):
            with patch.object(source, "_fetch_snapshots", return_value=mock_snapshots):
                await source.start(["AAPL"])

        # Cache should have data immediately from the first poll
        assert cache.get_price("AAPL") == 190.50

        await source.stop()


class TestResolvePrice:
    """The fallback chain, bar by bar."""

    def test_last_trade_wins_when_present(self):
        snap = _snapshot(
            "AAPL",
            last_trade={"price": 190.5, "timestamp": 1707580800000},
            min={"close": 189.0, "timestamp": 1707580740000},
        )
        assert resolve_price(snap) == (190.5, 1707580800.0)

    def test_minute_bar_when_no_last_trade(self):
        snap = _snapshot("AAPL", min={"close": 189.0, "timestamp": 1707580740000})
        assert resolve_price(snap) == (189.0, 1707580740.0)

    def test_day_close_with_snapshot_updated_time(self):
        snap = _snapshot("AAPL", day={"open": 1.0, "close": 188.0}, updated=1707580800000000000)
        assert resolve_price(snap) == (188.0, 1707580800.0)

    def test_prev_day_close_is_the_last_resort(self):
        snap = _snapshot("AAPL", day={"open": 0, "close": 0}, prev_day={"close": 187.0})
        price, ts = resolve_price(snap)
        assert price == 187.0
        assert ts > 0  # no bar timestamp: falls back to now

    def test_nothing_usable_returns_none(self):
        assert resolve_price(_snapshot("AAPL")) is None
        assert resolve_price(_snapshot("AAPL", last_trade={"price": None})) is None
        assert resolve_price(_snapshot("AAPL", min={"close": "n/a"})) is None


class TestResolveOpenPrice:
    def test_day_open_during_or_after_the_session(self):
        snap = _snapshot("AAPL", day={"open": 316.67}, prev_day={"close": 315.34})
        assert resolve_open_price(snap) == 316.67

    def test_prior_close_before_the_first_trade_of_the_day(self):
        """Between midnight ET and the first pre-market print, day is zeros."""
        snap = _snapshot("AAPL", day={"open": 0, "close": 0}, prev_day={"close": 315.34})
        assert resolve_open_price(snap) == 315.34

    def test_no_baseline_at_all(self):
        assert resolve_open_price(_snapshot("AAPL")) is None
