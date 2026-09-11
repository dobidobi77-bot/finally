"""Startup and shutdown wiring, and the snapshot gate (BUILD_CONTRACT B4)."""

import asyncio

import pytest

from app import main, state
from app.db.init import close_db
from app.main import create_app, lifespan


@pytest.fixture
def env(tmp_path, monkeypatch, clean_state):
    """A temp database and no Massive key, so the simulator is selected."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "finally.db"))
    monkeypatch.setenv("MASSIVE_API_KEY", "")
    yield


class TestLifespan:
    async def test_startup_seeds_the_cache_and_shutdown_clears_the_source(self, env):
        app = create_app()

        async with lifespan(app):
            assert state.market_source is not None
            assert len(state.price_cache) == 10
            assert state.price_cache.get_price("AAPL") == 190.0
            assert state.price_cache.get_open_price("AAPL") == 190.0

        assert state.market_source is None
        await close_db()

    async def test_startup_tracks_a_held_ticker_off_the_watchlist(self, env):
        from app.db import repo_portfolio, repo_watchlist
        from app.db.init import init_db

        await init_db()
        await repo_portfolio.execute_trade_tx("PYPL", "buy", 1, 100.0)
        await repo_watchlist.remove_from_watchlist("AAPL")

        app = create_app()
        async with lifespan(app):
            assert "PYPL" in state.get_market_source().get_tickers()
            assert "AAPL" not in state.get_market_source().get_tickers()

        await close_db()

    async def test_the_snapshot_task_is_cancelled_on_shutdown(self, env):
        app = create_app()

        async with lifespan(app):
            tasks = [t for t in asyncio.all_tasks() if t.get_name() == "portfolio-snapshots"]
            assert len(tasks) == 1

        await asyncio.sleep(0)
        assert all(t.done() for t in tasks)
        await close_db()


class TestSnapshotGate:
    """Snapshotting an idle app would fill the table with rows for nobody."""

    @pytest.fixture
    def recorder(self, monkeypatch):
        from app.services import portfolio_service

        calls = []

        async def snapshot_now():
            calls.append(1)

        monkeypatch.setattr(portfolio_service, "snapshot_now", snapshot_now)
        monkeypatch.setattr(main, "SNAPSHOT_INTERVAL", 0.01)
        return calls

    async def test_skipped_with_no_sse_clients(self, clean_state, recorder):
        task = asyncio.create_task(main._snapshot_loop())
        await asyncio.sleep(0.05)
        task.cancel()

        assert recorder == []

    async def test_runs_while_a_client_is_connected(self, clean_state, recorder):
        state.sse_client_connected()

        task = asyncio.create_task(main._snapshot_loop())
        await asyncio.sleep(0.05)
        task.cancel()

        assert len(recorder) > 0

    async def test_a_snapshot_failure_does_not_kill_the_loop(self, clean_state, monkeypatch):
        from app.services import portfolio_service

        calls = []

        async def boom():
            calls.append(1)
            raise RuntimeError("database is gone")

        monkeypatch.setattr(portfolio_service, "snapshot_now", boom)
        monkeypatch.setattr(main, "SNAPSHOT_INTERVAL", 0.01)
        state.sse_client_connected()

        task = asyncio.create_task(main._snapshot_loop())
        await asyncio.sleep(0.05)
        still_running = not task.done()
        task.cancel()

        assert len(calls) > 1
        assert still_running
