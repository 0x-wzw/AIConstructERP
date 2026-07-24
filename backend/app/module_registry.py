"""Module registry — the contract every pluggable module satisfies.

A module is a self-contained feature that exposes a `ModuleManifest`. `main.py`
registers manifests and mounts each router through the registry (with a
per-tenant enablement gate) instead of hand-wiring routers one by one.

Enablement rules:
- Platform admins always have access (they are cross-tenant).
- Otherwise the `tenant_modules` table decides; absent row ⇒ `default_enabled`.

This is intentionally an EXPLICIT registry (main.py calls `register(...)`) rather
than import-magic, so the mounted surface is auditable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Type

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from .models import TenantModule, User
from .security import get_current_active_user, is_admin


@dataclass
class ModuleManifest:
    name: str
    version: str
    router: APIRouter
    models: List[Type] = field(default_factory=list)
    migrations: List[str] = field(default_factory=list)
    config_model: Optional[Type] = None
    adds_roles: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    default_enabled: bool = True


_REGISTRY: Dict[str, ModuleManifest] = {}


def register(manifest: ModuleManifest) -> ModuleManifest:
    if manifest.name in _REGISTRY:
        raise RuntimeError(f"Module '{manifest.name}' is already registered")
    _REGISTRY[manifest.name] = manifest
    return manifest


def all_manifests() -> List[ModuleManifest]:
    return list(_REGISTRY.values())


def get_manifest(name: str) -> Optional[ModuleManifest]:
    return _REGISTRY.get(name)


def validate_dependencies() -> None:
    """Fail fast if a module declares a dependency on an unregistered module."""
    for m in _REGISTRY.values():
        for dep in m.depends_on:
            if dep not in _REGISTRY:
                raise RuntimeError(
                    f"Module '{m.name}' depends on unknown module '{dep}'")


def is_module_enabled(db: Session, name: str, user: User) -> bool:
    manifest = _REGISTRY.get(name)
    if manifest is None:
        return False
    if is_admin(user):
        return True
    row = (db.query(TenantModule)
           .filter(TenantModule.tenant_id == user.tenant_id,
                   TenantModule.module_name == name)
           .first())
    return manifest.default_enabled if row is None else row.enabled


def require_module(name: str):
    """Router-level dependency: 404 the whole module if it's disabled for the
    caller's tenant. Mounted by main.py, so individual routes stay clean."""
    def dependency(user: User = Depends(get_current_active_user),
                   db: Session = Depends(get_db)) -> None:
        if not is_module_enabled(db, name, user):
            raise HTTPException(status_code=404, detail="Not found")

    return dependency


def reset_registry() -> None:
    """Test/helper hook — clear the registry (used to make registration idempotent
    across app re-imports)."""
    _REGISTRY.clear()
