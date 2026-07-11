"""Generic CRUD router factory.

Builds a full REST resource (list / create / retrieve / update / delete) for a
SQLAlchemy model + its Pydantic schemas, keeping every entity consistent and
DRY. `on_create` lets an entity hook in extra logic (e.g. PO number gen).
"""
from typing import Callable, List, Optional, Type

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .database import get_db
from .security import get_current_active_user, require_roles


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

    def _get_or_404(item_id: int, db: Session):
        obj = db.get(model, item_id)
        if obj is None:
            raise HTTPException(status_code=404, detail=f"{tag} {item_id} not found")
        return obj

    @router.get("", response_model=List[read_schema], summary=f"List {tag}",
                dependencies=read_dep)
    def list_items(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        q: Optional[str] = Query(None, description="Case-insensitive search"),
        db: Session = Depends(get_db),
    ):
        query = db.query(model)
        if q and search_fields:
            query = query.filter(
                or_(*[getattr(model, f).ilike(f"%{q}%") for f in search_fields])
            )
        return query.order_by(model.id).offset(skip).limit(limit).all()

    @router.post("", response_model=read_schema, status_code=201, summary=f"Create {tag}",
                 dependencies=write_dep)
    def create_item(payload: create_schema, db: Session = Depends(get_db)):
        obj = model(**payload.model_dump(exclude_unset=True))
        if on_create is not None:
            on_create(obj, db)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    @router.get("/{item_id}", response_model=read_schema, summary=f"Get one {tag}",
                dependencies=read_dep)
    def get_item(item_id: int, db: Session = Depends(get_db)):
        return _get_or_404(item_id, db)

    @router.patch("/{item_id}", response_model=read_schema, summary=f"Update {tag}",
                  dependencies=write_dep)
    def update_item(item_id: int, payload: update_schema, db: Session = Depends(get_db)):
        obj = _get_or_404(item_id, db)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(obj, key, value)
        db.commit()
        db.refresh(obj)
        return obj

    @router.delete("/{item_id}", status_code=204, summary=f"Delete {tag}",
                   dependencies=write_dep)
    def delete_item(item_id: int, db: Session = Depends(get_db)):
        obj = _get_or_404(item_id, db)
        db.delete(obj)
        db.commit()

    return router


def generate_po_number(obj, db: Session) -> None:
    """Assign the next PO-YYYY-NNN number if one wasn't supplied."""
    from .models import PurchaseOrder

    if getattr(obj, "po_number", None):
        return
    existing = db.query(PurchaseOrder.po_number).all()
    nums = [
        int(n.rsplit("-", 1)[-1])
        for (n,) in existing
        if n and n.rsplit("-", 1)[-1].isdigit()
    ]
    nxt = (max(nums) + 1) if nums else 1
    obj.po_number = f"PO-2024-{nxt:03d}"
