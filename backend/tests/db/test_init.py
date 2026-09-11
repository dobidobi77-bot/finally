"""Schema creation and default seeding."""

from app.db import repo_portfolio, repo_seeds, repo_watchlist
from app.db.connection import get_connection
from app.db.init import DEFAULT_WATCHLIST, close_db, init_db


async def test_seeds_default_cash_balance():
    assert await repo_portfolio.get_cash() == 10000.0


async def test_seeds_default_watchlist():
    assert await repo_watchlist.list_watchlist() == list(DEFAULT_WATCHLIST)


async def test_creates_all_tables():
    conn = await get_connection()
    async with conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'") as cursor:
        names = {row["name"] for row in await cursor.fetchall()}
    assert {
        "users_profile",
        "watchlist",
        "positions",
        "trades",
        "portfolio_snapshots",
        "chat_messages",
        "ticker_seeds",
    } <= names


async def test_applies_required_pragmas():
    conn = await get_connection()
    async with conn.execute("PRAGMA journal_mode") as cursor:
        journal_mode = (await cursor.fetchone())[0]
    async with conn.execute("PRAGMA busy_timeout") as cursor:
        busy_timeout = (await cursor.fetchone())[0]
    assert journal_mode == "wal"
    assert busy_timeout == 5000


async def test_init_is_idempotent(db_path):
    """A second init must not duplicate the seed rows or reset cash."""
    await repo_portfolio.execute_trade_tx("AAPL", "buy", 1, 100.0)
    await init_db(db_path)

    assert await repo_watchlist.list_watchlist() == list(DEFAULT_WATCHLIST)
    assert await repo_portfolio.get_cash() == 9900.0


async def test_does_not_reseed_a_curated_watchlist(db_path):
    """A user who swapped the defaults for their own picks keeps them."""
    for ticker in DEFAULT_WATCHLIST:
        await repo_watchlist.remove_from_watchlist(ticker)
    await repo_watchlist.add_to_watchlist("PYPL")
    await init_db(db_path)

    assert await repo_watchlist.list_watchlist() == ["PYPL"]


async def test_does_not_reseed_an_emptied_watchlist_across_a_restart(db_path):
    """An empty watchlist stays empty after a restart.

    Regression: seeding used to be gated per-table, so an emptied watchlist was
    re-seeded on the next startup and the user's removals were silently undone.
    """
    for ticker in DEFAULT_WATCHLIST:
        await repo_watchlist.remove_from_watchlist(ticker)
    assert await repo_watchlist.list_watchlist() == []

    await close_db()
    await init_db(db_path)

    assert await repo_watchlist.list_watchlist() == []
    assert await repo_portfolio.get_cash() == 10000.0


async def test_removed_ticker_does_not_reappear_while_a_position_is_open(db_path):
    """BUILD_CONTRACT A2: tracking a held ticker must not recreate its watchlist row."""
    await repo_portfolio.execute_trade_tx("AAPL", "buy", 1, 190.0)
    await repo_watchlist.remove_from_watchlist("AAPL")

    await close_db()
    await init_db(db_path)

    assert "AAPL" not in await repo_watchlist.list_watchlist()
    assert (await repo_portfolio.get_position("AAPL")).quantity == 1


async def test_restart_preserves_persisted_ticker_seeds(db_path):
    """A3 depends on a stored seed surviving every later init_db."""
    await repo_seeds.upsert_ticker_seed("PYPL", 137.5, 0.05, 0.25)

    await close_db()
    await init_db(db_path)

    seed = await repo_seeds.get_ticker_seed("PYPL")
    assert (seed.seed_price, seed.drift, seed.volatility) == (137.5, 0.05, 0.25)
