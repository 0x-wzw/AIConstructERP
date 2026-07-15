"""Generic CRUD router factory.

Builds a full REST resource (list / create / retrieve / update / delete) for a
SQLAlchemy model + its Pydantic schemas, keeping every entity consistent and
DRY. `on_create` lets an entity hook in extra logic (e.g. PO number gen).

Multi-tenancy: when the model has a `tenant_id` column and the authenticated
user has a tenant_id, reads are auto-filtered to that tenant and creates are
stamped with it. Admins (tenant_id=None) see all tenants.

Soft delete: when the model has an `is_archived` column, the delete endpoint
sets is_archived=True instead of removing the row. List endpoints exclude
archived rows by default (pass `?include_archived=true` to see them).

Audit: every create/update/delete is recorded in the audit_log table.
"""
import logging
from typing import Callable, List, Optional, Type

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .audit import log_action
from .database import get_db
from .models import User
from .security import get_current_active_user, require_roles

logger = logging.getLogger("constructerp.crud")


def _has_tenant_column(model: Type) -> bool:
    return hasattr(model, "tenant_id")


def _has_archive_column(model: Type) -> bool:
    return hasattr(model, "is_archived")


def _tenant_filter(model: Type, user: User):
    """Return a SQLAlchemy filter condition for the user's tenant, or None."""
    if not _has_tenant_column(model):
        return None
    if user.tenant_id is None:
        return None  # admin / unscoped — see everything
    return model.tenant_id == user.tenant_id


def _entity_tag(model: Type) -> str:
    return model.__tablename__


def make_crud_router(
    *,
    model: Type,
    read_schema: Type,
    create_schema: Type,
    update_schema: Type,
    prefix: str,
    tag: str,
    search_fields: Optional[List[str]] = None,
    on_create: Optional[Callable] = None,
    write_roles: Optional[List[str]] = None,
) -> APIRouter:
    # Reads: any authenticated user. Writes: listed roles (admin always allowed).
    read_dep = [Depends(get_current_active_user)]
    write_dep = [Depends(require_roles(*(write_roles or [])))]
    router = APIRouter(prefix=prefix, tags=[tag])

    def _get_or_404(item_id: int, db: Session, user: User):
        obj = db.get(model, item_id)
        if obj is None:
            raise HTTPException(status_code=404, detail=f"{tag} {item_id} not found")
        # Enforce tenant isolation on single-record access too.
        tf = _tenant_filter(model, user)
        if tf is not None and getattr(obj, "tenant_id", None) != user.tenant_id:
            raise HTTPException(status_code=404, detail=f"{tag} {item_id} not found")
        # Archived items return 404 on single-record access.
        if _has_archive_column(model) and getattr(obj, "is_archived", False):
            raise HTTPException(status_code=404, detail=f"{tag} {item_id} not found")
        return obj

    @router.get("", response_model=List[read_schema], summary=f"List {tag}")
    def list_items(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        q: Optional[str] = Query(None, description="Case-insensitive search"),
        include_archived: bool = Query(False, description="Include archived rows"),
        db: Session = Depends(get_db),
        user: User = Depends(get_current_active_user),
    ):
        query = db.query(model)
        tf = _tenant_filter(model, user)
        if tf is not None:
            query = query.filter(tf)
        # Exclude archived by default.
        if _has_archive_column(model) and not include_archived:
            query = query.filter(model.is_archived == False)  # noqa: E712
        if q and search_fields:
            query = query.filter(
                or_(*[getattr(model, f).ilike(f"%{q}%") for f in search_fields])
            )
        return query.order_by(model.id).offset(skip).limit(limit).all()

    @router.post("", response_model=read_schema, status_code=201, summary=f"Create {tag}")
    def create_item(
        payload: create_schema,
        db: Session = Depends(get_db),
        user: User = Depends(require_roles(*(write_roles or []))),
    ):
        data = payload.model_dump(exclude_unset=True)
        # Stamp tenant_id from the authenticated user (if model supports it).
        if _has_tenant_column(model) and "tenant_id" not in data:
            data["tenant_id"] = user.tenant_id
        obj = model(**data)
        if on_create is not None:
            on_create(obj, db)
        db.add(obj)
        db.flush()  # get the id for audit
        log_action(db, user=user, action="create", entity_type=_entity_tag(model),
                   entity_id=obj.id, summary=f"Created {tag}: {data.get('name', data.get('title', data.get('po_number', obj.id)))}")
        db.commit()
        db.refresh(obj)
        return obj

    @router.get("/{item_id}", response_model=read_schema, summary=f"Get one {tag}")
    def get_item(
        item_id: int,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_active_user),
    ):
        return _get_or_404(item_id, db, user)

    @router.patch("/{item_id}", response_model=read_schema, summary=f"Update {tag}")
    def update_item(
        item_id: int,
        payload: update_schema,
        db: Session = Depends(get_db),
        user: User = Depends(require_roles(*(write_roles or []))),
    ):
        obj = _get_or_404(item_id, db, user)
        changes = payload.model_dump(exclude_unset=True)
        for key, value in changes.items():
            setattr(obj, key, value)
        log_action(db, user=user, action="update", entity_type=_entity_tag(model),
                   entity_id=item_id, summary=f"Updated {tag} {item_id}: {', '.join(changes.keys())}")
        db.commit()
        db.refresh(obj)
        return obj

    @router.delete("/{item_id}", status_code=204, summary=f"Delete {tag}")
    def delete_item(
        item_id: int,
        db: Session = Depends(get_db),
        user: User = Depends(require_roles(*(write_roles or []))),
    ):
        obj = _get_or_404(item_id, db, user)
        if _has_archive_column(model):
            # Soft delete — archive instead of removing.
            obj.is_archived = True
            log_action(db, user=user, action="archive", entity_type=_entity_tag(model),
                       entity_id=item_id, summary=f"Archived {tag} {item_id}")
        else:
            log_action(db, user=user, action="delete", entity_type=_entity_tag(model),
                       entity_id=item_id, summary=f"Deleted {tag} {item_id}")
            db.delete(obj)
        db.commit()

    return router


def generate_po_number(obj, db: Session) -> None:
    """Assign the next PO-YYYY-NNN number if one wasn't supplied.

    Uses a SQL max() on the full po_number column first (O(log n)), falling
    back to Python parsing for the numeric suffix.
    """
    from datetime import datetime

    from sqlalchemy import func as sa_func

    from .models import PurchaseOrder

    if getattr(obj, "po_number", None):
        return
    year = datetime.now().year
    prefix = f"PO-{year}-"
    # Get the highest PO number for this year using a LIKE query.
    max_po = (
        db.query(sa_func.max(PurchaseOrder.po_number))
        .filter(PurchaseOrder.po_number.like(f"{prefix}%"))
        .scalar()
    )
    if max_po:
        suffix = max_po.rsplit("-", 1)[-1]
        if suffix.isdigit():
            obj.po_number = f"{prefix}{int(suffix) + 1:03d}"
            return
    obj.po_number = f"{prefix}001"