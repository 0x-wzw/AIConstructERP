"""AI agent API routes — all auth-protected, tenant-scoped.

AI routes require project_manager or admin role. Viewers and accounting
cannot access AI features (AI commands are advisory and should not be
available to read-only or finance-only roles).
"""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from . import models
from .ai import ai_agent
from .crud import _tenant_filter
from .database import get_db
from .models import User
from .security import Role, get_current_active_user, require_roles

router = APIRouter(prefix="/ai", tags=["ai"])

# AI routes require PM or admin (viewers and accounting excluded).
AI_ROLE = [Role.project_manager.value]


class CommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: List[Dict[str, str]] = []


def get_data_context(db: Session, user: User) -> Dict[str, Any]:
    """Gather ERP data for AI context, scoped to the user's tenant."""
    def scoped(model):
        q = db.query(model)
        tf = _tenant_filter(model, user)
        if tf is not None:
            q = q.filter(tf)
        return q.all()

    projects = scoped(models.Project)
    pos = scoped(models.PurchaseOrder)
    budget = scoped(models.BudgetItem)
    subs = scoped(models.Subcontractor)

    return {
        "projects": [
            {"id": p.id, "name": p.name, "budget": float(p.budget),
             "progress": p.progress, "status": p.status}
            for p in projects
        ],
        "purchase_orders": [
            {"id": po.id, "supplier": po.supplier, "amount": float(po.amount),
             "status": po.status}
            for po in pos
        ],
        "budget": [
            {"category": b.category, "budget": float(b.budget), "spent": float(b.spent)}
            for b in budget
        ],
        "subcontractors": [
            {"id": s.id, "name": s.name, "contract": float(s.contract),
             "progress": s.progress}
            for s in subs
        ],
    }


@router.get("/status", summary="Check AI agent availability",
            dependencies=[Depends(require_roles(*AI_ROLE))])
def ai_status():
    return {
        "available": ai_agent.is_available(),
        "provider": ai_agent.provider if ai_agent.is_available() else None,
        "model": ai_agent.model if ai_agent.is_available() else None,
    }


@router.post("/command", summary="Process a natural language command",
             dependencies=[Depends(require_roles(*AI_ROLE))])
def ai_command(
    payload: CommandRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    if not ai_agent.is_available():
        return {"action": "error", "message": "AI agent not configured."}
    context = get_data_context(db, user)
    return ai_agent.process_command(payload.command, context)


@router.post("/analyze", summary="Analyze budget/project data",
             dependencies=[Depends(require_roles(*AI_ROLE))])
def ai_analyze(db: Session = Depends(get_db),
               user: User = Depends(get_current_active_user)):
    if not ai_agent.is_available():
        return {"analysis": "AI agent not configured."}
    # Query only budget data directly instead of loading the full context.
    q = db.query(models.BudgetItem)
    tf = _tenant_filter(models.BudgetItem, user)
    if tf is not None:
        q = q.filter(tf)
    if hasattr(models.BudgetItem, "is_archived"):
        q = q.filter(models.BudgetItem.is_archived == False)  # noqa: E712
    budget_data = [
        {"category": b.category, "budget": float(b.budget),
         "committed": float(b.committed), "spent": float(b.spent)}
        for b in q.all()
    ]
    return {"analysis": ai_agent.analyze_budget(budget_data)}


@router.get("/briefing", summary="Get AI-powered morning briefing",
            dependencies=[Depends(require_roles(*AI_ROLE))])
def ai_briefing(db: Session = Depends(get_db),
                user: User = Depends(get_current_active_user)):
    if not ai_agent.is_available():
        return {"briefing": "AI agent not configured."}
    context = get_data_context(db, user)
    return {"briefing": ai_agent.generate_briefing(context)}


@router.post("/chat", summary="Conversational AI assistant",
             dependencies=[Depends(require_roles(*AI_ROLE))])
def ai_chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    if not ai_agent.is_available():
        return {"response": "AI agent not configured."}
    context = get_data_context(db, user)
    return {"response": ai_agent.chat(payload.message, payload.history, context)}