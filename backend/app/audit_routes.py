"""Audit log endpoints — read-only access to the audit trail."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from . import models
from .database import get_db
from .models import User
from .security import get_current_active_user

router = APIRouter(prefix="/audit", tags=["audit"])

ORM = ConfigDict(from_attributes=True)


class AuditLogRead(BaseModel):
    model_config = ORM
    id: int
    tenant_id: Optional[int] = None
    user_id: Optional[int] = None
    user_email: str
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    summary: str
    created_at: str


@router.get("", response_model=List[AuditLogRead], summary="List audit log entries")
def list_audit(
    entity_type: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    """List audit log entries, auto-filtered to the user's tenant."""
    q = db.query(models.AuditLog)
    if user.tenant_id is not None:
        q = q.filter(models.AuditLog.tenant_id == user.tenant_id)
    if entity_type:
        q = q.filter(models.AuditLog.entity_type == entity_type)
    if action:
        q = q.filter(models.AuditLog.action == action)
    entries = q.order_by(models.AuditLog.id.desc()).offset(skip).limit(limit).all()
    return [
        AuditLogRead(
            id=e.id,
            tenant_id=e.tenant_id,
            user_id=e.user_id,
            user_email=e.user_email,
            action=e.action,
            entity_type=e.entity_type,
            entity_id=e.entity_id,
            summary=e.summary,
            created_at=e.created_at.isoformat() if e.created_at else "",
        )
        for e in entries
    ]