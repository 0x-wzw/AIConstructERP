"""AI chat persistence routes — create sessions, list messages, send messages.

Chat sessions are persisted so conversations survive page reloads and can be
reviewed later. Each session belongs to a user and tenant.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from . import models
from .ai import ai_agent
from .brd_schemas2 import (
    ChatMessageCreate,
    ChatMessageRead,
    ChatSessionCreate,
    ChatSessionRead,
)
from .crud import _tenant_filter
from .database import get_db
from .models import User
from .security import get_current_active_user, require_roles

router = APIRouter(prefix="/ai/chat", tags=["ai_chat"])

PM_ROLE = ["project_manager"]


def _get_session_or_404(db: Session, session_id: int, user: User) -> models.ChatSession:
    session = db.get(models.ChatSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    if user.tenant_id is not None and session.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Chat session not found")
    if session.user_id is not None and session.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session


@router.get("/sessions", response_model=List[ChatSessionRead],
            summary="List chat sessions",
            dependencies=[Depends(require_roles(*PM_ROLE))])
def list_sessions(db: Session = Depends(get_db),
                  user: User = Depends(get_current_active_user)):
    q = db.query(models.ChatSession).filter(models.ChatSession.user_id == user.id)
    if user.tenant_id is not None:
        q = q.filter(models.ChatSession.tenant_id == user.tenant_id)
    return q.order_by(models.ChatSession.id.desc()).all()


@router.post("/sessions", response_model=ChatSessionRead, status_code=201,
             summary="Create chat session",
             dependencies=[Depends(require_roles(*PM_ROLE))])
def create_session(payload: ChatSessionCreate,
                   db: Session = Depends(get_db),
                   user: User = Depends(get_current_active_user)):
    session = models.ChatSession(
        tenant_id=user.tenant_id,
        user_id=user.id,
        title=payload.title,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageRead],
             summary="List messages in a chat session",
             dependencies=[Depends(require_roles(*PM_ROLE))])
def list_messages(session_id: int, db: Session = Depends(get_db),
                  user: User = Depends(get_current_active_user)):
    _get_session_or_404(db, session_id, user)
    return (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.session_id == session_id)
        .order_by(models.ChatMessage.id.asc())
        .all()
    )


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageRead,
              status_code=201, summary="Send a message and get AI reply",
              dependencies=[Depends(require_roles(*PM_ROLE))])
def send_message(session_id: int, payload: ChatMessageCreate,
                 db: Session = Depends(get_db),
                 user: User = Depends(get_current_active_user)):
    _get_session_or_404(db, session_id, user)  # 404-guard: validates ownership

    # Save the user's message.
    user_msg = models.ChatMessage(
        session_id=session_id,
        role="user",
        content=payload.content,
    )
    db.add(user_msg)
    db.flush()

    # Build history from existing messages.
    history = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.session_id == session_id)
        .order_by(models.ChatMessage.id.asc())
        .all()
    )
    history_dicts = [{"role": m.role, "content": m.content} for m in history]

    # Gather data context for AI.
    def scoped(model):
        q = db.query(model)
        tf = _tenant_filter(model, user)
        if tf is not None:
            q = q.filter(tf)
        return q.all()


    data_context = {
        "projects": [{"id": p.id, "name": p.name, "progress": p.progress} for p in scoped(models.Project)],
        "budget": [{"category": b.category, "budget": float(b.budget), "spent": float(b.spent)} for b in scoped(models.BudgetItem)],
    }

    # Get AI response.
    ai_response = ai_agent.chat(payload.content, history_dicts[:-1], data_context)

    # Save the AI's message.
    ai_msg = models.ChatMessage(
        session_id=session_id,
        role="assistant",
        content=ai_response,
    )
    db.add(ai_msg)
    db.flush()
    db.commit()
    db.refresh(ai_msg)
    return ai_msg


@router.delete("/sessions/{session_id}", status_code=204,
               summary="Delete chat session",
               dependencies=[Depends(require_roles(*PM_ROLE))])
def delete_session(session_id: int, db: Session = Depends(get_db),
                   user: User = Depends(get_current_active_user)):
    session = _get_session_or_404(db, session_id, user)
    db.delete(session)
    db.commit()