"""MyInvois e-invoice API: per-tenant config, line items, and the
submit / status / cancel / validate-TIN clearance lifecycle.

Tenant isolation and RBAC follow the same rules as the rest of the app:
reads require an authenticated user scoped to their tenant; credential config
is admin-only; submit/cancel require the accounting role (admins always
allowed).
"""
from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from . import models
from .audit import log_action
from .database import get_db
from .einvoice.backends import get_einvoice_backend
from .einvoice.schemas import (
    CancelRequest,
    EInvoiceLineCreate,
    EInvoiceLineRead,
    MyInvoisConfigRead,
    MyInvoisConfigUpsert,
    StatusResult,
    SubmitResult,
    TinValidationResult,
)
from .encryption import encrypt_secret
from .models import User
from .security import Role, get_current_active_user, is_admin, require_roles

router = APIRouter(prefix="/einvoice", tags=["einvoice"])

ACCT = Role.accounting.value


# ── helpers ───────────────────────────────────────────────────────────
def _get_config(db: Session, user: User) -> models.MyInvoisConfig | None:
    # Config is per-tenant; each caller (admin included) manages the row for
    # their own tenant_id. Cross-tenant config administration is out of scope
    # for this scaffold.
    return (db.query(models.MyInvoisConfig)
            .filter(models.MyInvoisConfig.tenant_id == user.tenant_id)
            .first())


def _config_to_read(c: models.MyInvoisConfig) -> dict:
    return {
        "id": c.id, "tenant_id": c.tenant_id, "enabled": c.enabled,
        "environment": c.environment, "tin": c.tin, "registration_no": c.registration_no,
        "sst_no": c.sst_no, "msic_code": c.msic_code, "business_activity": c.business_activity,
        "email": c.email, "address_line": c.address_line, "city": c.city,
        "state_code": c.state_code, "postal_code": c.postal_code,
        "country_code": c.country_code, "client_id": c.client_id,
        "is_intermediary": c.is_intermediary, "onbehalf_tin": c.onbehalf_tin,
        "cert_ref": c.cert_ref, "has_client_secret": bool(c.client_secret_enc),
        "created_at": c.created_at, "updated_at": c.updated_at,
    }


def _get_invoice(db: Session, invoice_id: int, user: User) -> models.EInvoice:
    inv = db.get(models.EInvoice, invoice_id)
    if inv is None or inv.is_archived:
        raise HTTPException(status_code=404, detail="E-invoice not found")
    if not is_admin(user) and inv.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="E-invoice not found")
    return inv


def _require_ready_config(db: Session, user: User) -> models.MyInvoisConfig:
    cfg = _get_config(db, user)
    if cfg is None or not cfg.enabled:
        raise HTTPException(
            status_code=400,
            detail="MyInvois is not configured/enabled for this tenant. "
                   "Set it up via PUT /api/einvoice/config first.",
        )
    return cfg


# ── config (admin-only: holds API credentials) ────────────────────────
@router.get("/config", response_model=MyInvoisConfigRead,
            dependencies=[Depends(require_roles())], summary="Get MyInvois config")
def get_config(db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    cfg = _get_config(db, user)
    if cfg is None:
        raise HTTPException(status_code=404, detail="No MyInvois config for this tenant")
    return _config_to_read(cfg)


@router.put("/config", response_model=MyInvoisConfigRead,
            dependencies=[Depends(require_roles())], summary="Create/update MyInvois config")
def upsert_config(payload: MyInvoisConfigUpsert, db: Session = Depends(get_db),
                  user: User = Depends(get_current_active_user)):
    cfg = _get_config(db, user)
    data = payload.model_dump(exclude_unset=True)
    secret = data.pop("client_secret", None)
    if cfg is None:
        cfg = models.MyInvoisConfig(tenant_id=user.tenant_id)
        db.add(cfg)
    for key, value in data.items():
        setattr(cfg, key, value)
    if secret is not None:  # only touch the secret when explicitly provided
        cfg.client_secret_enc = encrypt_secret(secret) if secret else ""
    cfg.updated_at = datetime.utcnow()
    db.flush()
    log_action(db, user=user, action="update", entity_type="myinvois_config",
               entity_id=cfg.id, summary="Updated MyInvois config")
    db.commit()
    db.refresh(cfg)
    return _config_to_read(cfg)


# ── line items ────────────────────────────────────────────────────────
@router.get("/{invoice_id}/lines", response_model=List[EInvoiceLineRead],
            summary="List e-invoice line items")
def list_lines(invoice_id: int, db: Session = Depends(get_db),
               user: User = Depends(get_current_active_user)):
    inv = _get_invoice(db, invoice_id, user)
    return sorted(inv.lines, key=lambda x: x.line_no)


@router.put("/{invoice_id}/lines", response_model=List[EInvoiceLineRead],
            dependencies=[Depends(require_roles(ACCT))], summary="Replace e-invoice line items")
def replace_lines(invoice_id: int, lines: List[EInvoiceLineCreate],
                  db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    inv = _get_invoice(db, invoice_id, user)
    if inv.myinvois_status in ("submitted", "valid"):
        raise HTTPException(status_code=409, detail="Cannot edit lines after submission")
    inv.lines.clear()
    db.flush()
    for ln in lines:
        inv.lines.append(models.EInvoiceLine(tenant_id=inv.tenant_id, **ln.model_dump()))
    db.commit()
    db.refresh(inv)
    return sorted(inv.lines, key=lambda x: x.line_no)


# ── clearance lifecycle ───────────────────────────────────────────────
@router.post("/{invoice_id}/submit", response_model=SubmitResult,
             dependencies=[Depends(require_roles(ACCT))], summary="Submit to MyInvois")
def submit(invoice_id: int, db: Session = Depends(get_db),
           user: User = Depends(get_current_active_user)):
    inv = _get_invoice(db, invoice_id, user)
    cfg = _require_ready_config(db, user)
    if inv.myinvois_status in ("submitted", "valid"):
        raise HTTPException(status_code=409, detail=f"Already {inv.myinvois_status}")

    backend = get_einvoice_backend()
    inv.myinvois_status = "submitting"
    db.flush()
    try:
        result = backend.submit(inv, cfg)
    except Exception as exc:  # noqa: BLE001 — surface any backend/mapping/signing error
        inv.myinvois_status = "invalid"
        inv.myinvois_error = str(exc)[:2000]
        db.commit()
        raise HTTPException(status_code=502, detail=f"MyInvois submission failed: {exc}")

    _apply(inv, result)
    inv.submitted_at = datetime.utcnow()
    if inv.myinvois_status == "valid":
        inv.validated_at = datetime.utcnow()
    log_action(db, user=user, action="submit", entity_type="e_invoices",
               entity_id=inv.id, summary=f"Submitted e-invoice to MyInvois ({backend.name})")
    db.commit()
    db.refresh(inv)
    return SubmitResult(e_invoice_id=inv.id, myinvois_status=inv.myinvois_status,
                        submission_uid=inv.submission_uid, myinvois_uuid=inv.myinvois_uuid,
                        validation_link=inv.validation_link, error=inv.myinvois_error)


@router.get("/{invoice_id}/status", response_model=StatusResult,
            summary="Refresh MyInvois clearance status")
def refresh_status(invoice_id: int, db: Session = Depends(get_db),
                   user: User = Depends(get_current_active_user)):
    inv = _get_invoice(db, invoice_id, user)
    if inv.myinvois_status in ("not_submitted", ""):
        raise HTTPException(status_code=409, detail="Not submitted yet")
    cfg = _require_ready_config(db, user)
    backend = get_einvoice_backend()
    try:
        result = backend.get_status(inv, cfg)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Status check failed: {exc}")
    _apply(inv, result)
    if inv.myinvois_status == "valid" and inv.validated_at is None:
        inv.validated_at = datetime.utcnow()
    db.commit()
    db.refresh(inv)
    return StatusResult(e_invoice_id=inv.id, myinvois_status=inv.myinvois_status,
                        myinvois_uuid=inv.myinvois_uuid, myinvois_long_id=inv.myinvois_long_id,
                        validation_link=inv.validation_link, error=inv.myinvois_error)


@router.post("/{invoice_id}/cancel", response_model=StatusResult,
             dependencies=[Depends(require_roles(ACCT))], summary="Cancel a validated e-invoice")
def cancel(invoice_id: int, payload: CancelRequest, db: Session = Depends(get_db),
           user: User = Depends(get_current_active_user)):
    inv = _get_invoice(db, invoice_id, user)
    if inv.myinvois_status not in ("submitted", "valid"):
        raise HTTPException(status_code=409, detail="Only a submitted/valid document can be cancelled")
    cfg = _require_ready_config(db, user)
    backend = get_einvoice_backend()
    try:
        result = backend.cancel(inv, cfg, payload.reason)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Cancellation failed: {exc}")
    _apply(inv, result)
    inv.cancel_reason = payload.reason
    inv.cancelled_at = datetime.utcnow()
    log_action(db, user=user, action="cancel", entity_type="e_invoices",
               entity_id=inv.id, summary=f"Cancelled e-invoice: {payload.reason}")
    db.commit()
    db.refresh(inv)
    return StatusResult(e_invoice_id=inv.id, myinvois_status=inv.myinvois_status,
                        myinvois_uuid=inv.myinvois_uuid, myinvois_long_id=inv.myinvois_long_id,
                        validation_link=inv.validation_link, error=inv.myinvois_error)


@router.get("/validate-tin/{tin}", response_model=TinValidationResult,
            summary="Validate a TIN against MyInvois")
def validate_tin(tin: str, db: Session = Depends(get_db),
                 user: User = Depends(get_current_active_user)):
    cfg = _require_ready_config(db, user)
    backend = get_einvoice_backend()
    try:
        ok = backend.validate_tin(cfg, tin)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"TIN validation failed: {exc}")
    return TinValidationResult(tin=tin, valid=ok, detail="" if ok else "TIN not recognised")


def _apply(inv: models.EInvoice, result: dict) -> None:
    for field in ("myinvois_status", "submission_uid", "myinvois_uuid",
                  "myinvois_long_id", "validation_link"):
        if result.get(field):
            setattr(inv, field, result[field])
    inv.myinvois_error = result.get("error", "") or ""
