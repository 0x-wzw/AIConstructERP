"""Pydantic v2 schemas for BRD domain modules.

Each entity follows the Base/Create/Update/Read convention.
These are intentionally flexible (status as str, not Literal) because the
BRD defines workflow states that may evolve.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

ORM = ConfigDict(from_attributes=True)


# ── Generic helper ─────────────────────────────────────────────────────
def _read_base(name: str, fields: dict) -> type:
    """Create a Read schema with id, is_archived, created_at appended."""
    annotations = {**fields, "id": int, "is_archived": bool, "created_at": Optional[datetime]}
    return type(name, (BaseModel,), {
        "__annotations__": annotations,
        "model_config": ORM,
        "id": 0,
        "is_archived": False,
        "created_at": None,
    })


# ── Vendor (Module 1) ──────────────────────────────────────────────────
class VendorBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    registration_no: str = ""
    category: str = ""
    contact_person: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""
    status: str = "pending"
    rating: int = Field(default=0, ge=0, le=5)


class VendorCreate(VendorBase):
    pass


class VendorUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    registration_no: Optional[str] = None
    category: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    status: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=0, le=5)


class VendorRead(VendorBase):
    model_config = ORM
    id: int
    is_archived: bool = False
    created_at: Optional[datetime] = None


# ── Tender (Module 2) ──────────────────────────────────────────────────
class TenderBase(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    status: str = "draft"
    tender_type: str = "public"
    project_id: Optional[int] = None
    submission_deadline: Optional[datetime] = None
    awarded_vendor_id: Optional[int] = None
    awarded_amount: float = Field(default=0, ge=0)


class TenderCreate(TenderBase):
    pass


class TenderUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    description: Optional[str] = None
    status: Optional[str] = None
    tender_type: Optional[str] = None
    project_id: Optional[int] = None
    submission_deadline: Optional[datetime] = None
    awarded_vendor_id: Optional[int] = None
    awarded_amount: Optional[float] = Field(default=None, ge=0)


class TenderRead(TenderBase):
    model_config = ORM
    id: int
    is_archived: bool = False
    created_at: Optional[datetime] = None


# ── BOQ Item (Module 2) ────────────────────────────────────────────────
class BOQItemBase(BaseModel):
    tender_id: Optional[int] = None
    item_no: str = ""
    description: str = ""
    unit: str = ""
    quantity: float = Field(default=0, ge=0)
    rate: float = Field(default=0, ge=0)


class BOQItemCreate(BOQItemBase):
    pass


class BOQItemUpdate(BaseModel):
    tender_id: Optional[int] = None
    item_no: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    quantity: Optional[float] = Field(default=None, ge=0)
    rate: Optional[float] = Field(default=None, ge=0)


class BOQItemRead(BOQItemBase):
    model_config = ORM
    id: int
    is_archived: bool = False


# ── TenderBid (Module 2) ───────────────────────────────────────────────
class TenderBidBase(BaseModel):
    tender_id: int
    vendor_id: Optional[int] = None
    bid_amount: float = Field(default=0, ge=0)
    technical_score: int = Field(default=0, ge=0, le=100)
    status: str = "submitted"


class TenderBidCreate(TenderBidBase):
    pass


class TenderBidUpdate(BaseModel):
    vendor_id: Optional[int] = None
    bid_amount: Optional[float] = Field(default=None, ge=0)
    technical_score: Optional[int] = Field(default=None, ge=0, le=100)
    status: Optional[str] = None


class TenderBidRead(TenderBidBase):
    model_config = ORM
    id: int
    is_archived: bool = False
    submitted_at: Optional[datetime] = None


# ── ProgressClaim (Module 3) ───────────────────────────────────────────
class ProgressClaimBase(BaseModel):
    project_id: Optional[int] = None
    vendor_id: Optional[int] = None
    claim_no: str = ""
    period: str = ""
    claim_amount: float = Field(default=0, ge=0)
    certified_amount: float = Field(default=0, ge=0)
    status: str = "submitted"


class ProgressClaimCreate(ProgressClaimBase):
    pass


class ProgressClaimUpdate(BaseModel):
    project_id: Optional[int] = None
    vendor_id: Optional[int] = None
    claim_no: Optional[str] = None
    period: Optional[str] = None
    claim_amount: Optional[float] = Field(default=None, ge=0)
    certified_amount: Optional[float] = Field(default=None, ge=0)
    status: Optional[str] = None


class ProgressClaimRead(ProgressClaimBase):
    model_config = ORM
    id: int
    is_archived: bool = False
    created_at: Optional[datetime] = None


# ── PaymentCertificate (Module 3) ──────────────────────────────────────
class PaymentCertificateBase(BaseModel):
    project_id: Optional[int] = None
    vendor_id: Optional[int] = None
    certificate_no: str = ""
    claim_id: Optional[int] = None
    gross_amount: float = Field(default=0, ge=0)
    retention_amount: float = Field(default=0, ge=0)
    net_amount: float = Field(default=0, ge=0)
    status: str = "pending"


class PaymentCertificateCreate(PaymentCertificateBase):
    pass


class PaymentCertificateUpdate(BaseModel):
    project_id: Optional[int] = None
    vendor_id: Optional[int] = None
    certificate_no: Optional[str] = None
    claim_id: Optional[int] = None
    gross_amount: Optional[float] = Field(default=None, ge=0)
    retention_amount: Optional[float] = Field(default=None, ge=0)
    net_amount: Optional[float] = Field(default=None, ge=0)
    status: Optional[str] = None


class PaymentCertificateRead(PaymentCertificateBase):
    model_config = ORM
    id: int
    is_archived: bool = False
    created_at: Optional[datetime] = None


# ── Consultant (Module 4) ──────────────────────────────────────────────
class ConsultantBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    firm: str = ""
    discipline: str = ""
    email: str = ""
    phone: str = ""
    status: str = "active"
    appointment_date: Optional[datetime] = None


class ConsultantCreate(ConsultantBase):
    pass


class ConsultantUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    firm: Optional[str] = None
    discipline: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    appointment_date: Optional[datetime] = None


class ConsultantRead(ConsultantBase):
    model_config = ORM
    id: int
    is_archived: bool = False
    created_at: Optional[datetime] = None


# ── Submittal (Module 6) ───────────────────────────────────────────────
class SubmittalBase(BaseModel):
    project_id: Optional[int] = None
    submittal_no: str = ""
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    status: str = "submitted"
    submitted_by: str = ""


class SubmittalCreate(SubmittalBase):
    pass


class SubmittalUpdate(BaseModel):
    project_id: Optional[int] = None
    submittal_no: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    submitted_by: Optional[str] = None


class SubmittalRead(SubmittalBase):
    model_config = ORM
    id: int
    is_archived: bool = False
    created_at: Optional[datetime] = None


# ── Defect (Module 6) ──────────────────────────────────────────────────
class DefectBase(BaseModel):
    project_id: Optional[int] = None
    defect_no: str = ""
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    location: str = ""
    severity: str = "minor"
    status: str = "open"


class DefectCreate(DefectBase):
    pass


class DefectUpdate(BaseModel):
    project_id: Optional[int] = None
    defect_no: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None


class DefectRead(DefectBase):
    model_config = ORM
    id: int
    is_archived: bool = False
    created_at: Optional[datetime] = None


# ── Inspection (Module 6) ──────────────────────────────────────────────
class InspectionBase(BaseModel):
    project_id: Optional[int] = None
    inspection_no: str = ""
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    inspector: str = ""
    result: str = "pending"


class InspectionCreate(InspectionBase):
    pass


class InspectionUpdate(BaseModel):
    project_id: Optional[int] = None
    inspection_no: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    inspector: Optional[str] = None
    result: Optional[str] = None


class InspectionRead(InspectionBase):
    model_config = ORM
    id: int
    is_archived: bool = False
    created_at: Optional[datetime] = None


# ── SiteDiary (Module 6) ───────────────────────────────────────────────
class SiteDiaryBase(BaseModel):
    project_id: Optional[int] = None
    diary_date: Optional[datetime] = None
    weather: str = ""
    manpower: int = Field(default=0, ge=0)
    work_summary: str = ""
    issues: str = ""
    prepared_by: str = ""


class SiteDiaryCreate(SiteDiaryBase):
    pass


class SiteDiaryUpdate(BaseModel):
    project_id: Optional[int] = None
    diary_date: Optional[datetime] = None
    weather: Optional[str] = None
    manpower: Optional[int] = Field(default=None, ge=0)
    work_summary: Optional[str] = None
    issues: Optional[str] = None
    prepared_by: Optional[str] = None


class SiteDiaryRead(SiteDiaryBase):
    model_config = ORM
    id: int
    is_archived: bool = False
    created_at: Optional[datetime] = None


# ── CostCode (Module 8) ────────────────────────────────────────────────
class CostCodeBase(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    description: str = ""
    category: str = ""


class CostCodeCreate(CostCodeBase):
    pass


class CostCodeUpdate(BaseModel):
    code: Optional[str] = Field(default=None, min_length=1, max_length=30)
    description: Optional[str] = None
    category: Optional[str] = None


class CostCodeRead(CostCodeBase):
    model_config = ORM
    id: int
    is_archived: bool = False


# ── PurchaseRequest (Module 8) ─────────────────────────────────────────
class PurchaseRequestBase(BaseModel):
    project_id: Optional[int] = None
    request_no: str = ""
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    estimated_amount: float = Field(default=0, ge=0)
    status: str = "draft"


class PurchaseRequestCreate(PurchaseRequestBase):
    pass


class PurchaseRequestUpdate(BaseModel):
    project_id: Optional[int] = None
    request_no: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    estimated_amount: Optional[float] = Field(default=None, ge=0)
    status: Optional[str] = None


class PurchaseRequestRead(PurchaseRequestBase):
    model_config = ORM
    id: int
    is_archived: bool = False
    created_at: Optional[datetime] = None


# ── RFQ (Module 8) ──────────────────────────────────────────────────────
class RFQBase(BaseModel):
    purchase_request_id: Optional[int] = None
    rfq_no: str = ""
    description: str = ""
    deadline: Optional[datetime] = None
    status: str = "open"


class RFQCreate(RFQBase):
    pass


class RFQUpdate(BaseModel):
    purchase_request_id: Optional[int] = None
    rfq_no: Optional[str] = None
    description: Optional[str] = None
    deadline: Optional[datetime] = None
    status: Optional[str] = None


class RFQRead(RFQBase):
    model_config = ORM
    id: int
    is_archived: bool = False
    created_at: Optional[datetime] = None


# ── GoodsReceipt (Module 8) ────────────────────────────────────────────
class GoodsReceiptBase(BaseModel):
    purchase_order_id: Optional[int] = None
    receipt_no: str = ""
    received_date: Optional[datetime] = None
    quantity_received: float = Field(default=0, ge=0)
    condition: str = "good"
    notes: str = ""
    status: str = "pending"


class GoodsReceiptCreate(GoodsReceiptBase):
    pass


class GoodsReceiptUpdate(BaseModel):
    purchase_order_id: Optional[int] = None
    receipt_no: Optional[str] = None
    received_date: Optional[datetime] = None
    quantity_received: Optional[float] = Field(default=None, ge=0)
    condition: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class GoodsReceiptRead(GoodsReceiptBase):
    model_config = ORM
    id: int
    is_archived: bool = False
    created_at: Optional[datetime] = None


# ── EInvoice (Module 8) ────────────────────────────────────────────────
class EInvoiceBase(BaseModel):
    purchase_order_id: Optional[int] = None
    invoice_no: str = ""
    vendor_name: str = ""
    invoice_date: Optional[datetime] = None
    subtotal: float = Field(default=0, ge=0)
    tax_amount: float = Field(default=0, ge=0)
    total_amount: float = Field(default=0, ge=0)
    status: str = "draft"


class EInvoiceCreate(EInvoiceBase):
    pass


class EInvoiceUpdate(BaseModel):
    purchase_order_id: Optional[int] = None
    invoice_no: Optional[str] = None
    vendor_name: Optional[str] = None
    invoice_date: Optional[datetime] = None
    subtotal: Optional[float] = Field(default=None, ge=0)
    tax_amount: Optional[float] = Field(default=None, ge=0)
    total_amount: Optional[float] = Field(default=None, ge=0)
    status: Optional[str] = None


class EInvoiceRead(EInvoiceBase):
    model_config = ORM
    id: int
    is_archived: bool = False
    created_at: Optional[datetime] = None