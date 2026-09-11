"""Health check endpoint."""

from __future__ import annotations

import os

from fastapi import APIRouter

from app import state

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
async def health() -> dict:
    """Readiness gate for Docker and the E2E suite (BUILD_CONTRACT B14)."""
    return {
        "status": "ok",
        "market_source": "massive" if os.environ.get("MASSIVE_API_KEY", "").strip() else "simulator",
        "cache_ready": len(state.price_cache) > 0,
    }
