"""Persisted ticker seeds (BUILD_CONTRACT A3)."""

from app.db import repo_seeds
from app.db.connection import close_connection, get_connection


async def test_unknown_ticker_has_no_seed():
    assert await repo_seeds.get_ticker_seed("PYPL") is None


async def test_upsert_stores_and_returns_the_seed():
    seed = await repo_seeds.upsert_ticker_seed("PYPL", 100.0, 0.05, 0.25)

    assert seed.ticker == "PYPL"
    assert seed.seed_price == 100.0
    assert await repo_seeds.get_ticker_seed("PYPL") == seed


async def test_upsert_is_idempotent():
    await repo_seeds.upsert_ticker_seed("PYPL", 100.0, 0.05, 0.25)
    await repo_seeds.upsert_ticker_seed("PYPL", 100.0, 0.05, 0.25)

    conn = await get_connection()
    async with conn.execute(
        "SELECT COUNT(*) AS n FROM ticker_seeds WHERE ticker = ?", ("PYPL",)
    ) as cursor:
        assert (await cursor.fetchone())["n"] == 1


async def test_upsert_overwrites_the_stored_parameters():
    await repo_seeds.upsert_ticker_seed("PYPL", 100.0, 0.05, 0.25)
    await repo_seeds.upsert_ticker_seed("PYPL", 120.0, 0.06, 0.30)

    seed = await repo_seeds.get_ticker_seed("PYPL")
    assert (seed.seed_price, seed.drift, seed.volatility) == (120.0, 0.06, 0.30)


async def test_seed_survives_a_reconnect():
    """The point of persisting: the same ticker is not repriced on restart."""
    await repo_seeds.upsert_ticker_seed("PYPL", 137.5, 0.05, 0.25)

    await close_connection()

    assert (await repo_seeds.get_ticker_seed("PYPL")).seed_price == 137.5
