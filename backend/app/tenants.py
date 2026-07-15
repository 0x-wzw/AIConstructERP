"""Tenant management endpoints (admin-only)."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from . import models
from .database import get_db
from .security import Role, require_roles

router = APIRouter(prefix="/tenants", tags=["tenants"])

ORM = ConfigDict(from_attributes=True)


class TenantBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class TenantCreate(TenantBase):
    pass


class TenantRead(TenantBase):
    model_config = ORM
    id: int
    created_at: Optional[datetime] = None


@router.get("", response_model=List[TenantRead],
            dependencies=[Depends(require_roles(Role.admin))],
            summary="List tenants (admin)")
def list_tenants(db: Session = Depends(get_db)):
    return db.query(models.Tenant).order_by(models.Tenant.id).all()


@router.post("", response_model=TenantRead, status_code=201,
             dependencies=[Depends(require_roles(Role.admin))],
             summary="Create tenant (admin)")
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Tenant).filter(models.Tenant.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Tenant name already exists")
    tenant = models.Tenant(name=payload.name)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


@router.get("/{tenant_id}", response_model=TenantRead,
            dependencies=[Depends(require_roles(Role.admin))],
            summary="Get tenant (admin)")
def get_tenant(tenant_id: int, db: Session = Depends(get_db)):
    tenant = db.get(models.Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.delete("/{tenant_id}", status_code=204,
               dependencies=[Depends(require_roles(Role.admin))],
               summary="Delete tenant (admin)")
def delete_tenant(tenant_id: int, db: Session = Depends(get_db)):
    tenant = db.get(models.Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    db.delete(tenant)
    db.commit()