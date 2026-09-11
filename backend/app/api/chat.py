"""Chat routes. Thin wrapper over app.llm.chat, which the llm-engineer owns."""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.llm import chat as llm_chat
from app.services.errors import ServiceError

router = APIRouter(prefix="/api/chat", tags=["chat"])

HISTORY_LIMIT = 20  # BUILD_CONTRACT B5


class ChatRequest(BaseModel):
    message: str = ""


@router.get("")
async def get_history(limit: int = Query(HISTORY_LIMIT, ge=1, le=100)) -> dict:
    return await llm_chat.get_history(limit)


@router.post("")
async def send_message(body: ChatRequest) -> dict:
    message = body.message.strip()
    if not message:
        raise ServiceError("Message cannot be empty")
    return await llm_chat.handle_chat(message)
