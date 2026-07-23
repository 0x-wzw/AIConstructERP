"""Pydantic schemas for the MyInvois e-invoice API surface."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

ORM = ConfigDict(from_attributes=True)


# ── Per-tenant config ─────────────────────────────────────────────────
class MyInvoisConfigBase(BaseModel):
    enabled: bool = False
    environment: str = "sandbox"  # sandbox | production
    tin: str = ""
    registration_no: str = ""
    sst_no: str = ""
    msic_code: str = ""
    business_activity: str = ""
    email: str = ""
    address_line: str = ""
    city: str = ""
    state_code: str = ""
    postal_code: str = ""
    country_code: str = "MYS"
    client_id: str = ""
    is_intermediary: bool = False
    onbehalf_tin: str = ""
    cert_ref: str = ""


class MyInvoisConfigUpsert(MyInvoisConfigBase):
    # Write-only: never echoed back. Omit to leave the stored secret unchanged.
    client_secret: Optional[str] = None


class MyInvoisConfigRead(MyInvoisConfigBase):
    model_config = ORM
    id: int
    tenant_id: Optional[int] = None
    has_client_secret: bool = False  # computed — the secret itself is never returned
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ── Line items ────────────────────────────────────────────────────────
class EInvoiceLineBase(BaseModel):
    line_no: int = 1
    classification_code: str = ""
    description: str = ""
    quantity: float = Field(default=1, ge=0)
    unit_price: float = Field(default=0, ge=0)
    measurement: str = ""
    tax_type: str = ""
    tax_rate: float = Field(default=0, ge=0)
    tax_amount: float = Field(default=0, ge=0)
    discount: float = Field(default=0, ge=0)
    subtotal: float = Field(default=0, ge=0)


class EInvoiceLineCreate(EInvoiceLineBase):
    pass


class EInvoiceLineRead(EInvoiceLineBase):
    model_config = ORM
    id: int


# ── Submission results ────────────────────────────────────────────────
class SubmitResult(BaseModel):
    e_invoice_id: int
    myinvois_status: str
    submission_uid: str = ""
    myinvois_uuid: str = ""
    validation_link: str = ""
    error: str = ""


class StatusResult(BaseModel):
    e_invoice_id: int
    myinvois_status: str
    myinvois_uuid: str = ""
    myinvois_long_id: str = ""
    validation_link: str = ""
    error: str = ""


class CancelRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=300)


class TinValidationResult(BaseModel):
    tin: str
    valid: bool
    detail: str = ""
