"""Watchlist add, remove and ordering."""

from app.db import repo_watchlist
from app.db.init import DEFAULT_WATCHLIST


async def test_add_returns_true_and_appends_to_the_end():
    assert await repo_watchlist.add_to_watchlist("PYPL") is True
    assert await repo_watchlist.list_watchlist() == [*DEFAULT_WATCHLIST, "PYPL"]


async def test_duplicate_add_returns_false_without_raising():
    assert await repo_watchlist.add_to_watchlist("AAPL") is False
    assert (await repo_watchlist.list_watchlist()).count("AAPL") == 1


async def test_remove_returns_true_and_drops_the_ticker():
    assert await repo_watchlist.remove_from_watchlist("AAPL") is True
    assert "AAPL" not in await repo_watchlist.list_watchlist()


async def test_removing_an_unwatched_ticker_returns_false():
    assert await repo_watchlist.remove_from_watchlist("PYPL") is False


async def test_watchlists_are_isolated_per_user():
    await repo_watchlist.add_to_watchlist("PYPL", user_id="other")

    assert await repo_watchlist.list_watchlist(user_id="other") == ["PYPL"]
    assert "PYPL" not in await repo_watchlist.list_watchlist()
