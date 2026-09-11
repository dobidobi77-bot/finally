"""Portfolio routes. ServiceError is turned into 400 {"error"} by the app handler."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import portfolio_service

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class TradeRequest(BaseModel):
    """Body of POST /api/portfolio/trade.

    Fields stay loose so the service layer owns validation and every rejection
    comes back in one shape, rather than FastAPI's 422 for some and ours for
    the rest.
    """

    ticker: object = None
    quantity: object = None
    side: object = None


@router.get("")
async def get_portfolio() -> dict:
    return await portfolio_service.get_portfolio()


@router.post("/trade")
async def trade(body: TradeRequest) -> dict:
    return await portfolio_service.execute_trade(body.ticker, body.side, body.quantity)


@router.get("/history")
async def history() -> dict:
    return await portfolio_service.get_history()
