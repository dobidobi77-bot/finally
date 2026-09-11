"""Persisted seed prices for unseeded tickers (BUILD_CONTRACT A3)."""

import pytest

from app.db import repo_seeds
from app.db.init import close_db, init_db
from app.market.seed_prices import DEFAULT_SEED_PRICE, SEED_PRICES
from app.market.seed_resolver import builtin_seed, resolve_seed, resolve_seeds
from app.market.simulator import GBMSimulator


@pytest.fixture
async def db(tmp_path):
    await init_db(str(tmp_path / "finally.db"))
    yield
    await close_db()


class TestBuiltinSeed:
    def test_known_ticker(self):
        seed = builtin_seed("AAPL")
        assert seed["seed_price"] == SEED_PRICES["AAPL"]
        assert seed["sigma"] == 0.22

    def test_unknown_ticker_returns_none(self):
        assert builtin_seed("PYPL") is None


class TestResolveSeed:
    async def test_known_ticker_skips_the_database(self, db):
        seed = await resolve_seed("MSFT")
        assert seed["seed_price"] == 420.00
        assert await repo_seeds.get_ticker_seed("MSFT") is None

    async def test_unknown_ticker_is_persisted_at_the_default_price(self, db):
        seed = await resolve_seed("PYPL")

        assert seed["seed_price"] == DEFAULT_SEED_PRICE
        stored = await repo_seeds.get_ticker_seed("PYPL")
        assert stored is not None
        assert stored.seed_price == DEFAULT_SEED_PRICE

    async def test_a_stored_seed_wins_so_a_restart_reprices_identically(self, db):
        """The defect this replaces: random.uniform(50, 300) per process gave a
        held position a different valuation on every restart."""
        await repo_seeds.upsert_ticker_seed("PYPL", 62.5, 0.07, 0.33)

        seed = await resolve_seed("PYPL")

        assert seed == {"seed_price": 62.5, "mu": 0.07, "sigma": 0.33}

    async def test_second_resolution_returns_the_same_price(self, db):
        first = await resolve_seed("SNAP")
        second = await resolve_seed("SNAP")
        assert first == second

    async def test_falls_back_to_the_default_when_the_database_is_unavailable(
        self, db, monkeypatch
    ):
        """A seed lookup failure must not stop the simulator from running."""

        async def boom(_ticker):
            raise RuntimeError("database is gone")

        monkeypatch.setattr(repo_seeds, "get_ticker_seed", boom)

        seed = await resolve_seed("ZZZ")

        assert seed["seed_price"] == DEFAULT_SEED_PRICE

    async def test_resolve_seeds_batch(self, db):
        seeds = await resolve_seeds(["AAPL", "PYPL"])
        assert seeds["AAPL"]["seed_price"] == SEED_PRICES["AAPL"]
        assert seeds["PYPL"]["seed_price"] == DEFAULT_SEED_PRICE


class TestSimulatorUsesSeeds:
    def test_unseeded_ticker_is_deterministic_not_random(self):
        first = GBMSimulator(tickers=["PYPL"])
        second = GBMSimulator(tickers=["PYPL"])
        assert first.get_price("PYPL") == second.get_price("PYPL") == DEFAULT_SEED_PRICE

    def test_a_resolved_seed_overrides_the_default(self):
        sim = GBMSimulator(
            tickers=["PYPL"],
            seeds={"PYPL": {"seed_price": 62.5, "mu": 0.07, "sigma": 0.33}},
        )
        assert sim.get_price("PYPL") == 62.5

    def test_add_ticker_accepts_a_seed(self):
        sim = GBMSimulator(tickers=["AAPL"])
        sim.add_ticker("PYPL", seed={"seed_price": 62.5, "mu": 0.07, "sigma": 0.33})
        assert sim.get_price("PYPL") == 62.5
