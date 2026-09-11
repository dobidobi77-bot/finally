"""Cache regressions: removal versioning (defect 1) and open_price (A1)."""

from app.market.cache import PriceCache


class TestRemoveBumpsVersion:
    """Regression: remove() used to pop the key without bumping _version, so
    the SSE generator never noticed and stale rows lingered in open tabs."""

    def test_remove_bumps_version(self):
        cache = PriceCache()
        cache.update("AAPL", 190.0)
        before = cache.version

        cache.remove("AAPL")

        assert cache.version > before
        assert "AAPL" not in cache

    def test_remove_unknown_ticker_does_not_bump_version(self):
        cache = PriceCache()
        cache.update("AAPL", 190.0)
        before = cache.version

        cache.remove("MSFT")

        assert cache.version == before


class TestOpenPrice:
    def test_first_update_seeds_open_price(self):
        cache = PriceCache()
        update = cache.update("AAPL", 190.0)
        assert update.open_price == 190.0

    def test_open_price_survives_later_updates(self):
        cache = PriceCache()
        cache.update("AAPL", 190.0)
        cache.update("AAPL", 195.0)
        assert cache.get("AAPL").open_price == 190.0
        assert cache.get_open_price("AAPL") == 190.0

    def test_set_open_price_overrides_and_rewrites_current(self):
        cache = PriceCache()
        cache.update("AAPL", 190.0)
        before = cache.version

        cache.set_open_price("AAPL", 185.0)

        assert cache.get("AAPL").open_price == 185.0
        assert cache.get("AAPL").price == 190.0
        assert cache.version > before

    def test_set_open_price_is_idempotent(self):
        cache = PriceCache()
        cache.update("AAPL", 190.0)
        cache.set_open_price("AAPL", 185.0)
        before = cache.version

        cache.set_open_price("AAPL", 185.0)

        assert cache.version == before

    def test_removal_clears_open_price(self):
        cache = PriceCache()
        cache.update("AAPL", 190.0)
        cache.remove("AAPL")
        assert cache.get_open_price("AAPL") is None

        cache.update("AAPL", 250.0)
        assert cache.get_open_price("AAPL") == 250.0

    def test_to_dict_includes_open_price(self):
        cache = PriceCache()
        cache.update("AAPL", 190.0)
        cache.update("AAPL", 191.0)
        assert cache.get("AAPL").to_dict()["open_price"] == 190.0
