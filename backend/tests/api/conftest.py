"""Fixtures for service and route tests: temp database, fake feed, no lifespan."""

import httpx
import pytest

from app import state
from app.db.init import close_db, init_db
from app.main import create_app
from app.market.interface import MarketDataSource


class FakeMarketSource(MarketDataSource):
    """Records tracking calls and prices new tickers instantly."""

    def __init__(self, price_cache, seed_price: float | None = 100.0) -> None:
        self._cache = price_cache
        self._seed_price = seed_price
        self.tickers: list[str] = []
        self.added: list[str] = []
        self.removed: list[str] = []

    async def start(self, tickers: list[str]) -> None:
        for ticker in tickers:
            await self.add_ticker(ticker)

    async def stop(self) -> None:
        pass

    async def add_ticker(self, ticker: str) -> None:
        self.added.append(ticker)
        if ticker not in self.tickers:
            self.tickers.append(ticker)
        if self._seed_price is not None:
            self._cache.update(ticker, self._seed_price)

    async def remove_ticker(self, ticker: str) -> None:
        self.removed.append(ticker)
        self.tickers = [t for t in self.tickers if t != ticker]
        self._cache.remove(ticker)

    def get_tickers(self) -> list[str]:
        return list(self.tickers)


@pytest.fixture
async def db(tmp_path):
    """A fresh temporary database, seeded with the defaults."""
    await init_db(str(tmp_path / "finally.db"))
    yield
    await close_db()


@pytest.fixture
def clean_state():
    state.reset()
    yield
    state.reset()


@pytest.fixture
def market(clean_state):
    """A fake feed wired into app state, with no prices cached yet."""
    source = FakeMarketSource(state.price_cache)
    state.set_market_source(source)
    return source


@pytest.fixture
def prices(market):
    """Live prices for the default watchlist."""
    for ticker, price in {"AAPL": 190.0, "GOOGL": 175.0, "MSFT": 420.0}.items():
        state.price_cache.update(ticker, price)
    return state.price_cache


@pytest.fixture
async def client(db, market):
    """HTTP client over the real app. Lifespan is not run — the fixtures above
    do that job with a temp database and a fake feed."""
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
