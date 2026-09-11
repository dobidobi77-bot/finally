"""SSE contract (BUILD_CONTRACT A5) and the module-level-router regression."""

import asyncio
import json

import pytest
from fastapi import APIRouter

from app import state
from app.market import stream
from app.market.cache import PriceCache
from app.market.stream import _generate_events, create_stream_router


class FakeRequest:
    """Minimal stand-in for starlette's Request: connection state only."""

    def __init__(self, disconnect_after: int = 999) -> None:
        self.client = None
        self._checks = 0
        self._disconnect_after = disconnect_after

    async def is_disconnected(self) -> bool:
        self._checks += 1
        return self._checks > self._disconnect_after


async def drain(generator, limit: int = 50) -> list[str]:
    """Collect chunks until the generator finishes or `limit` is reached."""
    chunks = []
    async for chunk in generator:
        chunks.append(chunk)
        if len(chunks) >= limit:
            break
    return chunks


@pytest.fixture(autouse=True)
def clean_state():
    state.reset()
    yield
    state.reset()


class TestRouterFactory:
    """Regression: `router` was created at module scope, so a second
    create_stream_router() call added a duplicate route to the same router and
    kept serving the first cache."""

    def test_module_has_no_shared_router(self):
        assert not hasattr(stream, "router")

    def test_each_call_returns_a_distinct_router(self):
        first = create_stream_router(PriceCache())
        second = create_stream_router(PriceCache())
        assert first is not second

    def test_second_call_does_not_double_register_the_route(self):
        create_stream_router(PriceCache())
        second = create_stream_router(PriceCache())
        paths = [r.path for r in second.routes]
        assert paths == ["/api/stream/prices"]

    def test_returns_an_api_router(self):
        assert isinstance(create_stream_router(PriceCache()), APIRouter)


class TestGenerator:
    async def test_first_chunk_is_the_retry_directive(self):
        cache = PriceCache()
        chunks = await drain(_generate_events(cache, FakeRequest(disconnect_after=0), interval=0.01))
        assert chunks[0] == "retry: 1000\n\n"

    async def test_exits_cleanly_on_client_disconnect(self):
        """BUILD_CONTRACT C7 — the part of reconnection this project owns."""
        cache = PriceCache()
        cache.update("AAPL", 190.0)
        request = FakeRequest(disconnect_after=1)

        chunks = await asyncio.wait_for(
            drain(_generate_events(cache, request, interval=0.01)), timeout=2.0
        )

        assert chunks[0] == "retry: 1000\n\n"
        assert state.sse_client_count() == 0

    async def test_emits_one_event_keyed_by_ticker(self):
        cache = PriceCache()
        cache.update("AAPL", 190.0)
        cache.update("MSFT", 420.0)

        chunks = await drain(_generate_events(cache, FakeRequest(disconnect_after=1), interval=0.01))

        data = json.loads(chunks[1].removeprefix("data: ").strip())
        assert set(data) == {"AAPL", "MSFT"}
        assert data["AAPL"]["price"] == 190.0
        assert data["AAPL"]["open_price"] == 190.0

    async def test_does_not_re_emit_without_a_version_change(self):
        cache = PriceCache()
        cache.update("AAPL", 190.0)

        chunks = await drain(_generate_events(cache, FakeRequest(disconnect_after=4), interval=0.01))

        assert len([c for c in chunks if c.startswith("data: ")]) == 1

    async def test_removal_is_pushed_to_the_client(self):
        """Ties the cache defect to its user-visible symptom."""
        cache = PriceCache()
        cache.update("AAPL", 190.0)
        cache.update("MSFT", 420.0)
        request = FakeRequest(disconnect_after=6)

        generator = _generate_events(cache, request, interval=0.01)
        chunks = [await generator.__anext__(), await generator.__anext__()]
        cache.remove("MSFT")
        chunks.extend(await drain(generator))

        events = [json.loads(c.removeprefix("data: ").strip()) for c in chunks if c.startswith("data: ")]
        assert set(events[0]) == {"AAPL", "MSFT"}
        assert set(events[-1]) == {"AAPL"}

    async def test_keepalive_comment_during_a_quiet_period(self, monkeypatch):
        monkeypatch.setattr(stream, "KEEPALIVE_INTERVAL", 0.02)
        cache = PriceCache()
        cache.update("AAPL", 190.0)

        chunks = await drain(
            _generate_events(cache, FakeRequest(disconnect_after=8), interval=0.01)
        )

        assert ": keepalive\n\n" in chunks

    async def test_client_count_tracks_the_connection(self):
        cache = PriceCache()
        request = FakeRequest(disconnect_after=3)
        generator = _generate_events(cache, request, interval=0.01)

        await generator.__anext__()
        assert state.sse_client_count() == 1

        await drain(generator)
        assert state.sse_client_count() == 0
