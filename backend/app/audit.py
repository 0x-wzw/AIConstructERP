"""Audit log utility — records every mutation to the audit_log table."""
from typing import Optional

from sqlalchemy.orm import Session

from .models import AuditLog, User


def log_action(
    db: Session,
    *,
    user: Optional[User],
    action: str,
    entity_type: str,
    entity_id: Optional[int] = None,
    summary: str = "",
    tenant_id: Optional[int] = None,
) -> AuditLog:
    """Create an immutable audit log entry. Does NOT commit — caller commits."""
    if user is not None and tenant_id is None:
        tenant_id = user.tenant_id
    entry = AuditLog(
        user_id=user.id if user else None,
        user_email=user.email if user else "system",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary[:500],
        tenant_id=tenant_id,
    )
    db.add(entry)
    return entry