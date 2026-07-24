"""Module enablement API — inspect registered modules and toggle them per tenant."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import models
from .database import get_db
from .module_registry import all_manifests, get_manifest, is_module_enabled
from .models import User
from .security import get_current_active_user, is_admin, require_roles

router = APIRouter(prefix="/modules", tags=["modules"])


class ModuleInfo(BaseModel):
    name: str
    version: str
    depends_on: List[str]
    default_enabled: bool
    enabled: bool


class ModuleToggle(BaseModel):
    enabled: bool
    # Platform admins may target a specific tenant; otherwise the caller's tenant.
    tenant_id: Optional[int] = None


@router.get("", response_model=List[ModuleInfo], summary="List registered modules")
def list_modules(db: Session = Depends(get_db),
                 user: User = Depends(get_current_active_user)):
    return [
        ModuleInfo(
            name=m.name, version=m.version, depends_on=m.depends_on,
            default_enabled=m.default_enabled,
            enabled=is_module_enabled(db, m.name, user),
        )
        for m in all_manifests()
    ]


@router.put("/{name}", response_model=ModuleInfo,
            dependencies=[Depends(require_roles())],  # admin only
            summary="Enable/disable a module for a tenant")
def set_module(name: str, payload: ModuleToggle, db: Session = Depends(get_db),
               user: User = Depends(get_current_active_user)):
    manifest = get_manifest(name)
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"Unknown module '{name}'")

    # Platform admins (no tenant) may target any tenant; a tenant-scoped admin
    # can only toggle their own tenant.
    target = payload.tenant_id if (is_admin(user) and user.tenant_id is None) else user.tenant_id

    row = (db.query(models.TenantModule)
           .filter(models.TenantModule.tenant_id == target,
                   models.TenantModule.module_name == name)
           .first())
    if row is None:
        row = models.TenantModule(tenant_id=target, module_name=name)
        db.add(row)
    row.enabled = payload.enabled
    row.updated_at = datetime.utcnow()
    db.commit()

    return ModuleInfo(
        name=manifest.name, version=manifest.version, depends_on=manifest.depends_on,
        default_enabled=manifest.default_enabled, enabled=payload.enabled,
    )
