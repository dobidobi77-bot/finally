"""Watchlist routes. ServiceError is turned into 400 {"error"} by the app handler."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import watchlist_service

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class TickerRequest(BaseModel):
    ticker: object = None


@router.get("")
async def get_watchlist() -> dict:
    return await watchlist_service.get_watchlist()


@router.post("")
async def add_ticker(body: TickerRequest) -> dict:
    return await watchlist_service.add_ticker(body.ticker)


@router.delete("/{ticker}")
async def remove_ticker(ticker: str) -> dict:
    return await watchlist_service.remove_ticker(ticker)
