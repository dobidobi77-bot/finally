"""HTTP contract: status codes and response shapes (BUILD_CONTRACT section 4)."""

import pytest

from app import state


class TestHealth:
    async def test_reports_the_simulator_and_an_empty_cache(self, client, monkeypatch):
        monkeypatch.delenv("MASSIVE_API_KEY", raising=False)

        response = await client.get("/api/health")

        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "market_source": "simulator",
            "cache_ready": False,
        }

    async def test_cache_ready_once_a_price_arrives(self, client):
        state.price_cache.update("AAPL", 190.0)

        assert (await client.get("/api/health")).json()["cache_ready"] is True

    async def test_reports_massive_when_a_key_is_set(self, client, monkeypatch):
        monkeypatch.setenv("MASSIVE_API_KEY", "abc123")

        assert (await client.get("/api/health")).json()["market_source"] == "massive"


class TestPortfolioRoutes:
    async def test_get_portfolio_shape(self, client):
        response = await client.get("/api/portfolio")

        assert response.status_code == 200
        assert set(response.json()) == {"cash", "positions", "total_value", "unrealized_pnl"}

    async def test_buy_returns_ok_trade_and_portfolio(self, client, prices):
        response = await client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "buy"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert set(body["trade"]) == {
            "id",
            "ticker",
            "side",
            "quantity",
            "price",
            "executed_at",
        }
        assert body["portfolio"]["cash"] == 8100.0

    async def test_position_shape(self, client, prices):
        await client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1, "side": "buy"}
        )

        position = (await client.get("/api/portfolio")).json()["positions"][0]

        assert set(position) == {
            "ticker",
            "quantity",
            "avg_cost",
            "current_price",
            "unrealized_pnl",
            "pnl_percent",
        }

    @pytest.mark.parametrize(
        ("body", "message"),
        [
            ({"ticker": "AAPL", "quantity": 0, "side": "buy"}, "Quantity"),
            ({"ticker": "AAPL", "quantity": -1, "side": "buy"}, "Quantity"),
            ({"ticker": "AAPL", "quantity": "abc", "side": "buy"}, "Quantity"),
            ({"ticker": "AAPL", "side": "buy"}, "Quantity"),
            ({"ticker": "TOOLONG", "quantity": 1, "side": "buy"}, "Invalid ticker format"),
            ({"ticker": "AAPL", "quantity": 1, "side": "hold"}, "Side must be"),
            ({"ticker": "AAPL", "quantity": 99999, "side": "buy"}, ""),
        ],
    )
    async def test_bad_trades_are_400_with_an_error_body(self, client, prices, body, message):
        response = await client.post("/api/portfolio/trade", json=body)

        assert response.status_code == 400
        assert set(response.json()) == {"error"}
        assert message in response.json()["error"]

    @pytest.mark.parametrize(
        "raw",
        [
            b'["AAPL", 1, "buy"]',  # a JSON array, not an object
            b'{"ticker": "AAPL", "quantity": 1, "side": "buy"',  # truncated JSON
        ],
    )
    async def test_bodies_pydantic_rejects_are_also_400_with_an_error_body(self, client, raw):
        """FastAPI would answer 422 {"detail": [...]}; the contract wants one shape."""
        response = await client.post(
            "/api/portfolio/trade", content=raw, headers={"content-type": "application/json"}
        )

        assert response.status_code == 400
        assert set(response.json()) == {"error"}
        assert response.json()["error"].startswith("Invalid ")

    async def test_history_shape(self, client, prices):
        await client.post(
            "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1, "side": "buy"}
        )

        response = await client.get("/api/portfolio/history")

        assert response.status_code == 200
        snapshots = response.json()["snapshots"]
        assert len(snapshots) == 1
        assert set(snapshots[0]) == {"total_value", "recorded_at"}


class TestWatchlistRoutes:
    async def test_get_returns_the_seeded_tickers(self, client):
        response = await client.get("/api/watchlist")

        assert response.status_code == 200
        assert len(response.json()["tickers"]) == 10

    async def test_priced_row_carries_open_price(self, client, prices):
        rows = (await client.get("/api/watchlist")).json()["tickers"]
        aapl = next(r for r in rows if r["ticker"] == "AAPL")

        assert aapl["open_price"] == 190.0

    async def test_post_adds_a_ticker(self, client):
        response = await client.post("/api/watchlist", json={"ticker": "PYPL"})

        assert response.status_code == 200
        assert response.json() == {"ok": True, "ticker": "PYPL"}

        tickers = [r["ticker"] for r in (await client.get("/api/watchlist")).json()["tickers"]]
        assert "PYPL" in tickers

    @pytest.mark.parametrize("ticker", ["", "TOOLONG", "PY PL", "123"])
    async def test_post_rejects_a_bad_symbol(self, client, ticker):
        response = await client.post("/api/watchlist", json={"ticker": ticker})

        assert response.status_code == 400
        assert response.json() == {"error": "Invalid ticker format"}

    async def test_delete_removes_a_ticker(self, client):
        response = await client.delete("/api/watchlist/AAPL")

        assert response.status_code == 200
        assert response.json() == {"ok": True}

        tickers = [r["ticker"] for r in (await client.get("/api/watchlist")).json()["tickers"]]
        assert "AAPL" not in tickers

    async def test_delete_rejects_a_bad_symbol(self, client):
        response = await client.delete("/api/watchlist/TOOLONG")

        assert response.status_code == 400
        assert response.json() == {"error": "Invalid ticker format"}


class TestChatRoutes:
    """app.llm.chat is owned by another role and is stubbed here. These cover
    the wrapper only: delegation, trimming, and the error shapes."""

    @pytest.fixture
    def llm(self, monkeypatch):
        from app.llm import chat as llm_chat

        calls = {}

        async def handle_chat(message):
            calls["message"] = message
            return {
                "id": "1",
                "role": "assistant",
                "content": "ok",
                "actions": [],
                "created_at": "2026-01-01T00:00:00Z",
            }

        async def get_history(limit=20):
            calls["limit"] = limit
            return {"messages": []}

        monkeypatch.setattr(llm_chat, "handle_chat", handle_chat)
        monkeypatch.setattr(llm_chat, "get_history", get_history)
        return calls

    async def test_post_delegates_the_trimmed_message(self, client, llm):
        response = await client.post("/api/chat", json={"message": "  buy AAPL  "})

        assert response.status_code == 200
        assert llm["message"] == "buy AAPL"
        assert set(response.json()) == {"id", "role", "content", "actions", "created_at"}

    async def test_get_defaults_to_twenty_messages(self, client, llm):
        response = await client.get("/api/chat")

        assert response.status_code == 200
        assert response.json() == {"messages": []}
        assert llm["limit"] == 20

    async def test_get_passes_an_explicit_limit(self, client, llm):
        await client.get("/api/chat", params={"limit": 5})
        assert llm["limit"] == 5

    async def test_empty_message_is_400(self, client, llm):
        response = await client.post("/api/chat", json={"message": "   "})

        assert response.status_code == 400
        assert response.json() == {"error": "Message cannot be empty"}
        assert "message" not in llm

    async def test_history_limit_is_validated(self, client):
        response = await client.get("/api/chat", params={"limit": 0})

        assert response.status_code == 400
        assert set(response.json()) == {"error"}
        assert "limit" in response.json()["error"]


class TestStaticServing:
    async def test_api_routes_are_not_shadowed_by_the_static_mount(self, client):
        assert (await client.get("/api/health")).status_code == 200

    async def test_a_missing_static_directory_does_not_crash_the_app(self, client):
        """Local dev has no build output; the API must still serve."""
        assert (await client.get("/api/portfolio")).status_code == 200
