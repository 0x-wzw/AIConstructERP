"""SSE streaming endpoint for AI chat — streams token-by-token from the LLM.

When the AI agent is available and the provider supports streaming (OpenAI
and Ollama both do via the OpenAI SDK), the response is streamed via
Server-Sent Events. If the agent is unavailable or streaming fails, it
falls back to the regular non-streaming response.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .ai import ai_agent
from .crud import _tenant_filter
from .database import get_db
from .models import User
from .security import get_current_active_user, require_roles

logger = logging.getLogger("constructerp.sse")

router = APIRouter(prefix="/ai", tags=["ai_streaming"])

PM_ROLE = ["project_manager"]


class StreamChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list = []


@router.post("/chat/stream", summary="Stream AI chat response via SSE",
             dependencies=[Depends(require_roles(*PM_ROLE))])
async def ai_chat_stream(
    payload: StreamChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    """Stream an AI chat response using Server-Sent Events.

    Falls back to a single-event response if streaming is not available.
    """

    def scoped(model):
        q = db.query(model)
        tf = _tenant_filter(model, user)
        if tf is not None:
            q = q.filter(tf)
        return q.all()

    import json as _json

    from . import models as _models

    data_context = {
        "projects": [{"id": p.id, "name": p.name, "progress": p.progress}
                     for p in scoped(_models.Project)],
    }

    async def event_stream():
        if not ai_agent.is_available():
            yield f"data: {_json.dumps({'type': 'done', 'content': 'AI agent not configured.'})}\n\n"
            return

        try:
            # Try streaming from the LLM.
            stream = ai_agent.client.chat.completions.create(
                model=ai_agent.model,
                messages=[{"role": "user", "content": payload.message}],
                max_tokens=800,
                temperature=0.7,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    yield f"data: {_json.dumps({'type': 'token', 'content': token})}\n\n"
            yield f"data: {_json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            logger.error("Streaming failed: %s", e)
            # Fallback: non-streaming response in a single event.
            response = ai_agent.chat(payload.message, payload.history, data_context)
            yield f"data: {_json.dumps({'type': 'done', 'content': response})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )